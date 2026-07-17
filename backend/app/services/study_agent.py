"""
NotesOS - Study Agent Service
RAG-powered Q&A assistant with conversation history tracking.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from typing import AsyncIterator

import uuid

from app.services.rag import rag_service
from app.services.llm import call_llm, call_llm_stream
from app.models.course import Topic
from app.models.progress import AIConversation, AIMessage, MessageRole
from app.services.retrieval import subject_profiles


class StudyAgent:
    """RAG-powered study assistant with conversation memory."""

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
        # 1. Get or create conversation — one per user per topic
        if conversation_id:
            conversation = await self._get_conversation(db, conversation_id, user_id)
        else:
            conversation = await self._get_or_create_conversation(
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

        # 4. Generate answer — subject shape (STEM ⇒ work the math) is a lean orthogonal
        # to persona; only on a topic, course-wide chat stays neutral.
        subject_directive = await self._subject_directive(db, topic_id)
        answer = await self._generate_answer(
            question, context, history, personality=personality, subject_directive=subject_directive
        )

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

    async def ask_question_stream(
        self,
        db: AsyncSession,
        user_id: str,
        course_id: str,
        question: str,
        topic_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        personality: Optional[dict] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Streaming twin of ``ask_question``.

        Yields structured events for the SSE surface:
          - ``{"type": "meta", "conversation_id", "sources"}`` first,
          - ``{"type": "token", "text"}`` per delta,
          - ``{"type": "done", "conversation_id"}`` once persisted.
        The full answer is accumulated and saved exactly like the blocking path,
        so the attempt/history record is identical regardless of transport.
        """
        # 1. Get or create conversation
        if conversation_id:
            conversation = await self._get_conversation(db, conversation_id, user_id)
        else:
            conversation = await self._get_or_create_conversation(
                db, user_id, course_id, topic_id
            )

        # 2. RAG context + 3. history
        rag_result = await rag_service.query_notes(
            db=db, question=question, course_id=course_id, topic_id=topic_id, max_chunks=5,
        )
        context = rag_result["context"]
        sources = rag_result["sources"]
        history = await self._get_conversation_history(db, conversation.id)

        yield {"type": "meta", "conversation_id": str(conversation.id), "sources": sources}

        # 4. Stream the answer, accumulating for persistence
        subject_directive = await self._subject_directive(db, topic_id)
        messages = self._build_answer_messages(
            question, context, history, personality, subject_directive=subject_directive
        )
        chunks: list[str] = []
        async for delta in call_llm_stream(
            "", task="study_chat", messages=messages, temperature=0.5, max_tokens=3000, timeout=45.0
        ):
            chunks.append(delta)
            yield {"type": "token", "text": delta}

        answer = "".join(chunks)

        # 5. Persist question + answer, title on first message
        await self._save_messages(db, conversation.id, question, answer)
        if not conversation.title:
            conversation.title = await self._generate_title(question)
            await db.commit()

        yield {"type": "done", "conversation_id": str(conversation.id)}

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

    async def _get_or_create_conversation(
        self,
        db: AsyncSession,
        user_id: str,
        course_id: str,
        topic_id: Optional[str] = None,
    ) -> AIConversation:
        """Return the existing conversation for this user+topic, or create one."""
        import uuid

        if topic_id:
            result = await db.execute(
                select(AIConversation).where(
                    AIConversation.user_id == uuid.UUID(user_id),
                    AIConversation.topic_id == uuid.UUID(topic_id),
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing

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

    async def _subject_directive(self, db: AsyncSession, topic_id: Optional[str]) -> Optional[str]:
        """The subject-shape lean for the tutor — a math directive on quantitative topics.

        Branches on the topic profile's ``render`` directive (never ``if family == STEM``),
        so a later family that renders math inherits it. Returns None for course-wide chat
        (no topic) and for prose families, which need no special shaping — content leads.
        """
        if not topic_id:
            return None
        topic = await db.scalar(select(Topic).where(Topic.id == uuid.UUID(topic_id)))
        if topic is None:
            return None
        profile = subject_profiles.profile_for(topic.subject_family)
        if profile.render != subject_profiles.RENDER_MATH:
            return None
        return (
            "This is a quantitative topic. Render all mathematics as LaTeX ($…$ inline, "
            "$$…$$ display). When the student asks about a problem or procedure, WORK THE "
            "EXAMPLE step by step — show the actual steps and keep derivations intact, "
            "rather than describing the method in prose."
        )

    def _build_answer_messages(
        self, question: str, context: str, history: list,
        personality: Optional[dict] = None, subject_directive: Optional[str] = None,
    ) -> list:
        """Assemble the chat messages (system + history + user) for an answer.

        Shared by the blocking and streaming paths so prompt construction lives in
        one place.
        """
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

        if subject_directive:
            # Subject shape is a separate axis from persona above — a visual humanities
            # student and a concise STEM student are both possible.
            system_prompt += f"\n\n        SUBJECT SHAPE (independent of the style above):\n        {subject_directive}"

        user_prompt = f"""Here are the notes for this topic:

        {context}

        ---

        Student's question: {question}"""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})
        return messages

    async def _generate_answer(
        self, question: str, context: str, history: list,
        personality: Optional[dict] = None, subject_directive: Optional[str] = None,
    ) -> str:
        """Generate a full answer (non-streaming) with RAG context + personality."""
        messages = self._build_answer_messages(
            question, context, history, personality, subject_directive=subject_directive
        )
        return await call_llm("", task="study_chat", messages=messages, temperature=0.5, max_tokens=3000, timeout=45.0)

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
