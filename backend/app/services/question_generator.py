"""
NotesOS - Question Generator Service
LangGraph-based test question generation with quality loop.
"""

import json
import httpx
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.resource import Resource
from app.models.test import Test, TestQuestion, TestType, QuestionType


class QuestionGenState(TypedDict):
    """State for question generation workflow."""

    test_id: str
    topic_ids: List[str]
    resource_content: str
    question_count: int
    difficulty: str
    question_types: List[str]
    generated_questions: List[Dict[str, Any]]
    quality_score: float
    retry_count: int


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
        user_id: str,  # Added user_id
        topic_ids: List[str],
        question_count: int = 10,
        difficulty: str = "medium",
        question_types: List[str] = None,
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
            title=f"Practice Test - {difficulty.capitalize()}",
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

    async def _generate_questions(self, state: QuestionGenState) -> Dict[str, Any]:
        """Generate questions using DeepSeek."""
        prompt = f"""Generate {state["question_count"]} practice test questions based on this course content.

Difficulty: {state["difficulty"]}
Question Types: {", ".join(state["question_types"])}

Content:
{state["resource_content"][:4000]}

Requirements:
1. Ensure all major concepts are covered
2. Create diverse questions (don't repeat topics)
3. For MCQ: provide 4 answer options with exactly one correct answer
4. For short answer: provide a model answer (2-3 sentences)
5. Make questions clear and unambiguous

Return JSON array of questions in this format:
[
  {{
    "question_text": "What is...?",
    "question_type": "mcq",
    "correct_answer": "Option B",
    "answer_options": ["Option A", "Option B", "Option C", "Option D"],
    "points": 1
  }},
  {{
    "question_text": "Explain...",
    "question_type": "short_answer",
    "correct_answer": "Model answer here...",
    "points": 2
  }}
]

Return ONLY valid JSON, no other text."""

        response = await self._call_deepseek(prompt)

        try:
            questions = self._parse_json_response(response)
            return {"generated_questions": questions}
        except Exception as e:
            print(f"[QUESTION GEN] Error parsing questions: {e}")
            return {"generated_questions": []}

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

    async def _call_deepseek(self, prompt: str) -> str:
        """Make API call to DeepSeek."""
        async with httpx.AsyncClient() as client:
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
                    "max_tokens": 3000,
                },
                timeout=45.0,
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
