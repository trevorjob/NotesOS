"""
NotesOS - Question Generator Service
LangGraph-based test question generation with quality loop.
"""

import asyncio
import json
import uuid
import logging
from typing import TypedDict, List, Dict, Any, Callable, Awaitable, Optional
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.services.llm import call_llm

logger = logging.getLogger(__name__)

from app.config import settings
from app.models.resource import Resource
from app.models.test import Test, TestQuestion, TestType, TestGenerationStatus, QuestionType


class QuestionGenState(TypedDict):
    """State for question generation workflow."""

    test_id: str
    topic_ids: List[str]
    topic_name: str
    resource_content: str
    question_count: int
    difficulty: str
    question_types: List[str]
    generated_questions: List[Dict[str, Any]]
    quality_score: float
    retry_count: int
    # Streaming callback — called after each batch is generated (before quality check)
    on_batch_ready: Optional[Callable[[int, int, List[Dict[str, Any]]], Awaitable[None]]]


BATCH_SIZE = 12  # Questions per parallel API call


class QuestionGenerator:
    """LangGraph-based question generator with quality loop."""

    def __init__(self):
        self.max_retries = 2

    async def create_pending_test(
        self,
        db: AsyncSession,
        course_id: str,
        user_id: str,
        topic_ids: List[str],
        topic_name: str,
        question_count: int = 10,
        difficulty: str = "medium",
        question_types: List[str] = None,
        title: str = None,
    ) -> Test:
        """Create a Test row with status=pending. Returns immediately — no generation."""
        if question_types is None:
            question_types = ["mcq", "short_answer"]

        is_essay = question_types == ["essay"]
        total = 1 if is_essay else question_count
        total_batches = 1 if is_essay else (total + BATCH_SIZE - 1) // BATCH_SIZE

        test = Test(
            course_id=uuid.UUID(course_id),
            created_by=uuid.UUID(user_id),
            title=title or f"Practice Test - {difficulty.capitalize()}",
            test_type=TestType.PRACTICE,
            topics=topic_ids,
            question_types=question_types,
            question_count=total,
            generation_status=TestGenerationStatus.PENDING,
            batches_total=total_batches,
            batches_done=0,
        )
        db.add(test)
        await db.commit()
        await db.refresh(test)
        return test

    async def generate_for_test(
        self,
        db: AsyncSession,
        test: Test,
        on_batch_ready: Optional[Callable[[int, int, List[Dict[str, Any]]], Awaitable[None]]] = None,
    ) -> Test:
        """
        Run the LangGraph generation workflow for an existing pending/generating Test.
        Commits questions per-batch and calls on_batch_ready(batch_index, batches_total, questions)
        after each batch passes through the generate node.

        on_batch_ready fires during generation — before the quality gate. If the quality gate
        triggers a regenerate, the worker clears committed questions and calls on_batch_ready again.
        """
        topic_ids = test.topics
        question_count = test.question_count

        resource_content = await self._gather_resources(db, topic_ids)

        difficulty = self._infer_difficulty(test.title)
        question_types = test.question_types if test.question_types else ["mcq", "short_answer"]
        topic_name = self._infer_topic_name(test.title)

        workflow = self._build_graph()
        app = workflow.compile()

        initial_state = {
            "test_id": str(test.id),
            "topic_ids": topic_ids,
            "topic_name": topic_name,
            "resource_content": resource_content,
            "question_count": question_count,
            "difficulty": difficulty,
            "question_types": question_types,
            "generated_questions": [],
            "quality_score": 0.0,
            "retry_count": 0,
            "on_batch_ready": on_batch_ready,
        }

        result = await app.ainvoke(initial_state)

        # Final commit of any remaining questions not yet saved per-batch
        # (In practice, per-batch saving in _generate_questions handles this.
        # This is a safety net for the quality-loop case.)
        committed_ids = set()
        existing = await db.execute(select(TestQuestion).where(TestQuestion.test_id == test.id))
        for q in existing.scalars().all():
            committed_ids.add(q.order_index)

        for idx, q_data in enumerate(result["generated_questions"]):
            if idx not in committed_ids:
                db.add(TestQuestion(
                    test_id=test.id,
                    question_text=q_data["question_text"],
                    question_type=QuestionType[q_data["question_type"].upper()],
                    correct_answer=q_data.get("correct_answer"),
                    answer_options=q_data.get("answer_options"),
                    points=q_data.get("points", 1),
                    order_index=idx,
                ))

        await db.commit()
        await db.refresh(test)
        return test

    def _infer_difficulty(self, title: str) -> str:
        title_lower = title.lower()
        if "hard" in title_lower:
            return "hard"
        if "easy" in title_lower:
            return "easy"
        return "medium"

    def _infer_topic_name(self, title: str) -> str:
        # Title format: "CODE: Topic A, Topic B — Difficulty"
        # Extract everything between the colon and the em-dash
        if ":" in title and "—" in title:
            return title.split(":", 1)[1].split("—")[0].strip()
        if ":" in title:
            return title.split(":", 1)[1].strip()
        return title

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow."""
        workflow = StateGraph(QuestionGenState)

        workflow.add_node("generate", self._generate_questions)
        workflow.add_node("quality_check", self._quality_check)
        workflow.add_node("regenerate", self._regenerate_with_feedback)

        workflow.set_entry_point("generate")
        workflow.add_edge("generate", "quality_check")
        workflow.add_conditional_edges(
            "quality_check",
            self._should_regenerate,
            {
                "done": END,
                "regenerate": "regenerate",
            },
        )
        workflow.add_edge("regenerate", "generate")

        return workflow

    async def _gather_resources(self, db: AsyncSession, topic_ids: List[str]) -> str:
        """Gather all resource content for topics."""
        topic_uuids = [uuid.UUID(tid) for tid in topic_ids]
        # Quarantined uploads don't feed generated tests either (Merge Agent gate).
        query = select(Resource).where(
            Resource.topic_id.in_(topic_uuids), Resource.quarantined.is_(False)
        )
        result = await db.execute(query)
        resources = result.scalars().all()

        content_parts = []
        for resource in resources:
            if resource.content:
                content_parts.append(f"=== {resource.title} ===\n{resource.content}")

        return "\n\n".join(content_parts)

    def _build_essay_prompt(self, state: QuestionGenState) -> str:
        difficulty_guide = {
            "easy": "Ask the student to explain a core concept clearly, using their own words, with at least one concrete example.",
            "medium": "Ask the student to analyse a relationship, cause-and-effect, or trade-off — they must go beyond recall and show they understand *why*.",
            "hard": "Ask the student to critically evaluate, compare competing ideas, or synthesise across multiple concepts. A strong answer should take a defensible position and support it.",
        }.get(state["difficulty"], "Ask the student to demonstrate deep understanding of a central concept.")

        return f"""You are setting a single essay question for a university student studying {state["topic_name"]}.

This is not a short-answer question. It should require 3–5 paragraphs of sustained argument, analysis, or explanation.

TOPIC: {state["topic_name"]}
DIFFICULTY: {state["difficulty"]}

DIFFICULTY GUIDE FOR THIS QUESTION:
{difficulty_guide}

STUDY MATERIAL:
{state["resource_content"]}

WHAT MAKES A GOOD ESSAY QUESTION:
- Tests understanding of a central, substantive idea — not a peripheral detail
- Requires the student to construct an argument or explanation, not just list facts
- Has enough scope for a strong student to shine and a weak student to expose gaps
- Cannot be answered by quoting the notes directly — requires synthesis
- Is specific enough to be answerable in 3–5 paragraphs; not so broad it's unanswerable

WHAT MAKES A BAD ESSAY QUESTION:
- "Discuss X" — too vague
- "What is X?" — that's a short-answer question
- Anything answerable in 2 sentences
- Questions that test recall, not understanding

The "correct_answer" field should be a marking guide listing:
- The central argument or explanation a strong answer must make
- The key sub-points, evidence, or mechanisms the student should address
- What distinguishes a strong answer from a weak one

Format: "Essay rubric: [central claim the answer must make] | [key point 1] | [key point 2] | [key point 3] | [what a strong answer includes that a weak answer misses]"

Return a JSON array with EXACTLY 1 element:
[
  {{
    "question_text": "The essay question — a complete, clear prompt the student will respond to",
    "question_type": "essay",
    "answer_options": null,
    "correct_answer": "Essay rubric: [central claim] | [key point 1] | [key point 2] | [key point 3] | [distinguisher]",
    "explanation": "What a strong answer demonstrates vs a weak one.",
    "points": 10
  }}
]

Return ONLY valid JSON. No preamble. No text outside the array."""

    def _build_prompt(self, state: QuestionGenState, batch_count: int, batch_index: int, total_batches: int) -> str:
        return f"""You are writing a quiz for a student studying {state["topic_name"]}.
Your job is to write questions that actually test whether someone
understands the material — not just whether they memorised keywords.

Good questions:
- Test a concept, relationship, or application — not just a definition
- Have wrong answers that are plausible (a student who half-understands
  could pick them)
- Are specific enough that someone can answer them without guessing
- Are not trick questions or gotchas

Bad questions (never write these):
- "What is the definition of X?" when X was defined word-for-word in the notes
- Questions with obviously wrong distractors
- Questions testing trivial details that wouldn't appear on a real exam
- Two questions that test essentially the same idea

TOPIC: {state["topic_name"]}
DIFFICULTY: {state["difficulty"]}
NUMBER OF QUESTIONS: {batch_count} (generate EXACTLY this many, no more, no fewer)
QUESTION TYPES ALLOWED: {", ".join(state["question_types"])} — use ONLY these types, no others
BATCH: {batch_index + 1} of {total_batches} — cover a DIFFERENT section of the material than other batches

STUDY MATERIAL:
{state["resource_content"]}

DIFFICULTY GUIDE:
- easy: recall of key facts and straightforward definitions
- medium: application of concepts, cause-and-effect, compare-and-contrast
- hard: synthesis, edge cases, explain why something works the way it does

QUESTION TYPE RULES:

For "mcq":
- Write exactly 4 answer options
- All 4 options must be plausible to someone who partially understands the topic
- Wrong options should represent common misconceptions or close-but-wrong ideas
- Never make the correct answer obviously longer or more detailed than the others
- correct_answer must be the EXACT TEXT of one of the answer_options strings —
  not a label, not a paraphrase, the exact string copied

For "short_answer":
- The question should require 2–4 sentences to answer properly
- correct_answer is a model answer showing the key points the student must hit
- Format model answer as: "Key points: [point 1] / [point 2] / [point 3]"
  so the grader knows what to look for

COVERAGE:
- Spread questions across different concepts — don't cluster on one section
- Ensure no two questions test the same idea
- Prioritise concepts that appear repeatedly in the material or seem central to the topic

VARY THE FRAMING (don't fill one mould):
- Don't cast every question the same way. If one asks "which of the following", the next shouldn't.
  Mix how you probe — a scenario, a "why does X happen", a "what breaks if Y changes", a
  compare-two-ideas. Questions that all read alike are as forgettable as a wall of prose.
- Before returning, check your own set: do these read as {batch_count} distinct probes, or {batch_count}
  fills of one template? If they rhyme, recast them.

CRITICAL: Return a JSON array of EXACTLY {batch_count} question(s). Not more, not fewer. If {batch_count} is 1, return an array with 1 element. If {batch_count} is 2, return exactly 2 elements.
[
  {{
    "question_text": "The question",
    "question_type": "mcq",
    "answer_options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": "Option B",
    "explanation": "Brief explanation of why this is correct and why the others are wrong. 1–2 sentences.",
    "points": 1
  }},
  {{
    "question_text": "The question",
    "question_type": "short_answer",
    "correct_answer": "Key points: [first thing they must say] / [second thing] / [third thing if applicable]",
    "explanation": "What a strong answer looks like and what a weak answer misses.",
    "points": 2
  }}
]

Return ONLY valid JSON. No preamble. No text outside the array."""

    async def _generate_batch(self, state: QuestionGenState, batch_count: int, batch_index: int, total_batches: int) -> List[Dict[str, Any]]:
        """Generate a single batch of questions."""
        prompt = self._build_prompt(state, batch_count, batch_index, total_batches)
        max_tokens = min(500 + batch_count * 350, 8000)
        try:
            response = await self._call_llm(prompt, max_tokens=max_tokens)
            questions = self._parse_json_response(response)
            return questions[:batch_count]
        except Exception as e:
            logger.error(f"[QUESTION GEN] Batch {batch_index + 1} failed: {e}")
            return []

    async def _generate_questions(self, state: QuestionGenState) -> Dict[str, Any]:
        """Generate questions using parallel batches, streaming each as it completes."""
        total = state["question_count"]
        on_batch_ready = state.get("on_batch_ready")

        # Essay: single question, specialised prompt, no parallelism needed
        if state["question_types"] == ["essay"]:
            prompt = self._build_essay_prompt(state)
            try:
                response = await self._call_llm(prompt, max_tokens=2000)
                questions = self._parse_json_response(response)[:1]
            except Exception as e:
                logger.error(f"[QUESTION GEN] Essay generation failed: {e}")
                questions = []
            if on_batch_ready and questions:
                await on_batch_ready(0, 1, questions)
            return {"generated_questions": questions}

        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        batches = []
        remaining = total
        for i in range(total_batches):
            batch_count = min(BATCH_SIZE, remaining)
            batches.append((batch_count, i, total_batches))
            remaining -= batch_count

        all_questions: List[Dict[str, Any]] = []

        # Use as_completed so each batch streams to the caller as it finishes
        tasks = {
            asyncio.ensure_future(self._generate_batch(state, count, idx, total_batches)): (count, idx, total_batches)
            for count, idx, total_batches in batches
        }

        pending = set(tasks.keys())
        batch_index_counter = 0

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for fut in done:
                questions = fut.result()
                all_questions.extend(questions)
                if on_batch_ready and questions:
                    await on_batch_ready(batch_index_counter, total_batches, questions)
                batch_index_counter += 1

        logger.info(f"[QUESTION GEN] Generated {len(all_questions)} / {total} questions across {total_batches} batches")
        return {"generated_questions": all_questions}

    async def _quality_check(self, state: QuestionGenState) -> Dict[str, Any]:
        """Check quality of generated questions."""
        questions = state["generated_questions"]

        if not questions:
            return {"quality_score": 0.0}

        unique_topics = set()
        valid_questions = 0

        for q in questions:
            if "question_text" in q and "question_type" in q:
                valid_questions += 1
                unique_topics.add(q["question_text"][:30])

        coverage_score = len(unique_topics) / len(questions) if questions else 0
        validity_score = valid_questions / len(questions) if questions else 0
        quality_score = (coverage_score * 0.6) + (validity_score * 0.4)

        return {"quality_score": quality_score}

    def _should_regenerate(self, state: QuestionGenState) -> str:
        if state["quality_score"] >= 0.75:
            return "done"
        if state["retry_count"] >= self.max_retries:
            return "done"
        return "regenerate"

    async def _regenerate_with_feedback(self, state: QuestionGenState) -> Dict[str, Any]:
        return {"retry_count": state["retry_count"] + 1}

    async def _call_llm(self, prompt: str, max_tokens: int = 3000) -> str:
        return await call_llm(prompt, task="question_gen", temperature=0.6, max_tokens=max_tokens, timeout=180.0)

    def _parse_json_response(self, response: str) -> List[Dict[str, Any]]:
        """Extract and parse JSON from AI response."""
        start = response.find("[")
        end = response.rfind("]") + 1

        if start == -1 or end == 0:
            raise ValueError("No JSON array found in response")

        json_str = response[start:end]
        return json.loads(json_str)


# Singleton instance
question_generator = QuestionGenerator()
