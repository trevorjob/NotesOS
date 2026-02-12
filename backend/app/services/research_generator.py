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


class ResearchGenerator:
    """Generate AI-powered pre-class research for topics."""

    def __init__(self):
        self.deepseek_api_key = settings.DEEPSEEK_API_KEY
        self.serper_api_key = settings.SERPER_API_KEY
        self.deepseek_base = "https://api.deepseek.com/v1"
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

        prompt = f"""Generate comprehensive pre-class research for this topic.

Topic: {topic_title}
{f"Description: {topic_description}" if topic_description else ""}

Web Sources:
{sources_text}

Create a structured research overview that helps students prepare for class. Include:
1. **Core Concepts** - Key ideas and definitions
2. **Historical Context** - Important background (if relevant)
3. **Key Points** - Main learning objectives
4. **Common Misconceptions** - What students often get wrong
5. **Connections** - How this relates to other topics

Also extract 5-7 key concepts as a simple list.

Return JSON:
{{
  "research_content": "markdown-formatted research text with sections",
  "key_concepts": ["concept1", "concept2", "concept3", ...]
}}

Return ONLY valid JSON, no other text."""

        try:
            response = await self._call_deepseek(prompt)
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
                    "temperature": 0.4,  # Slightly higher for creative synthesis
                    "max_tokens": 3000,
                },
                timeout=45.0,  # Longer timeout for research
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
research_generator = ResearchGenerator()
