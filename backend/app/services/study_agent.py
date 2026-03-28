"""
NotesOS - Study Agent Service
RAG-powered Q&A assistant with conversation history tracking.
"""

import httpx
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.services.rag import rag_service
from app.models.progress import AIConversation, AIMessage, MessageRole


class StudyAgent:
    """RAG-powered study assistant with conversation memory."""

    def __init__(self):
        self.deepseek_api_key = settings.DEEPSEEK_API_KEY
        self.deepseek_base = "https://api.deepseek.com/v1"

    async def ask_question(
        self,
        db: AsyncSession,
        user_id: str,
        course_id: str,
        question: str,
        topic_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        personality: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Answer a study question using RAG + AI.

        Args:
            db: Database session
            user_id: User asking the question
            course_id: Course context
            question: User's question
            topic_id: Optional topic filter
            conversation_id: Optional existing conversation to continue

        Returns:
            dict with:
                - answer: AI-generated answer
                - sources: List of source resources
                - conversation_id: Conversation ID for follow-ups
        """
        # 1. Get or create conversation
        if conversation_id:
            conversation = await self._get_conversation(db, conversation_id, user_id)
        else:
            conversation = await self._create_conversation(
                db, user_id, course_id, topic_id
            )

        # 2. Retrieve relevant context via RAG
        rag_result = await rag_service.query_notes(
            db=db,
            question=question,
            course_id=course_id,
            topic_id=topic_id,
            max_chunks=5,
        )

        context = rag_result["context"]
        sources = rag_result["sources"]

        # 3. Get conversation history
        history = await self._get_conversation_history(db, conversation.id)

        # 4. Generate answer with DeepSeek
        answer = await self._generate_answer(question, context, history, personality=personality)

        # 5. Save messages to conversation
        await self._save_messages(db, conversation.id, question, answer)

        # 6. Update conversation title if first message
        if not conversation.title:
            conversation.title = await self._generate_title(question)
            await db.commit()

        return {
            "answer": answer,
            "sources": sources,
            "conversation_id": str(conversation.id),
        }

    async def _get_conversation(
        self, db: AsyncSession, conversation_id: str, user_id: str
    ) -> AIConversation:
        """Fetch existing conversation."""
        import uuid

        query = select(AIConversation).where(
            AIConversation.id == uuid.UUID(conversation_id),
            AIConversation.user_id == uuid.UUID(user_id),
        )
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise ValueError("Conversation not found or access denied")

        return conversation

    async def _create_conversation(
        self,
        db: AsyncSession,
        user_id: str,
        course_id: str,
        topic_id: Optional[str] = None,
    ) -> AIConversation:
        """Create new conversation."""
        import uuid

        conversation = AIConversation(
            user_id=uuid.UUID(user_id),
            course_id=uuid.UUID(course_id),
            topic_id=uuid.UUID(topic_id) if topic_id else None,
        )
        db.add(conversation)
        await db.flush()

        return conversation

    async def _get_conversation_history(
        self, db: AsyncSession, conversation_id
    ) -> list:
        """Get conversation message history."""
        query = (
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.asc())
        )
        result = await db.execute(query)
        messages = result.scalars().all()

        # Format for DeepSeek API
        history = []
        for msg in messages[-6:]:  # Last 3 exchanges (6 messages)
            history.append({"role": msg.role.value, "content": msg.content})

        return history

    async def _generate_answer(self, question: str, context: str, history: list, personality: Optional[dict] = None) -> str:
        """Generate answer using DeepSeek with RAG context and user personality."""
        tone = (personality or {}).get("tone", "encouraging")
        emoji_usage = (personality or {}).get("emoji_usage", "moderate")
        explanation_style = (personality or {}).get("explanation_style", "detailed")

        tone_desc = {
            "encouraging": (
                "warm and genuinely invested in the student's understanding. "
                "Celebrate when they ask good questions. If they're struggling, "
                "acknowledge it and break things down further. Never condescending."
            ),
            "direct": (
                "efficient and no-nonsense. Skip preamble, get to the answer. "
                "No 'great question!', no filler phrases. Respect that the student "
                "wants the information fast."
            ),
            "humorous": (
                "sharp and occasionally funny — use wit to make dense material "
                "more memorable, but never at the expense of clarity. "
                "A well-placed analogy beats a joke every time."
            ),
        }.get(tone, "friendly and clear")

        emoji_desc = {
            "none": "Do not use any emojis at all.",
            "moderate": (
                "Use 1–2 emojis per response maximum, only where they genuinely "
                "add meaning or warmth — not as decoration."
            ),
            "heavy": (
                "Use emojis naturally throughout, the way a student texting a "
                "classmate would."
            ),
        }.get(emoji_usage, "Use emojis sparingly.")

        style_desc = {
            "concise": (
                "Lead with the direct answer in 1–2 sentences. Only add context "
                "if the question requires it. Prefer short paragraphs over lists "
                "unless listing is genuinely the clearest format."
            ),
            "detailed": (
                "Give the full picture — explain not just what but why. "
                "Use examples where they help. Break complex ideas into steps. "
                "But don't pad — every sentence should earn its place."
            ),
            "visual": (
                "Think in examples and analogies first. Before explaining a concept "
                "abstractly, ground it in something concrete the student can picture. "
                "Use step-by-step breakdowns for processes. Comparisons are your "
                "best tool."
            ),
        }.get(explanation_style, "Give thorough explanations.")

        system_prompt = f"""You are the student's personal study partner for this course — 
        someone who has read all the same notes and is there to help them actually 
        understand the material, not just recite it back.

        HOW YOU COMMUNICATE:
        - Tone: {tone_desc}
        - Emojis: {emoji_desc}
        - Style: {style_desc}

        HOW YOU ANSWER:
        - Base every answer on the course notes provided. If the notes cover it, 
        use them as your primary source.
        - If the notes only partially cover the question, answer what you can from 
        the notes and clearly flag what's coming from general knowledge: 
        "Your notes don't cover this directly, but generally..."
        - If the question is completely outside the notes, say so plainly and 
        offer a general answer if it's helpful — don't refuse, don't pretend 
        the notes say something they don't.
        - If a question is vague, answer the most likely interpretation and 
        offer to go deeper on any part.
        - Never use phrases like "Based on the provided context..." or 
        "According to the course notes..." — just answer naturally, 
        the way a study partner would.
        - Match your response length to the question. A factual question 
        gets a short answer. A conceptual question gets a fuller explanation.
        - If the student seems to have a misconception in their question, 
        gently correct it before answering."""

        user_prompt = f"""Here are the notes for this topic:

        {context}

        ---

        Student's question: {question}"""
        # Build messages array with history
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)  # Add conversation history
        messages.append({"role": "user", "content": user_prompt})

        # Call DeepSeek API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.deepseek_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": messages,
                    "temperature": 0.5,
                    "max_tokens": 1500,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _save_messages(
        self, db: AsyncSession, conversation_id, question: str, answer: str
    ):
        """Save user question and AI answer to conversation."""
        user_message = AIMessage(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=question,
        )
        assistant_message = AIMessage(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=answer,
        )

        db.add(user_message)
        db.add(assistant_message)
        await db.commit()

    async def _generate_title(self, first_question: str) -> str:
        """Generate a short title for the conversation."""
        # Simple heuristic: use first 50 chars of question
        title = first_question[:50]
        if len(first_question) > 50:
            title += "..."
        return title


# Singleton instance
study_agent = StudyAgent()
