"""
NotesOS - Question Generator Service
LangGraph-based test question generation with quality loop.
"""

import asyncio
import json
import logging
import httpx
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

from app.config import settings
from app.models.resource import Resource
from app.models.test import Test, TestQuestion, TestType, QuestionType


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


BATCH_SIZE = 12  # Questions per parallel API call


class QuestionGenerator:
    """LangGraph-based question generator with quality loop."""

    def __init__(self):
        self.deepseek_api_key = settings.DEEPSEEK_API_KEY
        self.deepseek_base = "https://api.deepseek.com/v1"
        self.max_retries = 2

    async def generate_test(
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
        """
        Generate a complete test with questions.

        Args:
            db: Database session
            course_id: Course ID
            user_id: ID of the user creating the test
            topic_ids: List of topic IDs to cover
            question_count: Number of questions to generate
            difficulty: easy/medium/hard
            question_types: List of question types (mcq, short_answer, essay)

        Returns:
            Test model instance with questions
        """
        if question_types is None:
            question_types = ["mcq", "short_answer"]

        # 1. Gather resource content for topics
        resource_content = await self._gather_resources(db, topic_ids)

        # 2. Create test record
        import uuid

        test = Test(
            course_id=uuid.UUID(course_id),
            created_by=uuid.UUID(user_id),
            title=title or f"Practice Test - {difficulty.capitalize()}",
            test_type=TestType.PRACTICE,
            topics=topic_ids,
            question_count=question_count,
        )
        db.add(test)
        await db.flush()

        # 3. Run LangGraph workflow
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
        }

        result = await app.ainvoke(initial_state)

        # 4. Save questions to database
        for idx, q_data in enumerate(result["generated_questions"]):
            question = TestQuestion(
                test_id=test.id,
                question_text=q_data["question_text"],
                question_type=QuestionType[q_data["question_type"].upper()],
                correct_answer=q_data.get("correct_answer"),
                answer_options=q_data.get("answer_options"),
                points=q_data.get("points", 1),
                order_index=idx,
            )
            db.add(question)

        await db.commit()
        return test

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow."""
        workflow = StateGraph(QuestionGenState)

        # Add nodes
        workflow.add_node("generate", self._generate_questions)
        workflow.add_node("quality_check", self._quality_check)
        workflow.add_node("regenerate", self._regenerate_with_feedback)

        # Define edges
        workflow.set_entry_point("generate")
        workflow.add_edge("generate", "quality_check")
        workflow.add_conditional_edges(
            "quality_check",
            self._should_regenerate,
            {
                "done": END,  # Quality good or max retries
                "regenerate": "regenerate",  # Quality poor, retry
            },
        )
        workflow.add_edge("regenerate", "generate")

        return workflow

    async def _gather_resources(self, db: AsyncSession, topic_ids: List[str]) -> str:
        """Gather all resource content for topics."""
        import uuid

        topic_uuids = [uuid.UUID(tid) for tid in topic_ids]

        query = select(Resource).where(Resource.topic_id.in_(topic_uuids))
        result = await db.execute(query)
        resources = result.scalars().all()

        # Combine all content
        content_parts = []
        for resource in resources:
            if resource.content:
                content_parts.append(f"=== {resource.title} ===\n{resource.content}")

        return "\n\n".join(content_parts)

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
        # ~350 tokens per question (question + options + explanation + JSON overhead) + 500 base
        max_tokens = min(500 + batch_count * 350, 8000)
        try:
            response = await self._call_deepseek(prompt, max_tokens=max_tokens)
            questions = self._parse_json_response(response)
            # Trim to exact count in case the model over-generates
            return questions[:batch_count]
        except Exception as e:
            logger.error(f"[QUESTION GEN] Batch {batch_index + 1} failed: {e}")
            return []

    async def _generate_questions(self, state: QuestionGenState) -> Dict[str, Any]:
        """Generate questions using parallel batches."""
        total = state["question_count"]
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        # Build batch sizes (last batch may be smaller)
        batches = []
        remaining = total
        for i in range(total_batches):
            batch_count = min(BATCH_SIZE, remaining)
            batches.append((batch_count, i, total_batches))
            remaining -= batch_count

        results = await asyncio.gather(*[
            self._generate_batch(state, count, idx, total_batches)
            for count, idx, total in batches
        ])

        all_questions = [q for batch in results for q in batch]
        logger.info(f"[QUESTION GEN] Generated {len(all_questions)} / {total} questions across {total_batches} batches")
        return {"generated_questions": all_questions}

    async def _quality_check(self, state: QuestionGenState) -> Dict[str, Any]:
        """Check quality of generated questions."""
        questions = state["generated_questions"]

        if not questions:
            return {"quality_score": 0.0}

        # Quality metrics
        unique_topics = set()
        valid_questions = 0

        for q in questions:
            # Check if question has required fields
            if "question_text" in q and "question_type" in q:
                valid_questions += 1
                unique_topics.add(q["question_text"][:30])  # Simple topic check

        # Calculate quality score
        coverage_score = len(unique_topics) / len(questions) if questions else 0
        validity_score = valid_questions / len(questions) if questions else 0

        quality_score = (coverage_score * 0.6) + (validity_score * 0.4)

        return {"quality_score": quality_score}

    def _should_regenerate(self, state: QuestionGenState) -> str:
        """Decide if we should regenerate questions."""
        if state["quality_score"] >= 0.75:
            return "done"  # Quality good enough

        if state["retry_count"] >= self.max_retries:
            return "done"  # Max retries reached, accept current

        return "regenerate"  # Try again

    async def _regenerate_with_feedback(
        self, state: QuestionGenState
    ) -> Dict[str, Any]:
        """Provide feedback and increment retry counter."""
        return {"retry_count": state["retry_count"] + 1}

    async def _call_deepseek(self, prompt: str, max_tokens: int = 3000) -> str:
        """Make API call to DeepSeek."""
        timeout = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.deepseek_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.6,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

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
