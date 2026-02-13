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
        answer = await self._generate_answer(question, context, history)

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

    async def _generate_answer(self, question: str, context: str, history: list) -> str:
        """Generate answer using DeepSeek with RAG context."""
        system_prompt = """You are a friendly, knowledgeable study assistant helping students learn course material.

Your job is to:
1. Answer questions clearly and accurately based on the provided course notes
2. Explain concepts in an easy-to-understand way
3. Encourage students and keep them motivated
4. If the notes don't contain the answer, say so honestly

Be conversational, supportive, and use examples when helpful."""

        user_prompt = f"""Question: {question}

Course Notes Context:
{context}

Please provide a clear, helpful answer based on the course notes above."""

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
