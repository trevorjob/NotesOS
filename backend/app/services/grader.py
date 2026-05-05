"""
NotesOS - Grader Service
AI-powered answer grading with voice-awareness and encouragement.
"""

import json
import random
import httpx
from typing import Dict, Any, Optional

from app.config import settings


class Grader:
    """AI grader with voice-awareness and motivational feedback."""

    def __init__(self):
        self.deepseek_api_key = settings.DEEPSEEK_API_KEY
        self.deepseek_base = "https://api.deepseek.com/v1"

    async def grade_answer(
        self,
        question: str,
        expected_answer: str,
        student_answer: str,
        question_type: str,
        topic_name: str,
        is_voice: bool = False,
        
        
        personality: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Grade a student answer with AI + provide encouragement.

        Args:
            question: The question asked
            expected_answer: Model/correct answer
            student_answer: Student's submitted answer
            is_voice: True if answer was transcribed from voice
            question_type: Type of question (mcq, short_answer, essay)
            topic_name: Topic name for encouragement context
            personality: User personality settings dict

        Returns:
            dict with:
                - score: 0-10
                - feedback: Detailed feedback string
                - encouragement: Motivational message
                - key_points_covered: List of points student got right
                - key_points_missed: List of points student missed
        """
        # 1. Build grading prompt
        prompt = self._build_grading_prompt(
            question, expected_answer, student_answer, question_type, is_voice
        )

        # 2. Get AI grading
        response = await self._call_deepseek(prompt)

        try:
            grading_result = self._parse_json_response(response)
        except Exception as e:
            print(f"[GRADER] Error parsing grading result: {e}")
            grading_result = {
                "score": 5,
                "verdict": "partial",
                "key_points_covered": [],
                "key_points_missed": [],
                "misconception": None,
                "feedback": {
                    "what_you_got_right": None,
                    "what_to_fix": "Could not grade automatically. Please review manually.",
                    "one_thing_to_remember": None,
                },
            }

        score = grading_result.get("score", 5)
        verdict = grading_result.get("verdict", "")
        misconception = grading_result.get("misconception")

        # 3. Flatten nested feedback dict to string
        fb = grading_result.get("feedback", {})
        if isinstance(fb, dict):
            parts = [p for p in [
                fb.get("what_you_got_right"),
                fb.get("what_to_fix"),
                f"Remember: {fb['one_thing_to_remember']}" if fb.get("one_thing_to_remember") else None,
            ] if p]
            feedback_str = " ".join(parts)
        else:
            feedback_str = str(fb) if fb else ""

        # 4. Generate AI encouragement
        encouragement_prompt = self._build_encouragement_prompt(
            score=score,
            verdict=verdict,
            what_got_right=fb.get("what_you_got_right") if isinstance(fb, dict) else None,
            what_to_fix=fb.get("what_to_fix") if isinstance(fb, dict) else None,
            misconception=misconception,
            topic_name=topic_name,
            is_voice=is_voice,
            personality=personality,
        )
        try:
            encouragement = await self._call_deepseek(encouragement_prompt)
            encouragement = encouragement.strip()
        except Exception:
            encouragement = self._generate_encouragement(score)

        return {
            "score": score,
            "feedback": feedback_str,
            "encouragement": encouragement,
            "key_points_covered": grading_result.get("key_points_covered", []),
            "key_points_missed": grading_result.get("key_points_missed", []),
        }

    def _build_grading_prompt(
        self, question: str, expected: str, student: str, 
        question_type: str, is_voice: bool
    ) -> str:

        voice_guidance = ""
        if is_voice:
            voice_guidance = """
    VOICE ANSWER — ADJUST YOUR GRADING:
    This answer was transcribed from spoken audio. Apply these adjustments:
    - Ignore filler words (um, uh, like, you know, kind of)
    - Ignore false starts and self-corrections ("wait, no, I mean...")
    - Ignore informal grammar and sentence fragments
    - Do not penalise for missing technical spelling of terms if the 
    pronunciation is clearly correct
    - DO penalise for wrong concepts, missing key ideas, or clear 
    misunderstandings — those are content errors, not speech errors
    - If the student clearly knew something but struggled to articulate it, 
    give them the benefit of the doubt on that point
    """

        return f"""You are grading a student's answer. Your job is to be fair, 
    specific, and genuinely useful — not harsh, not generous. 
    A grade that doesn't reflect reality helps no one.

    QUESTION:
    {question}

    EXPECTED ANSWER (model answer — key points the student should cover):
    {expected}

    STUDENT'S ANSWER:
    {student}
    {voice_guidance}

    ═══════════════════════════════════════
    GRADING CRITERIA — read carefully:
    ═══════════════════════════════════════

    CONCEPT UNDERSTANDING (primary — worth most of the grade):
    Does the student actually understand what's happening, or are they 
    reciting words without meaning? 
    - Full marks: demonstrates clear understanding, could explain it 
    differently if asked
    - Partial: has the right idea but is missing the mechanism or reason
    - Low: uses correct vocabulary but shows no understanding of what 
    it means
    - Zero: fundamentally misunderstands the concept

    KEY POINTS COVERAGE (secondary):
    How many of the key points from the expected answer did they hit?
    Missing one non-central point is minor. Missing the core claim is major.

    EVIDENCE AND EXAMPLES (supporting):
    Did they use examples, evidence, or reasoning to support their answer?
    Only relevant for short answer questions — do not penalise MCQ for this.

    WHAT TO IGNORE:
    - Spelling and grammar (unless so bad it changes the meaning)
    - Points the student made that are correct but weren't in the expected 
    answer — reward accurate knowledge even if unexpected
    - Phrasing that differs from the model answer — grade the idea, 
    not the wording

    ═══════════════════════════════════════
    SCORING GUIDE:
    ═══════════════════════════════════════
    9–10: Covers all key points, demonstrates clear understanding, 
        could teach this concept to someone else
    7–8:  Gets the main idea right, hits most key points, 
        minor gaps or imprecision
    5–6:  Partially correct — right direction but missing something 
        important, or correct points without demonstrated understanding
    3–4:  Some relevant knowledge but significant gaps or 
        a meaningful misconception present
    1–2:  Minimal relevant content, mostly off-track
    0:    No relevant content or completely wrong

    Return JSON:
    {{
    "score": <integer 0-10>,
    "verdict": "<one of: correct | mostly_correct | partial | mostly_wrong | wrong>",
    "key_points_covered": [
        "<exact point from expected answer that student demonstrated>"
    ],
    "key_points_missed": [
        "<exact point from expected answer that student missed or got wrong>"
    ],
    "misconception": "<if the student has a specific wrong belief, name it clearly in one sentence — otherwise null>",
    "feedback": {{
        "what_you_got_right": "<1–2 sentences. Specific — name what they got right, not just 'good job'. If nothing is right, null.>",
        "what_to_fix": "<1–3 sentences. Tell them exactly what they got wrong or missed and why it matters. Be direct, not harsh. If nothing to fix, null.>",
        "one_thing_to_remember": "<The single most important thing they should take away from this question, whether they got it right or wrong. 1 sentence.>"
    }}
    }}

    Return ONLY valid JSON. No preamble."""

    def _build_encouragement_prompt(
        self, score: float, verdict: str, 
        what_got_right: str, what_to_fix: str,
        misconception: str, topic_name: str,
        is_voice: bool, personality: dict
    ) -> str:

        tone = (personality or {}).get("tone", "encouraging")
        
        tone_desc = {
            "encouraging": "warm and genuinely invested. Acknowledge effort, be specific about what's good.",
            "direct": "straight to the point. Skip the praise if the answer was wrong. Just tell them what to do next.",
            "humorous": "light but not dismissive. A touch of wit is fine; false positivity isn't.",
        }.get(tone, "warm and clear")

        score_context = (
            "They nailed it." if score >= 9 else
            "They got the main idea but missed something." if score >= 7 else
            "They're partially there but have a meaningful gap." if score >= 5 else
            "They're significantly off track." if score >= 3 else
            "They didn't get it."
        )

        misconception_note = (
            f"They have a specific misconception: {misconception}. "
            f"Acknowledge this carefully — don't make them feel stupid, "
            f"but be clear they have something to unlearn, not just learn."
            if misconception else
            "No specific misconception detected."
        )

        return f"""Write a 2–4 sentence response to a student who just answered 
    a quiz question on {topic_name}.

    THEIR RESULT:
    - Score: {score}/10
    - Situation: {score_context}
    - What they got right: {what_got_right or 'Nothing significant.'}
    - What they missed or got wrong: {what_to_fix or 'Nothing — they got it.'}
    - {misconception_note}
    - Answer was spoken aloud: {is_voice}

    YOUR TONE: {tone_desc}

    RULES:
    - Be specific — reference what they actually got right or wrong, 
    not generic praise or generic criticism
    - Do not repeat the feedback they already received — this message 
    comes after the detailed breakdown, so don't re-explain the gap
    - If they got it right, tell them something that makes the win feel real
    - If they got it wrong, end on what to do next — not on the failure
    - If they have a misconception, treat it as something to fix, 
    not something to feel bad about
    - 2–4 sentences maximum. This is a moment, not a lecture.
    - {"Use 1 emoji maximum, only if it fits naturally." if (personality or {}).get("emoji_usage") != "none" else "No emojis."}

    Return only the message text. No JSON. No label."""
    def _generate_encouragement(self, score: float) -> str:
        """Generate score-based encouragement with emojis."""
        if score >= 9:
            return random.choice(
                [
                    "🔥 Absolutely crushing it!",
                    "💯 You really know your stuff!",
                    "⭐ This is excellent work!",
                    "🎯 Perfect! You nailed it!",
                ]
            )
        elif score >= 7:
            return random.choice(
                [
                    "💪 Solid answer! Just a few tweaks needed.",
                    "👍 You're on the right track!",
                    "📈 Good progress! Keep it up!",
                    "✨ Nice work! You've got the main idea.",
                ]
            )
        elif score >= 5:
            return random.choice(
                [
                    "🌱 You're getting there! Let's clarify a few things.",
                    "💡 Good effort! Here's what to focus on...",
                    "📚 Not bad! You've got the basics, now let's deepen your understanding.",
                    "🎓 You're making progress! Review these key points.",
                ]
            )
        else:
            return random.choice(
                [
                    "🤔 This is tricky stuff! Let's break it down together.",
                    "💭 No worries, this concept takes time. Want me to explain it differently?",
                    "🔄 Let's try another approach to this topic.",
                    "🌟 Don't give up! Learning takes practice.",
                ]
            )

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
                    "temperature": 0.3,  # More deterministic for grading
                    "max_tokens": 1000,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Extract and parse JSON from AI response."""
        start = response.find("{")
        end = response.rfind("}") + 1

        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")

        json_str = response[start:end]
        return json.loads(json_str)


# Singleton instance
grader = Grader()
