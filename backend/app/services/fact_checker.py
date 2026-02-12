"""
NotesOS - Fact Checker Service
LangGraph-based multi-step agent for verifying factual claims in resources.
"""

import json
import httpx
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from app.config import settings


class FactCheckState(TypedDict):
    """State for the fact-checking workflow."""

    resource_id: str
    content: str
    claims: List[Dict[str, Any]]
    current_claim_index: int
    verifications: List[Dict[str, Any]]
    final_report: Dict[str, Any]


class FactChecker:
    """LangGraph-based fact checker using DeepSeek + Serper."""

    def __init__(self):
        self.deepseek_api_key = settings.DEEPSEEK_API_KEY
        self.serper_api_key = settings.SERPER_API_KEY
        self.deepseek_base = "https://api.deepseek.com/v1"
        self.serper_url = "https://google.serper.dev/search"

    async def check_facts(self, resource_id: str, content: str) -> Dict[str, Any]:
        """
        Run the complete fact-checking workflow.

        Args:
            resource_id: Resource UUID
            content: Text content to fact-check

        Returns:
            Final report with all verifications
        """
        workflow = self._build_graph()
        app = workflow.compile()

        initial_state = {
            "resource_id": resource_id,
            "content": content,
            "claims": [],
            "current_claim_index": 0,
            "verifications": [],
            "final_report": {},
        }

        result = await app.ainvoke(initial_state)
        return result["final_report"]

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(FactCheckState)

        # Add nodes
        workflow.add_node("extract", self._extract_claims)
        workflow.add_node("search", self._search_claim)
        workflow.add_node("verify", self._verify_claim)
        workflow.add_node("report", self._generate_report)

        # Define edges
        workflow.set_entry_point("extract")
        workflow.add_edge("extract", "search")
        workflow.add_edge("search", "verify")
        workflow.add_conditional_edges(
            "verify",
            self._should_continue,
            {
                "search": "search",  # More claims? Loop back
                "report": "report",  # Done? Generate report
            },
        )
        workflow.add_edge("report", END)

        return workflow

    async def _extract_claims(self, state: FactCheckState) -> Dict[str, Any]:
        """Step 1: Extract factual claims from content using DeepSeek."""
        prompt = f"""Extract factual claims from this text that can be verified. 
        
Focus on:
- Dates and historical events
- Statistics and numbers
- Definitions and concepts
- Cause-and-effect relationships

Text:
\"\"\"{state["content"][:3000]}\"\"\"

Return JSON array of claims:
[
  {{"claim_text": "Napoleon died in 1821", "importance": "high"}},
  {{"claim_text": "Paris is the capital of France", "importance": "medium"}}
]

Return ONLY the JSON array, no other text."""

        response = await self._call_deepseek(prompt)

        try:
            # Extract JSON from response
            claims = self._parse_json_response(response)
            return {"claims": claims if claims else []}
        except Exception as e:
            print(f"[FACT CHECK] Error extracting claims: {e}")
            return {"claims": []}

    async def _search_claim(self, state: FactCheckState) -> Dict[str, Any]:
        """Step 2: Search the web for the current claim using Serper."""
        if state["current_claim_index"] >= len(state["claims"]):
            return {}

        claim = state["claims"][state["current_claim_index"]]
        claim_text = claim["claim_text"]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.serper_url,
                    headers={
                        "X-API-KEY": self.serper_api_key,
                        "Content-Type": "application/json",
                    },
                    json={"q": claim_text, "num": 5},
                    timeout=10.0,
                )
                response.raise_for_status()
                search_results = response.json()

                # Extract organic results
                sources = []
                for result in search_results.get("organic", [])[:3]:
                    sources.append(
                        {
                            "title": result.get("title", ""),
                            "snippet": result.get("snippet", ""),
                            "url": result.get("link", ""),
                        }
                    )

                return {"search_results": sources}

        except Exception as e:
            print(f"[FACT CHECK] Error searching claim: {e}")
            return {"search_results": []}

    async def _verify_claim(self, state: FactCheckState) -> Dict[str, Any]:
        """Step 3: Verify the claim against search results using DeepSeek."""
        if state["current_claim_index"] >= len(state["claims"]):
            return {}

        claim = state["claims"][state["current_claim_index"]]
        sources = state.get("search_results", [])

        sources_text = "\n\n".join(
            [
                f"Source {i + 1}: {s['title']}\n{s['snippet']}\nURL: {s['url']}"
                for i, s in enumerate(sources)
            ]
        )

        prompt = f"""Verify this claim against the provided sources.

Claim: "{claim["claim_text"]}"

Sources:
{sources_text}

Return JSON:
{{
  "status": "verified" | "disputed" | "unverified",
  "confidence": 0.0-1.0,
  "explanation": "brief explanation of why",
  "sources_used": [0, 1, 2]  // indices of sources that support this
}}

Return ONLY valid JSON, no other text."""

        response = await self._call_deepseek(prompt)

        try:
            verification = self._parse_json_response(response)
            verification["claim_text"] = claim["claim_text"]
            verification["sources"] = [
                sources[i]
                for i in verification.get("sources_used", [])
                if i < len(sources)
            ]

            # Add to verifications list
            new_verifications = state.get("verifications", []) + [verification]

            return {
                "verifications": new_verifications,
                "current_claim_index": state["current_claim_index"] + 1,
            }
        except Exception as e:
            print(f"[FACT CHECK] Error verifying claim: {e}")
            return {"current_claim_index": state["current_claim_index"] + 1}

    def _should_continue(self, state: FactCheckState) -> str:
        """Decide if we should continue processing claims or generate report."""
        if state["current_claim_index"] < len(state["claims"]):
            return "search"  # More claims to process
        return "report"  # All done

    async def _generate_report(self, state: FactCheckState) -> Dict[str, Any]:
        """Step 4: Generate final fact-check report."""
        verifications = state.get("verifications", [])

        verified_count = sum(1 for v in verifications if v.get("status") == "verified")
        disputed_count = sum(1 for v in verifications if v.get("status") == "disputed")
        unverified_count = sum(
            1 for v in verifications if v.get("status") == "unverified"
        )

        total = len(verifications)
        overall_confidence = (
            sum(v.get("confidence", 0) for v in verifications) / total
            if total > 0
            else 0
        )

        report = {
            "resource_id": state["resource_id"],
            "total_claims": total,
            "verified": verified_count,
            "disputed": disputed_count,
            "unverified": unverified_count,
            "overall_confidence": round(overall_confidence, 2),
            "verifications": verifications,
            "summary": f"Checked {total} claims: {verified_count} verified, {disputed_count} disputed, {unverified_count} unverified.",
        }

        return {"final_report": report}

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
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _parse_json_response(self, response: str) -> Any:
        """Extract and parse JSON from AI response."""
        # Try to find JSON in response
        start = response.find("{")
        start_arr = response.find("[")

        if start_arr != -1 and (start == -1 or start_arr < start):
            # Array format
            end = response.rfind("]") + 1
            json_str = response[start_arr:end]
        elif start != -1:
            # Object format
            end = response.rfind("}") + 1
            json_str = response[start:end]
        else:
            raise ValueError("No JSON found in response")

        return json.loads(json_str)


# Singleton instance
fact_checker = FactChecker()
