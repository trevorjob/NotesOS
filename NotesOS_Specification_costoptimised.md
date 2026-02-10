# NotesOS - Your AI Study Companion
## Complete System Specification v2.1 (Cost-Optimized)

**Date:** February 2026  
**Tagline:** "Study smarter, together. Your notes, your AI, your success."

---

## 💰 Cost Optimization Strategy

### Current Setup (Cost-Conscious)

**AI Models:**
- **Primary AI: DeepSeek V3** (`deepseek-chat`)
  - Cost: ~$0.14 per 1M input tokens, ~$0.28 per 1M output tokens
  - 64K context window
  - Excellent at reasoning and educational content
  - **90% cheaper than Claude, 95% cheaper than GPT-4**
  - Can switch to Claude for complex cases if needed
  
**Embeddings:**
- **Primary: OpenAI text-embedding-3-small**
  - Cost: $0.02 per 1M tokens
  - 1536 dimensions (good enough for RAG)
  - **50x cheaper than Voyage AI**
- **Alternative: text-embedding-3-large** (if need better quality)
  - Cost: $0.13 per 1M tokens
  - 3072 dimensions
  - Still way cheaper than Voyage

**Transcription:**
- **OpenAI Whisper API**
  - Cost: $0.006 per minute
  - Only cost is when students use voice (opt-in)
  - No free alternative with comparable quality

**Web Search:**
- **Serper API**
  - Cost: $50 for 5,000 searches, then $5 per 1,000
  - Only used for fact-checking and research
  - Alternative: Tavily API (similar pricing)

### Future Upgrades (When Revenue Allows)

**When to upgrade to Claude:**
- Complex grading requiring nuance
- Students request better explanations
- Need longer context (200K vs 64K)
- Cost: ~$3 per 1M input tokens, ~$15 per 1M output

**When to upgrade embeddings:**
- RAG quality insufficient
- Need better semantic search
- Voyage AI: ~$0.10 per 1M tokens (5x OpenAI small)

### Cost Estimates (100 Active Students)

**Monthly Costs:**
```
DeepSeek API:
- 10M tokens/month (chat, grading, quiz gen) = ~$2
- Very cheap!

OpenAI Embeddings:
- 1M tokens/month (note chunking) = $0.02
- Negligible

Whisper Transcription:
- 50 hours voice answers/month = $18
- Only if students use voice

Serper Search:
- 1,000 searches/month = $10
- Fact checks + research

Total: ~$30-40/month for 100 students = $0.30-0.40 per student
```

**With Claude (for comparison):**
- Same usage would cost ~$150-200/month
- **5x more expensive**

---

## 1. Executive Summary

### 1.1 Product Vision

**NotesOS** is your AI-powered study companion built for students who are tired of scattered notes, lonely studying, and guessing if they actually understand the material. It's a collaborative knowledge hub where your entire class shares notes, and an AI that actually gets you helps you study, test yourself, and master your courses.

Think of it as: **Notion + ChatGPT + Your Best Study Buddy = NotesOS**

### 1.2 Core Value Propositions

- **Shared Knowledge Pool** - One person uploads notes → everyone benefits
- **Auto-Organized Everything** - Courses, topics, weeks—it just works
- **Study Mode, Not Summary Mode** - AI-powered quizzes, concept explanations, progress tracking
- **Your AI Study Partner** - Has personality, encourages you, adapts to how YOU learn
- **Voice-First Studying** - Record answers while cooking. AI transcribes and grades on concepts
- **Built-in Fact Checker** - Verify claims against trusted sources
- **Pre-Class Intel** - AI researches topics before lecture

### 1.3 Target Users

- **Primary:** Part-time students juggling work + school
- **Secondary:** Full-time students who want to actually understand material
- **Tertiary:** Study groups tired of Discord threads

### 1.4 Technology Stack (Cost-Optimized)

#### Frontend
- **React + Next.js 14** - Free (Vercel hosting)
- **Zustand** - Free state management
- **TailwindCSS** - Free styling
- **Shadcn/ui** - Free components

#### Backend & AI
- **Python FastAPI** - Free
- **LangGraph** - Free (OSS)
- **LangChain** - Free (OSS)
- **DeepSeek V3 API** - ~$0.14/$0.28 per 1M tokens (primary AI)
- **OpenAI Whisper** - $0.006/min (voice only)
- **OpenAI Embeddings (small)** - $0.02 per 1M tokens
- **Serper API** - $5 per 1K searches

#### Data & Storage
- **PostgreSQL** - Free tier: Supabase/Neon
- **pgvector** - Free (extension)
- **Redis** - Free tier: Upstash
- **S3-compatible storage** - Cloudflare R2 ($0.015/GB)

**Total startup cost: ~$0-10/month**  
**At 100 users: ~$30-40/month**

---

## 2. System Architecture

[KEEPING SAME AS v2.0 - No changes to architecture]

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User's Browser                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Next.js App  │  │  WebSocket   │  │ Voice Input  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Next.js API Routes (REST + SSE)                │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌──────────────────┐    ┌──────────────────────┐
│  PostgreSQL +    │    │   FastAPI Backend    │
│  pgvector        │◄───┤   (AI Workflows)     │
└──────────────────┘    └──────┬───────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
    ┌─────────┐        ┌──────────────┐     ┌──────────┐
    │  Redis  │        │  LangGraph   │     │   S3     │
    │ (Queue) │        │   Agents     │     │ Storage  │
    └─────────┘        └──────┬───────┘     └──────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
          ┌─────────┐  ┌──────────┐  ┌──────────┐
          │DeepSeek │  │ Whisper  │  │  Serper  │
          │   API   │  │   API    │  │  Search  │
          └─────────┘  └──────────┘  └──────────┘
```

### 2.2 AI Provider Configuration

```python
# config/ai_providers.py

from enum import Enum

class AIProvider(Enum):
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"  # Future upgrade
    OPENAI = "openai"  # Fallback

# Primary provider (cost-optimized)
PRIMARY_AI_PROVIDER = AIProvider.DEEPSEEK

# Model configurations
AI_MODELS = {
    AIProvider.DEEPSEEK: {
        "model": "deepseek-chat",
        "api_base": "https://api.deepseek.com/v1",
        "max_tokens": 8000,  # Output limit
        "context_window": 64000,
        "cost_per_1m_input": 0.14,
        "cost_per_1m_output": 0.28
    },
    AIProvider.CLAUDE: {
        "model": "claude-sonnet-4-5-20250929",
        "max_tokens": 8000,
        "context_window": 200000,
        "cost_per_1m_input": 3.0,
        "cost_per_1m_output": 15.0
    }
}

# Embedding configuration
EMBEDDING_CONFIG = {
    "provider": "openai",
    "model": "text-embedding-3-small",  # Cost-effective
    "dimensions": 1536,
    "cost_per_1m_tokens": 0.02
}

# Alternative for better quality (not using for now)
# EMBEDDING_CONFIG_LARGE = {
#     "provider": "openai",
#     "model": "text-embedding-3-large",
#     "dimensions": 3072,
#     "cost_per_1m_tokens": 0.13
# }

# Future upgrade option (not using for now)
# EMBEDDING_CONFIG_VOYAGE = {
#     "provider": "voyage",
#     "model": "voyage-large-2-instruct",
#     "dimensions": 1024,
#     "cost_per_1m_tokens": 0.10
# }
```

### 2.3 LLM Client Wrapper

```python
# services/llm.py

import httpx
from typing import AsyncGenerator

class LLMClient:
    def __init__(self, provider: AIProvider = PRIMARY_AI_PROVIDER):
        self.provider = provider
        self.config = AI_MODELS[provider]
        
    async def chat_completion(
        self,
        messages: list,
        stream: bool = False,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncGenerator:
        """
        Unified interface for any LLM provider
        """
        if self.provider == AIProvider.DEEPSEEK:
            return await self._deepseek_completion(messages, stream, temperature)
        elif self.provider == AIProvider.CLAUDE:
            return await self._claude_completion(messages, stream, temperature)
    
    async def _deepseek_completion(self, messages, stream, temperature):
        """DeepSeek API client"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.config['api_base']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.config["model"],
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": self.config["max_tokens"],
                    "stream": stream
                },
                timeout=60.0
            )
            
            if stream:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield line[6:]  # Remove "data: " prefix
            else:
                data = response.json()
                yield data["choices"][0]["message"]["content"]
    
    async def _claude_completion(self, messages, stream, temperature):
        """Claude API client (for future upgrade)"""
        # Implementation when we upgrade
        pass

# Usage in agents
llm_client = LLMClient()

async def ask_ai(prompt: str):
    messages = [{"role": "user", "content": prompt}]
    response = await llm_client.chat_completion(messages, stream=True)
    async for chunk in response:
        yield chunk
```

### 2.4 Embedding Service

```python
# services/embeddings.py

import httpx
from openai import AsyncOpenAI

class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.model = EMBEDDING_CONFIG["model"]
        self.dimensions = EMBEDDING_CONFIG["dimensions"]
    
    async def embed_texts(
        self,
        texts: list[str],
        input_type: str = "document"  # or "query"
    ) -> list[list[float]]:
        """
        Generate embeddings for text chunks
        
        Cost: ~$0.02 per 1M tokens
        For 1000 notes (500 words each): ~$0.01
        """
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions
        )
        
        return [item.embedding for item in response.data]
    
    async def embed_single(self, text: str, input_type: str = "document"):
        """Convenience method for single text"""
        embeddings = await self.embed_texts([text], input_type)
        return embeddings[0]

# Usage
embedding_service = EmbeddingService()
embeddings = await embedding_service.embed_texts(chunks)
```

---

## 3. Database Schema & Relations

[KEEPING SAME AS v2.0 - Just update note_chunks table]

### 3.1.6 note_chunks (for RAG)

**Updated for OpenAI embeddings:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Chunk identifier |
| note_id | UUID | FK → notes(id) | Parent note |
| chunk_text | TEXT | NOT NULL | Text chunk (500-1000 chars) |
| chunk_index | INTEGER | NOT NULL | Position in note |
| embedding | VECTOR(1536) | NOT NULL | OpenAI embedding (was 1024) |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation time |

**Index:**
```sql
-- Updated for 1536 dimensions
CREATE INDEX idx_note_chunks_embedding ON note_chunks 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

[REST OF DATABASE SCHEMA STAYS THE SAME]

---

## 4. Core Features & User Flows

[KEEPING SAME AS v2.0 - No changes needed]

---

## 5. AI Agent Workflows & RAG Implementation

### 5.1 RAG Architecture (Cost-Optimized)

**Embedding Cost Analysis:**
```
Scenario: 100 students, 1000 notes total
- Average note: 500 words = ~650 tokens
- Chunking: 5 chunks per note = 5000 chunks
- Total tokens for embedding: 650 × 5000 = 3.25M tokens

Cost with OpenAI text-embedding-3-small:
- 3.25M tokens × $0.02 / 1M = $0.065
- ONE-TIME COST for all notes

Cost with Voyage AI (for comparison):
- 3.25M tokens × $0.10 / 1M = $0.325
- 5x more expensive

Ongoing query embedding:
- ~1000 queries/day = ~20K tokens
- $0.0004/day = $0.12/month
- Negligible!
```

**Quality Comparison:**
- **OpenAI small (1536-dim):** Good for most RAG use cases
- **OpenAI large (3072-dim):** Better semantic understanding
- **Voyage AI (1024-dim):** Optimized for retrieval, but not worth 5x cost for MVP

**Decision:** Start with OpenAI small. If RAG quality is poor, upgrade to large (still cheaper than Voyage).

### 5.1.1 Note Ingestion Pipeline (Updated)

```python
# Pseudocode for note upload → RAG
from services.embeddings import embedding_service

async def ingest_note_for_rag(note_id: str, content: str):
    # 1. Chunk the content
    chunks = chunk_text(
        content,
        chunk_size=800,
        overlap=100,
        respect_sentences=True
    )
    
    # 2. Generate embeddings (OpenAI)
    texts = [chunk.text for chunk in chunks]
    embeddings = await embedding_service.embed_texts(
        texts,
        input_type="document"
    )
    
    # 3. Store chunks with vectors
    for chunk, embedding in zip(chunks, embeddings):
        db.insert("note_chunks", {
            "note_id": note_id,
            "chunk_text": chunk.text,
            "chunk_index": chunk.index,
            "embedding": embedding,  # 1536-dim vector
        })
    
    return f"Ingested {len(chunks)} chunks (cost: ~$0.00002)"
```

### 5.1.2 RAG Query Pipeline (Updated)

```python
from services.llm import LLMClient

async def answer_with_rag(
    question: str,
    topic_id: str,
    user_preferences: dict
) -> dict:
    # 1. Embed the question (OpenAI)
    question_embedding = await embedding_service.embed_single(
        question,
        input_type="query"
    )
    
    # 2. Vector similarity search (pgvector)
    similar_chunks = db.query(f"""
        SELECT 
            nc.chunk_text,
            nc.note_id,
            n.title,
            n.uploaded_by,
            1 - (nc.embedding <=> $1) as similarity
        FROM note_chunks nc
        JOIN notes n ON n.id = nc.note_id
        WHERE n.topic_id = $2
        ORDER BY nc.embedding <=> $1
        LIMIT 10
    """, [question_embedding, topic_id])
    
    # 3. Rerank (simple scoring)
    reranked = rerank_chunks(similar_chunks)
    top_5 = reranked[:5]
    
    # 4. Build context
    context = "\n\n---\n\n".join([
        f"From {chunk.uploader}'s notes ({chunk.title}):\n{chunk.text}"
        for chunk in top_5
    ])
    
    # 5. Call DeepSeek with personality
    llm = LLMClient()  # Uses DeepSeek by default
    personality_prompt = get_personality_prompt(user_preferences)
    
    messages = [
        {
            "role": "system",
            "content": f"""You are a helpful study AI assistant. {personality_prompt}

The student is studying a specific topic and has access to these notes from classmates:

{context}

Answer their question using the provided notes. If the notes don't have enough info, say so and offer to search the web for more. Always cite which classmate's notes you're referencing."""
        },
        {
            "role": "user",
            "content": question
        }
    ]
    
    response = await llm.chat_completion(messages, stream=True)
    
    # 6. Return with citations
    return {
        "answer": response,
        "sources": [
            {"note_id": chunk.note_id, "title": chunk.title}
            for chunk in top_5
        ],
        "cost_estimate": "$0.0001"  # Rough estimate
    }
```

### 5.2 LangGraph Agent Architectures (Using DeepSeek)

#### 5.2.1 Grader Agent (Cost-Optimized)

```python
from langgraph.graph import StateGraph, END
from services.llm import LLMClient

class GradingState(TypedDict):
    answer_id: str
    question: str
    expected_answer: str
    student_answer: str
    is_voice: bool
    score: float
    feedback: str
    encouragement: str

llm = LLMClient()  # DeepSeek

# Step 1: Grade content
async def grade_answer(state):
    prompt = f"""Grade this student answer on concept understanding.

Question: {state['question']}
Expected Answer: {state['expected_answer']}
Student Answer: {state['student_answer']}

{"IMPORTANT: This is transcribed speech. Ignore filler words (um, uh, like, you know), false starts, and rambling. Focus ONLY on concept understanding." if state['is_voice'] else ""}

Rubric:
- Concept understanding: 70%
- Key points coverage: 20%
- Examples/support: 10%

Return JSON:
{{
  "score": 0-100,
  "key_points_covered": ["list", "of", "points"],
  "key_points_missed": ["list", "of", "points"],
  "feedback": "constructive feedback here"
}}
"""
    
    messages = [{"role": "user", "content": prompt}]
    response = await llm.chat_completion(messages, stream=False)
    
    # Parse JSON from response
    result = json.loads(response)
    
    return {
        "score": result["score"],
        "feedback": result["feedback"],
        "key_points_covered": result["key_points_covered"],
        "key_points_missed": result["key_points_missed"]
    }

# Step 2: Generate encouragement
def add_encouragement(state):
    score = state["score"]
    tone = state.get("user_tone", "encouraging")
    
    if score >= 90:
        encouragements = {
            "encouraging": "🔥 Absolutely crushing it!",
            "direct": "Excellent work. Top marks.",
            "humorous": "🎉 You're basically a genius now!"
        }
    elif score >= 70:
        encouragements = {
            "encouraging": "💪 Solid answer! Just a few tweaks needed.",
            "direct": "Good. Address the missed points.",
            "humorous": "Not bad! You're like 80% wizard 🧙‍♂️"
        }
    elif score >= 50:
        encouragements = {
            "encouraging": "🌱 You're getting there! Let's clarify a few things.",
            "direct": "Needs improvement. Review the material.",
            "humorous": "Eh, you're getting warmer... like lukewarm 🤔"
        }
    else:
        encouragements = {
            "encouraging": "💭 No worries, this is tough. Want me to explain it differently?",
            "direct": "Review required. Focus on key concepts.",
            "humorous": "Okay so... let's try that again 😅"
        }
    
    return {"encouragement": encouragements.get(tone, encouragements["encouraging"])}

# Build graph
workflow = StateGraph(GradingState)
workflow.add_node("grade", grade_answer)
workflow.add_node("encourage", add_encouragement)

workflow.set_entry_point("grade")
workflow.add_edge("grade", "encourage")
workflow.add_edge("encourage", END)

grader_agent = workflow.compile()
```

**Cost per grading:**
```
Average grading:
- Input: ~500 tokens (question + answers)
- Output: ~200 tokens (feedback JSON)

DeepSeek cost: ($0.14 × 0.5 + $0.28 × 0.2) / 1000 = $0.000126
Claude cost (for comparison): ($3 × 0.5 + $15 × 0.2) / 1000 = $0.0045

DeepSeek is 35x cheaper!
```

#### 5.2.2 Fact Checker Agent (Multi-Step, Cost-Aware)

```python
# Only check critical facts to save on web search costs
# Serper: $5 per 1000 searches

async def extract_claims(state):
    """Extract only important factual claims"""
    prompt = f"""Extract ONLY critical factual claims from this text that MUST be verified:
- Dates of major events
- Names of key figures
- Statistics and numbers
- Cause-and-effect relationships

Ignore: Opinions, interpretations, general knowledge

Text: {state['content']}

Return JSON: {{"claims": [{{"text": "...", "type": "date|name|statistic|relationship"}}]}}
"""
    
    messages = [{"role": "user", "content": prompt}]
    response = await llm.chat_completion(messages, stream=False)
    claims = json.loads(response)["claims"]
    
    # Limit to 5 most important claims to control costs
    return {"claims": claims[:5]}

# Search only if claim is disputed or unclear
async def search_claim(state):
    claim = state["claims"][0]
    
    # Use Serper (costs $0.005 per search)
    results = await serper_search(claim["text"])
    
    return {"search_results": results}

# Rest of workflow same as v2.0...
```

**Cost per fact-check:**
```
Per note with 5 claims:
- LLM extraction: ~$0.0001
- 5 web searches: 5 × $0.005 = $0.025
- LLM verification: 5 × $0.0001 = $0.0005
Total: ~$0.026 per note

Can reduce by only fact-checking on demand (not automatic).
```

### 5.3 Cost-Saving Strategies

```python
# config/feature_flags.py

class FeatureFlags:
    # Expensive features (can disable to save costs)
    AUTO_FACT_CHECK = False  # Only on-demand initially
    AUTO_PRE_CLASS_RESEARCH = False  # Only on-demand
    
    # Cheap features (always on)
    RAG_ENABLED = True
    AI_CHAT = True
    QUIZ_GENERATION = True
    VOICE_GRADING = True  # Students opt-in, so controlled

# Usage
if FeatureFlags.AUTO_FACT_CHECK:
    queue_fact_check_job(note_id)
else:
    # Show button: "Verify Facts (uses AI)"
    pass
```

---

## 6-10. [REST OF SECTIONS]

[All remaining sections (API specs, frontend, security, deployment, phases) remain the same as v2.0, just references to Claude are now DeepSeek]

---

## Appendix C: Cost Analysis & Scaling

### C.1 Cost Breakdown by Feature

**Per Student Per Month (Active User):**

| Feature | Usage | Cost |
|---------|-------|------|
| RAG queries | 100 queries | $0.002 |
| AI chat | 50 messages | $0.01 |
| Quiz generation | 5 quizzes × 10 questions | $0.02 |
| Voice grading | 10 voice answers | $0.06 + $0.001 (transcription) |
| Fact checking | 5 notes (on-demand) | $0.13 |
| **Total** | | **$0.22/student/month** |

### C.2 Revenue Model (Future)

**Free Tier:**
- 3 courses
- 50 AI messages/day
- 5 quizzes/week
- Voice answers: 10/week
- No fact-checking (manual only)

**Pro Tier ($4.99/month):**
- Unlimited courses
- Unlimited AI messages
- Unlimited quizzes
- Unlimited voice answers
- Auto fact-checking
- Priority support

**Margin:**
- Revenue: $4.99
- Cost: $0.22
- Profit: $4.77 (95% margin!)

### C.3 When to Upgrade to Claude

**Upgrade triggers:**
1. **Revenue > $500/month** (100+ paying users)
2. **User complaints** about DeepSeek quality
3. **Complex reasoning needed** (DeepSeek struggles)
4. **Competitive advantage** (Claude's personality shines)

**Hybrid approach:**
- Use DeepSeek for: Chat, simple Q&A, quiz generation
- Use Claude for: Complex grading, nuanced feedback, personality-heavy interactions
- Saves 70% cost vs. Claude-only

---

## Appendix D: Handwritten Note Transcription (Cost-Optimized)

### D.1 Hybrid OCR Pipeline

**Philosophy:** Start with free/cheap OCR, escalate to premium only when needed.

```
┌─────────────────────────────────────────────────────────────────┐
│                  HANDWRITTEN NOTE TRANSCRIPTION                 │
└─────────────────────────────────────────────────────────────────┘

   ┌──────────────┐
   │ Image Upload │
   └──────┬───────┘
          │
          ▼
   ┌──────────────────────────────────────────────┐
   │ 1. IMAGE PREPROCESSING (Free)                │
   │    • Grayscale conversion                    │
   │    • Contrast enhancement                    │
   │    • Noise reduction                         │
   │    • Deskew correction                       │
   │    • Binarization (adaptive threshold)       │
   └──────────────────┬───────────────────────────┘
                      │
                      ▼
   ┌──────────────────────────────────────────────┐
   │ 2. TESSERACT OCR (Free - Default)            │
   │    • Model: eng + script/Latin               │
   │    • Config: --psm 6 (uniform block)         │
   │    • Returns: text + word confidence scores  │
   └──────────────────┬───────────────────────────┘
                      │
                      ▼
   ┌──────────────────────────────────────────────┐
   │ 3. CONFIDENCE CHECK                          │
   │    • Calculate average word confidence       │
   │    • Threshold: 65%                          │
   └──────────────────┬───────────────────────────┘
                      │
            ┌─────────┴─────────┐
            │                   │
    confidence ≥ 65%    confidence < 65%
            │                   │
            ▼                   ▼
   ┌────────────────┐  ┌─────────────────────────┐
   │ Use Tesseract  │  │ 4. GOOGLE VISION API    │
   │ Result         │  │    (Fallback, Paid)     │
   └───────┬────────┘  │    • DOCUMENT_TEXT mode │
           │           │    • Handwriting-aware  │
           │           └───────────┬─────────────┘
           │                       │
           └───────────┬───────────┘
                       │
                       ▼
   ┌──────────────────────────────────────────────┐
   │ 5. DEEPSEEK LLM CLEANUP (Always)             │
   │    • Fix spelling/spacing errors             │
   │    • Infer structure (headings, bullets)     │
   │    • Mark unclear text as [unclear]          │
   │    • Output clean Markdown                   │
   └──────────────────┬───────────────────────────┘
                      │
                      ▼
   ┌──────────────────────────────────────────────┐
   │ 6. STORE RESULTS                             │
   │    • Original raw OCR text                   │
   │    • Cleaned Markdown content                │
   │    • Confidence score                        │
   │    • OCR provider used                       │
   └──────────────────────────────────────────────┘
```

### D.2 OCR Confidence Scoring

```python
# services/ocr_confidence.py

def calculate_confidence(tesseract_output: dict) -> float:
    """
    Calculate weighted average of Tesseract word confidences.
    Returns: float between 0.0 and 1.0
    """
    word_confidences = tesseract_output.get("word_confidences", [])
    
    if not word_confidences:
        return 0.0
    
    # Weight longer words more (they're harder to OCR correctly)
    weighted_sum = 0
    total_weight = 0
    
    for word, conf in word_confidences:
        weight = max(1, len(word) / 3)  # Weight by word length
        weighted_sum += conf * weight
        total_weight += weight
    
    return weighted_sum / total_weight if total_weight > 0 else 0.0

# Thresholds
OCR_CONFIDENCE_THRESHOLD = 0.65  # Below this → use Google Vision
OCR_LOW_CONFIDENCE_THRESHOLD = 0.40  # Below this → mark as [unclear]
```

### D.3 Fallback to Google Vision API

```python
# services/google_vision_ocr.py

from google.cloud import vision

class GoogleVisionOCR:
    def __init__(self):
        self.client = vision.ImageAnnotatorClient()
    
    async def extract_handwriting(self, image_bytes: bytes) -> dict:
        """
        Extract text from handwritten images.
        Cost: $1.50 per 1000 images
        """
        image = vision.Image(content=image_bytes)
        response = self.client.document_text_detection(image=image)
        
        if response.error.message:
            raise Exception(response.error.message)
        
        full_text = response.full_text_annotation.text
        confidence = self._calculate_confidence(response)
        
        return {
            "text": full_text,
            "confidence": confidence,
            "provider": "google_vision"
        }
    
    def _calculate_confidence(self, response) -> float:
        """Calculate average symbol confidence"""
        confidences = []
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        for symbol in word.symbols:
                            confidences.append(symbol.confidence)
        
        return sum(confidences) / len(confidences) if confidences else 0.0
```

### D.4 DeepSeek LLM Cleanup

```python
# services/ocr_text_cleaner.py

CLEANUP_PROMPT = """
You are cleaning up OCR output from a handwritten student note.

INPUT (raw OCR text):
{raw_text}

INSTRUCTIONS:
1. Fix obvious spelling mistakes caused by OCR (e.g., "rn" → "m", "l" → "I")
2. Fix spacing issues (missing spaces, extra spaces)
3. Infer document structure:
   - Identify headings (larger text, underlined)
   - Identify bullet points or numbered lists
   - Identify paragraph breaks
4. Mark text that is truly illegible as [unclear]
5. Preserve the student's original meaning - don't add content
6. Output clean Markdown

OUTPUT FORMAT:
Return ONLY the cleaned Markdown text, no explanations.

If confidence level is below 40%, wrap uncertain sections like this:
[unclear: possible text here]

EXAMPLE:
Input: "Th3 Fench Revolut1on began 1n 1789  it was caosed by"
Output: "The French Revolution began in 1789. It was caused by"
"""

async def clean_ocr_text(
    raw_text: str,
    confidence: float
) -> dict:
    """
    Clean OCR text using DeepSeek.
    Cost: ~$0.0001 per cleaning (200 tokens avg)
    """
    prompt = CLEANUP_PROMPT.format(raw_text=raw_text)
    
    if confidence < 0.4:
        prompt += "\n\nWARNING: Low confidence OCR. Be aggressive about marking [unclear] sections."
    
    response = await llm_client.chat_completion([
        {"role": "user", "content": prompt}
    ])
    
    cleaned_text = ""
    async for chunk in response:
        cleaned_text += chunk
    
    return {
        "original_text": raw_text,
        "cleaned_text": cleaned_text.strip(),
        "confidence": confidence,
        "unclear_sections": cleaned_text.count("[unclear")
    }
```

### D.5 Cost Analysis

| Component | Cost | When Used |
|-----------|------|-----------|
| Image preprocessing | FREE | Always |
| Tesseract OCR | FREE | Always (first pass) |
| Google Vision API | $0.0015/image | Only when Tesseract < 65% confidence |
| DeepSeek cleanup | ~$0.0001/note | Always |

**Per-Student Estimates (20 handwritten notes/month):**

| Scenario | Cost |
|----------|------|
| Good handwriting (90% Tesseract success) | $0.002/month |
| Average handwriting (70% Tesseract success) | $0.011/month |
| Poor handwriting (30% Tesseract success) | $0.023/month |

**Worst Case:** 100 students × poor handwriting = $2.30/month for handwriting OCR

### D.6 Feature Flags

```python
class OCRFeatureFlags:
    # Default to cheap OCR only
    ENABLE_GOOGLE_VISION_FALLBACK = True  # Can disable to force Tesseract-only
    
    # Confidence thresholds
    GOOGLE_VISION_THRESHOLD = 0.65  # Trigger fallback below this
    
    # Premium tier only
    PREMIUM_ALWAYS_USE_GOOGLE_VISION = False  # For paying users
    
    # User override
    ALLOW_USER_REQUESTED_REPROCESS = True  # Let user click "Improve transcription"

# Usage
async def process_handwritten_note(image_bytes: bytes, user: User):
    result = await tesseract_ocr(image_bytes)
    
    # Check if we should use premium OCR
    use_premium = (
        (OCRFeatureFlags.ENABLE_GOOGLE_VISION_FALLBACK and result.confidence < OCRFeatureFlags.GOOGLE_VISION_THRESHOLD)
        or (user.is_premium and OCRFeatureFlags.PREMIUM_ALWAYS_USE_GOOGLE_VISION)
    )
    
    if use_premium:
        result = await google_vision_ocr(image_bytes)
    
    return await clean_ocr_text(result.text, result.confidence)
```

---

## Appendix E: Offline Mode (Consumption-First)

### E.1 Philosophy

**Pragmatic Offline:** Offline mode enables reading and creation, not AI. All intelligence requires internet.

**What This Is NOT:**
- ❌ Offline AI processing
- ❌ Offline embeddings or search
- ❌ Offline fact-checking
- ❌ Edge AI models

**What This IS:**
- ✅ Read your synced notes anywhere
- ✅ View already-generated AI content
- ✅ Create/edit notes (synced later)
- ✅ Queue uploads for later processing

### E.2 Offline Capabilities (What Works Offline)

| Feature | Offline Behavior |
|---------|------------------|
| **View notes** | ✅ Read all synced notes |
| **View AI summaries** | ✅ Pre-generated summaries load from cache |
| **View explanations** | ✅ Previously requested explanations available |
| **View fact-check results** | ✅ Cached verification results display |
| **View quiz Q&A** | ✅ Generated quizzes available (no grading) |
| **Read AI chat history** | ✅ Previous conversations cached |
| **Create text notes** | ✅ Saved locally, synced on reconnect |
| **Edit existing notes** | ✅ Changes queued for sync |
| **Upload images/files** | ✅ Queued locally, processed on reconnect |
| **View course structure** | ✅ Topics, metadata cached |

### E.3 Offline Limitations (What Requires Internet)

| Feature | Offline Behavior |
|---------|------------------|
| **AI chat (new messages)** | ❌ Blocked, shows "Offline" message |
| **AI explanations (new)** | ❌ Blocked, button disabled |
| **Quiz generation** | ❌ Blocked, can only view existing |
| **Quiz grading** | ❌ Blocked, answers saved for later grading |
| **Fact-checking** | ❌ Blocked, no web access |
| **Note search (semantic)** | ❌ Degraded to local text search |
| **Voice transcription** | ❌ Blocked, requires Whisper API |
| **File processing (OCR)** | ❌ Queued, processed on reconnect |
| **Real-time collaboration** | ❌ No WebSocket, changes queue locally |

### E.4 Offline Data Storage Strategy

```typescript
// Frontend: IndexedDB Schema

interface OfflineDatabase {
  // Synced data (read-only until online)
  notes: {
    id: string;
    topicId: string;
    title: string;
    content: string;  // Full markdown content
    fileUrl?: string;
    syncedAt: Date;
    localEdits?: string;  // Unsync'd changes
  }[];
  
  topics: {
    id: string;
    courseId: string;
    name: string;
    weekNumber: number;
    syncedAt: Date;
  }[];
  
  courses: {
    id: string;
    code: string;
    name: string;
    syncedAt: Date;
  }[];
  
  // Cached AI artifacts (read-only)
  aiArtifacts: {
    id: string;
    noteId: string;
    type: 'summary' | 'explanation' | 'fact_check' | 'quiz' | 'chat_history';
    content: any;  // Pre-rendered HTML or structured data
    generatedAt: Date;
    syncedAt: Date;
  }[];
  
  // Pending operations (sync queue)
  syncQueue: {
    id: string;
    type: 'create_note' | 'edit_note' | 'upload_file' | 'quiz_answer';
    payload: any;
    createdAt: Date;
    retryCount: number;
  }[];
  
  // Pending file uploads
  pendingUploads: {
    id: string;
    topicId: string;
    filename: string;
    fileBlob: Blob;
    metadata: any;
    queuedAt: Date;
  }[];
}
```

**Storage Limits:**
- Notes: Up to 1000 notes cached (~50MB)
- AI artifacts: Up to 500 artifacts cached (~20MB)
- Pending uploads: Up to 50 files (~100MB)
- Total: ~170MB IndexedDB quota (well under browser limits)

### E.5 Sync & Rehydration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     SYNC FLOW ON RECONNECT                      │
└─────────────────────────────────────────────────────────────────┘

   ┌────────────────┐
   │ App Detects    │
   │ Internet       │
   └───────┬────────┘
           │
           ▼
   ┌───────────────────────────────────────────┐
   │ 1. PUSH: Process Sync Queue               │
   │    • Create notes (in order)              │
   │    • Apply edits (with merge resolution)  │
   │    • Upload pending files                 │
   │    • Retry failed items (max 3 attempts)  │
   └───────────────────┬───────────────────────┘
                       │
                       ▼
   ┌───────────────────────────────────────────┐
   │ 2. PULL: Fetch Updates Since Last Sync    │
   │    • GET /api/sync?since={lastSyncTime}   │
   │    • Returns: changed notes, new notes,   │
   │      deleted IDs, new AI artifacts        │
   └───────────────────┬───────────────────────┘
                       │
                       ▼
   ┌───────────────────────────────────────────┐
   │ 3. MERGE: Reconcile Conflicts             │
   │    • Server wins for AI artifacts         │
   │    • User prompted for note conflicts     │
   │    • Deleted items removed locally        │
   └───────────────────┬───────────────────────┘
                       │
                       ▼
   ┌───────────────────────────────────────────┐
   │ 4. CACHE: Pre-fetch AI Artifacts          │
   │    • For notes viewed in last 7 days      │
   │    • Summaries, explanations, quizzes     │
   │    • Maximum 100 artifacts per sync       │
   └───────────────────────────────────────────┘
```

### E.6 UX States and User Messaging

```typescript
// Offline states
type OfflineState = 
  | 'online'           // Full functionality
  | 'offline'          // Read-only mode
  | 'syncing'          // Reconnected, syncing
  | 'sync_error';      // Sync failed

// UI messages
const OFFLINE_MESSAGES = {
  // Global banner
  banner: "You're offline. Notes are read-only. Changes will sync when you're back online.",
  
  // Feature-specific
  ai_chat_disabled: "AI chat requires internet. Your previous conversations are still available.",
  quiz_save: "Answer saved! Grading will happen when you're back online.",
  note_queued: "Note saved locally. It will upload when you're back online.",
  file_queued: "File queued. It will be processed when you're back online.",
  search_degraded: "Offline search uses text matching only. Semantic search requires internet.",
  
  // Reconnection
  syncing: "Back online! Syncing your changes...",
  sync_complete: "All changes synced successfully.",
  sync_conflict: "We found a conflict. Please review and choose which version to keep.",
  sync_error: "Sync failed. We'll try again automatically."
};
```

**Visual Indicators:**

| State | UI Treatment |
|-------|--------------|
| Offline | Yellow banner, AI buttons grayed out with tooltip |
| Queued content | Small "pending sync" icon on notes/uploads |
| Cached AI | Normal display (no indicator needed) |
| Syncing | Spinner in header, progress for uploads |
| Conflict | Modal dialog with diff view |

### E.7 Feature Flags for Offline

```python
class OfflineFeatureFlags:
    # Enable/disable offline mode entirely
    OFFLINE_MODE_ENABLED = True
    
    # Cache settings
    MAX_CACHED_NOTES = 1000
    MAX_CACHED_AI_ARTIFACTS = 500
    MAX_PENDING_UPLOADS = 50
    CACHE_RETENTION_DAYS = 30  # Clear unused cached items after 30 days
    
    # Sync settings
    AUTO_SYNC_ON_RECONNECT = True
    SYNC_RETRY_ATTEMPTS = 3
    SYNC_RETRY_DELAY_MS = 5000
    
    # Prefetch settings
    PREFETCH_AI_ARTIFACTS = True  # Pre-cache AI content for recently viewed notes
    PREFETCH_LOOKBACK_DAYS = 7    # Cache artifacts for notes viewed in last 7 days
```

---

## Document End

**TL;DR on Cost Optimization:**

✅ **Using DeepSeek:** 90% cheaper than Claude, still great quality  
✅ **Using OpenAI small embeddings:** 50x cheaper than Voyage, good enough  
✅ **Hybrid OCR:** Free Tesseract first, paid Google Vision only when needed  
✅ **Offline mode:** Read cached content, no offline AI processing  
✅ **Total cost:** ~$0.22-0.25 per active student per month  
✅ **Can upgrade later** when revenue allows  
✅ **Feature flags** to disable expensive features (fact-check, research, premium OCR)  

**Start cheap, scale smart. 🚀**

