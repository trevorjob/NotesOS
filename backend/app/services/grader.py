"""
NotesOS - Grader Service
AI-powered answer grading with voice-awareness and encouragement.
"""

import json
import random
import httpx
from typing import Dict, Any

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
        is_voice: bool = False,
    ) -> Dict[str, Any]:
        """
        Grade a student answer with AI + provide encouragement.

        Args:
            question: The question asked
            expected_answer: Model/correct answer
            student_answer: Student's submitted answer
            is_voice: True if answer was transcribed from voice

        Returns:
            dict with:
                - score: 0-100
                - feedback: Detailed feedback
                - encouragement: Motivational message with emoji
                - key_points_covered: List of points student got right
                - key_points_missed: List of points student missed
        """
        # 1. Build grading prompt
        prompt = self._build_grading_prompt(
            question, expected_answer, student_answer, is_voice
        )

        # 2. Get AI grading
        response = await self._call_deepseek(prompt)

        try:
            grading_result = self._parse_json_response(response)
        except Exception as e:
            print(f"[GRADER] Error parsing grading result: {e}")
            # Fallback grading
            grading_result = {
                "score": 50,
                "key_points_covered": [],
                "key_points_missed": [],
                "feedback": "Could not grade automatically. Please review manually.",
            }

        # 3. Add encouragement based on score
        score = grading_result.get("score", 50)
        encouragement = self._generate_encouragement(score)

        return {
            "score": score,
            "feedback": grading_result.get("feedback", ""),
            "encouragement": encouragement,
            "key_points_covered": grading_result.get("key_points_covered", []),
            "key_points_missed": grading_result.get("key_points_missed", []),
        }

    def _build_grading_prompt(
        self, question: str, expected: str, student: str, is_voice: bool
    ) -> str:
        """Build the grading prompt."""
        voice_note = ""
        if is_voice:
            voice_note = """
IMPORTANT: This is transcribed speech. Ignore filler words, false starts, and minor grammatical errors. 
Focus ONLY on concept understanding and content accuracy.
"""

        return f"""Grade this student answer using the rubric below.

Question: {question}

Expected Answer: {expected}

Student Answer: {student}
{voice_note}
Grading Rubric:
- Concept understanding: 70%
- Key points coverage: 20%
- Examples/support: 10%

Return JSON:
{{
  "score": 0-100,
  "key_points_covered": ["point 1", "point 2", ...],
  "key_points_missed": ["point 3", "point 4", ...],
  "feedback": "Detailed explanation of grade..."
}}

Return ONLY valid JSON, no other text."""

    def _generate_encouragement(self, score: float) -> str:
        """Generate score-based encouragement with emojis."""
        if score >= 90:
            return random.choice(
                [
                    "🔥 Absolutely crushing it!",
                    "💯 You really know your stuff!",
                    "⭐ This is excellent work!",
                    "🎯 Perfect! You nailed it!",
                ]
            )
        elif score >= 70:
            return random.choice(
                [
                    "💪 Solid answer! Just a few tweaks needed.",
                    "👍 You're on the right track!",
                    "📈 Good progress! Keep it up!",
                    "✨ Nice work! You've got the main idea.",
                ]
            )
        elif score >= 50:
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
