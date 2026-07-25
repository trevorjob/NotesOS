"""
NotesOS - Pre-class Research Generator
AI-powered research generation for topics using web search + synthesis.
"""

import json
import httpx
from typing import Dict, Any, List

from app.config import settings
from app.database import AsyncSession
from app.models.resource import PreClassResearch
from app.models.course import Topic
from app.services.llm import call_llm


class ResearchGenerator:
    """Generate AI-powered pre-class research for topics."""

    def __init__(self):
        self.serper_api_key = settings.SERPER_API_KEY
        self.serper_url = "https://google.serper.dev/search"

    async def generate_research(
        self, db: AsyncSession, topic: Topic
    ) -> PreClassResearch:
        """
        Generate comprehensive pre-class research for a topic.

        Args:
            db: Database session
            topic: Topic to research

        Returns:
            PreClassResearch model instance
        """
        # Step 1: Search for relevant content
        search_query = f"{topic.title} academic overview key concepts"
        sources = await self._search_topic(search_query)

        # Step 2: Synthesize research from sources
        research_content, key_concepts = await self._synthesize_research(
            topic.title, topic.description or "", sources
        )

        # Step 3: Save to database
        research = PreClassResearch(
            topic_id=topic.id,
            research_content=research_content,
            sources=sources,
            key_concepts=key_concepts,
        )
        db.add(research)
        await db.flush()

        return research

    async def _search_topic(self, query: str) -> List[Dict[str, str]]:
        """Search the web for topic-related content using Serper."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.serper_url,
                    headers={
                        "X-API-KEY": self.serper_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "q": query,
                        "num": 10,  # Get more sources for research
                        "type": "search",
                    },
                    timeout=15.0,
                )
                response.raise_for_status()
                search_results = response.json()

                # Extract organic results
                sources = []
                for result in search_results.get("organic", [])[:8]:
                    sources.append(
                        {
                            "title": result.get("title", ""),
                            "snippet": result.get("snippet", ""),
                            "url": result.get("link", ""),
                            "source": result.get("source", ""),
                        }
                    )

                return sources

        except Exception as e:
            print(f"[RESEARCH] Error searching topic: {e}")
            return []

    async def _synthesize_research(
        self, topic_title: str, topic_description: str, sources: List[Dict[str, str]]
    ) -> tuple[str, Dict[str, Any]]:
        """
        Synthesize research content from web sources using DeepSeek.

        Returns:
            (research_content, key_concepts)
        """
        if not sources:
            return self._generate_fallback_research(topic_title, topic_description)

        # Format sources for prompt
        sources_text = "\n\n".join(
            [
                f"Source {i + 1}: {s['title']}\n{s['snippet']}\nFrom: {s.get('source', 'Unknown')}"
                for i, s in enumerate(sources)
            ]
        )

        prompt = f"""You are preparing a student to walk into class already oriented on this topic —
knowing what matters, what's contested, and what they'll be expected to engage with.

Topic: {topic_title}
{f"Description: {topic_description}" if topic_description else ""}

Web Sources:
{sources_text}

Write a research overview that does exactly that. Let the MATERIAL decide which sections exist and
how many — there is no fixed skeleton to fill in. Include background only where the topic genuinely
has relevant history; name a common misconception only where a real one exists; draw connections only
where they're real. Lead with what a student most needs to know first, and cut anything that would
only be filler — a short, sharp overview of a simple topic beats a padded one with empty headings.

Before finishing, check your own output: is every section carrying real weight, or is one there just
because overviews "usually" have it? If the latter, drop it.

Also extract 5-7 key concepts as a simple list.

Return JSON:
{{
  "research_content": "markdown-formatted research text, sections chosen to fit the material",
  "key_concepts": ["concept1", "concept2", "concept3", ...]
}}

Return ONLY valid JSON, no other text."""

        try:
            response = await self._call_llm(prompt)
            result = self._parse_json_response(response)

            return (
                result.get("research_content", ""),
                {"concepts": result.get("key_concepts", [])},
            )

        except Exception as e:
            print(f"[RESEARCH] Error synthesizing research: {e}")
            return self._generate_fallback_research(topic_title, topic_description)

    def _generate_fallback_research(
        self, topic_title: str, topic_description: str
    ) -> tuple[str, Dict[str, Any]]:
        """Generate basic research when web search fails."""
        content = f"""# {topic_title}

## Overview
{topic_description or "Research content will be generated based on class materials."}

## Preparation Guidelines
1. Review any provided reading materials
2. Note down questions you have about the topic
3. Think about how this topic connects to previous lessons

*Note: Detailed research content requires an active internet connection.*
"""
        return content, {"concepts": [topic_title]}

    async def _call_llm(self, prompt: str) -> str:
        return await call_llm(prompt, task="research", temperature=0.4, max_tokens=6000, timeout=60.0)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Extract and parse JSON from AI response."""
        start = response.find("{")
        end = response.rfind("}") + 1

        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")

        json_str = response[start:end]
        return json.loads(json_str)


# Singleton instance
research_generator = ResearchGenerator()
