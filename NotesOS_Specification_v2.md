# NotesOS - Your AI Study Companion
## Complete System Specification v2.0

**Date:** February 2026  
**Tagline:** "Study smarter, together. Your notes, your AI, your success."

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Database Schema & Relations](#3-database-schema--relations)
4. [Core Features & User Flows](#4-core-features--user-flows)
5. [AI Agent Workflows & RAG Implementation](#5-ai-agent-workflows--rag-implementation)
6. [API Specifications](#6-api-specifications)
7. [Frontend Components & State Management](#7-frontend-components--state-management)
8. [Security & Authentication](#8-security--authentication)
9. [Deployment & Infrastructure](#9-deployment--infrastructure)
10. [Development Phases & Milestones](#10-development-phases--milestones)

---

## 1. Executive Summary

### 1.1 Product Vision

**NotesOS** is your AI-powered study companion built for students who are tired of scattered notes, lonely studying, and guessing if they actually understand the material. It's a collaborative knowledge hub where your entire class shares notes, and an AI that actually gets you helps you study, test yourself, and master your courses.

Think of it as: **Notion + ChatGPT + Your Best Study Buddy = NotesOS**

### 1.2 Core Value Propositions

- **Shared Knowledge Pool** - One person uploads notes → everyone benefits. No more "can I get your notes?" texts at 2 AM
- **Auto-Organized Everything** - Courses, topics, weeks—it just works. Your notes organize themselves
- **Study Mode, Not Summary Mode** - Don't just read—study with AI-powered quizzes, concept explanations, and progress tracking
- **Your AI Study Partner** - Not some boring corporate bot. This AI has personality, encourages you, and adapts to how YOU learn
- **Voice-First Studying** - Record your answers while cooking dinner. The AI transcribes, understands, and grades you on concepts (not grammar)
- **Built-in Fact Checker** - Because your classmate Sarah writes "Napoleon died in 1820" and you don't want to fail because of it
- **Pre-Class Intel** - AI researches topics before lecture so you're not completely lost when the professor starts talking

### 1.3 Target Users

- **Primary:** Part-time students juggling work + school
- **Secondary:** Full-time students who want to actually understand their material
- **Tertiary:** Study groups who are tired of Discord threads and shared Google Docs

### 1.4 Technology Stack

#### Frontend
- **React + Next.js 14 (App Router)** - Fast, modern, SEO-friendly
- **Zustand** - Simple state management (no Redux complexity)
- **TailwindCSS** - Beautiful UI without the CSS headache
- **Shadcn/ui** - Pre-built accessible components

#### Backend & AI
- **Python FastAPI** - Fast, async-first, perfect for AI workflows
- **LangGraph** - AI agent orchestration (complex multi-step workflows)
- **LangChain** - RAG implementation and tool calling
- **Anthropic Claude Sonnet 4.5** - Main AI brain (educational content, grading, reasoning)
- **OpenAI Whisper** - Voice transcription
- **Serper API** - Web search for fact-checking and research

#### Data & Storage
- **PostgreSQL** - Relational data with JSONB for flexibility
- **pgvector** - Vector embeddings for RAG similarity search
- **Redis** - Job queues, caching, rate limiting
- **Qdrant (optional)** - Dedicated vector database if scale demands it
- **S3-compatible storage** - Notes, audio files, PDFs

#### Search & Embeddings
- **Voyage AI Embeddings** - High-quality text embeddings for RAG
- **PostgreSQL Full-Text Search** - Keyword search
- **Vector Similarity Search** - Semantic search via pgvector

---

## 2. System Architecture

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
          │ Claude  │  │ Whisper  │  │  Serper  │
          │   API   │  │   API    │  │  Search  │
          └─────────┘  └──────────┘  └──────────┘
```

### 2.2 AI Workflow Architecture

**We're using LangGraph, not just LangChain, because:**
- Complex multi-step reasoning (fact-checking requires multiple searches + verification)
- State management across agent steps
- Conditional logic (if fact unclear → search more)
- Human-in-the-loop optional (user can verify disputed facts)

**RAG Implementation:**
```
User Question
      ↓
1. Embed question (Voyage AI)
      ↓
2. Vector search notes (pgvector) → Retrieve top 5 relevant chunks
      ↓
3. Rerank by relevance (simple scoring)
      ↓
4. Build context for Claude
      ↓
5. Claude generates answer with citations
      ↓
6. Stream response to user
```

### 2.3 Fact Checking External System Flow

```
Note Uploaded
      ↓
Extract Claims (Claude)
      ↓
For Each Claim:
  ├─→ Search Web (Serper API)
  ├─→ Filter Academic Sources (.edu, .gov, scholarly)
  ├─→ Fetch Top 3 Sources (BeautifulSoup)
  ├─→ Extract Relevant Text
  ├─→ Claude Verifies: "Does this source support the claim?"
  ├─→ Aggregate Verification Results
      ↓
Store in fact_checks table
      ↓
Display side-by-side with notes
```

---

## 3. Database Schema & Relations

### 3.1 Core Tables

#### 3.1.1 users
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique user identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL | User email |
| password_hash | VARCHAR(255) | NOT NULL | Hashed password |
| full_name | VARCHAR(255) | NOT NULL | User's full name |
| avatar_url | TEXT | NULL | Profile picture URL |
| study_personality | JSONB | NULL | AI personality preferences |
| created_at | TIMESTAMP | DEFAULT NOW() | Account creation time |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last update time |
| last_login | TIMESTAMP | NULL | Last login timestamp |

**study_personality JSONB structure:**
```json
{
  "tone": "encouraging",  // "encouraging", "direct", "humorous"
  "emoji_usage": "moderate",  // "none", "moderate", "heavy"
  "explanation_style": "detailed"  // "concise", "detailed", "visual"
}
```

#### 3.1.2 courses
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique course identifier |
| code | VARCHAR(50) | NOT NULL | Course code (e.g., HIST101) |
| name | VARCHAR(255) | NOT NULL | Course name |
| description | TEXT | NULL | Course description |
| semester | VARCHAR(50) | NULL | e.g., 'Fall 2026' |
| created_by | UUID | FK → users(id) | Course creator |
| is_active | BOOLEAN | DEFAULT true | Active status |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last update |

**Note:** NO "instructor" role. Everyone is a peer student.

#### 3.1.3 course_enrollments
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Enrollment ID |
| user_id | UUID | FK → users(id) | Student user ID |
| course_id | UUID | FK → courses(id) | Course ID |
| joined_at | TIMESTAMP | DEFAULT NOW() | Enrollment time |
| | | UNIQUE(user_id, course_id) | One enrollment per user-course |

#### 3.1.4 topics
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Topic identifier |
| course_id | UUID | FK → courses(id) | Parent course |
| title | VARCHAR(255) | NOT NULL | Topic title |
| description | TEXT | NULL | Topic description |
| week_number | INTEGER | NULL | Week in semester |
| order_index | INTEGER | NOT NULL | Display order |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation time |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last update |

#### 3.1.5 notes
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Note identifier |
| topic_id | UUID | FK → topics(id) | Parent topic |
| uploaded_by | UUID | FK → users(id) | User who uploaded |
| title | VARCHAR(255) | NOT NULL | Note title |
| content | TEXT | NOT NULL | Note content (markdown) |
| content_type | ENUM | 'text','pdf','image' | Content format |
| file_url | TEXT | NULL | Storage URL if file |
| is_verified | BOOLEAN | DEFAULT false | Fact-checked status |
| created_at | TIMESTAMP | DEFAULT NOW() | Upload time |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last edit time |

#### 3.1.6 note_chunks (for RAG)
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Chunk identifier |
| note_id | UUID | FK → notes(id) | Parent note |
| chunk_text | TEXT | NOT NULL | Text chunk (500-1000 chars) |
| chunk_index | INTEGER | NOT NULL | Position in note |
| embedding | VECTOR(1024) | NOT NULL | Vector embedding |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation time |

**Index:**
```sql
CREATE INDEX idx_note_chunks_embedding ON note_chunks 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

#### 3.1.7 note_versions
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Version identifier |
| note_id | UUID | FK → notes(id) | Parent note |
| content | TEXT | NOT NULL | Version content |
| edited_by | UUID | FK → users(id) | Editor user ID |
| version_number | INTEGER | NOT NULL | Version sequence |
| created_at | TIMESTAMP | DEFAULT NOW() | Version timestamp |

#### 3.1.8 fact_checks
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Fact check ID |
| note_id | UUID | FK → notes(id) | Related note |
| claim_text | TEXT | NOT NULL | Claim being verified |
| verification_status | ENUM | 'verified','disputed','unverified' | Check result |
| sources | JSONB | NOT NULL | Array of source objects |
| confidence_score | DECIMAL(3,2) | NULL | 0.00 - 1.00 |
| ai_explanation | TEXT | NULL | AI reasoning |
| created_at | TIMESTAMP | DEFAULT NOW() | Check time |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last update |

**sources JSONB structure:**
```json
[
  {
    "url": "https://britannica.com/...",
    "title": "French Revolution",
    "domain": "britannica.com",
    "snippet": "The revolution began in 1789...",
    "relevance_score": 0.95
  }
]
```

#### 3.1.9 pre_class_research
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Research ID |
| topic_id | UUID | FK → topics(id) | Topic researched |
| research_content | TEXT | NOT NULL | Research summary |
| sources | JSONB | NOT NULL | Source URLs array |
| key_concepts | JSONB | NULL | Extracted concepts |
| generated_at | TIMESTAMP | DEFAULT NOW() | Generation time |

#### 3.1.10 study_sessions
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Session identifier |
| user_id | UUID | FK → users(id) | Student |
| topic_id | UUID | FK → topics(id) | Topic studied |
| session_type | ENUM | 'reading','quiz','practice' | Activity type |
| started_at | TIMESTAMP | DEFAULT NOW() | Session start |
| ended_at | TIMESTAMP | NULL | Session end |
| duration_seconds | INTEGER | NULL | Time spent |
| notes_reviewed | JSONB | NULL | Array of note IDs |
| concepts_covered | JSONB | NULL | Concepts studied |

#### 3.1.11 tests
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Test identifier |
| course_id | UUID | FK → courses(id) | Course test belongs to |
| created_by | UUID | FK → users(id) | Test creator |
| title | VARCHAR(255) | NOT NULL | Test name |
| test_type | ENUM | 'practice','mock','self-test' | Type of test |
| topics | JSONB | NOT NULL | Array of topic IDs |
| question_count | INTEGER | NOT NULL | Number of questions |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation time |

#### 3.1.12 test_questions
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Question ID |
| test_id | UUID | FK → tests(id) | Parent test |
| question_text | TEXT | NOT NULL | Question content |
| question_type | ENUM | 'mcq','short_answer','essay' | Question format |
| correct_answer | TEXT | NULL | Expected answer |
| answer_options | JSONB | NULL | MCQ options |
| points | INTEGER | DEFAULT 1 | Point value |
| order_index | INTEGER | NOT NULL | Question order |

#### 3.1.13 test_attempts
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Attempt ID |
| test_id | UUID | FK → tests(id) | Test taken |
| user_id | UUID | FK → users(id) | Student |
| started_at | TIMESTAMP | DEFAULT NOW() | Start time |
| completed_at | TIMESTAMP | NULL | Completion time |
| total_score | DECIMAL(5,2) | NULL | Final score |
| max_score | INTEGER | NOT NULL | Maximum possible |

#### 3.1.14 test_answers
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Answer ID |
| attempt_id | UUID | FK → test_attempts(id) | Test attempt |
| question_id | UUID | FK → test_questions(id) | Question answered |
| answer_text | TEXT | NULL | Text answer |
| answer_audio_url | TEXT | NULL | Voice recording URL |
| transcription | TEXT | NULL | Audio transcription |
| score | DECIMAL(5,2) | NULL | Points earned |
| ai_feedback | TEXT | NULL | AI grading feedback |
| encouragement | TEXT | NULL | Motivational message |
| created_at | TIMESTAMP | DEFAULT NOW() | Answer time |

#### 3.1.15 user_progress
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Progress ID |
| user_id | UUID | FK → users(id) | Student |
| course_id | UUID | FK → courses(id) | Course |
| topic_id | UUID | FK → topics(id) | Topic |
| mastery_level | DECIMAL(3,2) | DEFAULT 0.00 | 0.00 - 1.00 |
| total_study_time | INTEGER | DEFAULT 0 | Seconds spent |
| total_attempts | INTEGER | DEFAULT 0 | Test attempts |
| avg_score | DECIMAL(5,2) | NULL | Average score |
| streak_days | INTEGER | DEFAULT 0 | Consecutive study days |
| last_activity | TIMESTAMP | DEFAULT NOW() | Last interaction |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last update |
| | | UNIQUE(user_id, course_id, topic_id) | One per user-topic |

#### 3.1.16 ai_conversations
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Conversation ID |
| user_id | UUID | FK → users(id) | User |
| course_id | UUID | FK → courses(id) | Context course |
| topic_id | UUID | FK → topics(id) | Context topic |
| title | VARCHAR(255) | NULL | Auto-generated title |
| created_at | TIMESTAMP | DEFAULT NOW() | Conversation start |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last message |

#### 3.1.17 ai_messages
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Message ID |
| conversation_id | UUID | FK → ai_conversations(id) | Parent conversation |
| role | ENUM | 'user','assistant' | Message sender |
| content | TEXT | NOT NULL | Message text |
| metadata | JSONB | NULL | Citations, sources, etc |
| created_at | TIMESTAMP | DEFAULT NOW() | Message time |

#### 3.1.18 course_outlines
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Outline ID |
| course_id | UUID | FK → courses(id) | Course |
| uploaded_by | UUID | FK → users(id) | Uploader |
| outline_content | TEXT | NOT NULL | Syllabus content |
| file_url | TEXT | NULL | Original file URL |
| parsed_topics | JSONB | NULL | Extracted topics |
| created_at | TIMESTAMP | DEFAULT NOW() | Upload time |

---

## 4. Core Features & User Flows

### 4.1 User Authentication & Onboarding

#### 4.1.1 Registration Flow
1. User visits `/register`
2. Fills form: email, password, full name
3. **AI Personality Setup (Optional):**
   - "How should your AI study buddy talk to you?"
   - Options: Encouraging / Direct / Humorous
   - Emoji preference: None / Moderate / Heavy
   - Explanation style: Concise / Detailed
4. System validates email uniqueness
5. Password hashed with bcrypt
6. User record created
7. JWT token generated
8. User redirected to `/dashboard` with welcome message

#### 4.1.2 Login Flow
1. User visits `/login`
2. Enters email and password
3. System verifies credentials
4. Updates `last_login` timestamp
5. JWT token issued
6. User redirected to `/dashboard`

### 4.2 Course Management (Peer-to-Peer)

#### 4.2.1 Create Course Flow
1. User clicks "Start a Course" on dashboard
2. Modal opens:
   - Course Code (e.g., HIST101)
   - Course Name
   - Semester (optional)
   - Description
   - **Public/Private toggle** (private = only with invite code)
3. `POST /api/courses` with form data
4. Course created
5. User enrolled automatically
6. Share link generated (if public) or invite code (if private)
7. User redirected to empty course page with onboarding tips

#### 4.2.2 Join Course Flow
1. User searches by:
   - Course code
   - Course name
   - Paste invite code/link
2. System shows matching courses
3. User clicks "Join"
4. `POST /api/courses/[courseId]/enroll`
5. Enrollment created
6. WebSocket notifies other classmates: "👋 [Name] just joined!"
7. Course appears in user's dashboard

#### 4.2.3 Upload Course Outline Flow
1. User in course clicks "Upload Syllabus"
2. Drag & drop PDF/DOCX or paste text
3. File uploaded to S3
4. Background LangGraph workflow:
   - Parse document structure
   - Extract topics with week numbers
   - Identify key dates/deadlines
   - Create topic records
   - Queue pre-class research for each topic
5. Real-time progress shown to user
6. Notification: "🎉 Syllabus processed! Found 12 topics"
7. Topics auto-organized in sidebar

### 4.3 Note Management (Collaborative)

#### 4.3.1 Upload Notes Flow
1. User on topic page clicks "Add Notes"
2. Options:
   - ✍️ Type/paste markdown
   - 📄 Upload PDF/DOCX
   - 📸 Upload image (OCR)
   - 🔗 Paste URL (webpage clipper)
3. For uploads:
   - File to S3
   - Extract text (pdf-parse, mammoth, Tesseract)
   - Clean & format
4. **Chunking for RAG:**
   - Split into 500-1000 char chunks
   - Generate embeddings (Voyage AI)
   - Store in `note_chunks` with vectors
5. Note saved to DB
6. Background fact-check job queued
7. **WebSocket broadcast to all enrolled students:**
   ```json
   {
     "type": "note:created",
     "data": {
       "note_id": "uuid",
       "title": "Lecture 3 Notes",
       "uploaded_by": "Sarah",
       "topic": "French Revolution"
     }
   }
   ```
8. Toast notification for online users: "Sarah just shared notes on French Revolution!"

#### 4.3.2 View Notes Flow
1. User navigates to topic
2. `GET /api/topics/[topicId]/notes`
3. Notes displayed as cards:
   - Title & preview
   - Uploader avatar & name
   - Time ago
   - ✅ Verified badge (if fact-checked)
   - 💬 Quick AI actions: "Explain this" "Quiz me"
4. Click to expand:
   - Full content (markdown rendered)
   - Fact-check sidebar (if available)
   - Version history
5. Inline AI chat for that specific note

#### 4.3.3 Collaborative Editing
- Users can only edit their own notes
- Edit history tracked in `note_versions`
- When note updated:
  - Re-chunk and re-embed
  - Re-run fact check
  - Notify users who bookmarked it

### 4.4 Study Mode (Not Just Summaries!)

#### 4.4.1 Study Session Flow
1. User clicks "Study This Topic"
2. Study session created in `study_sessions`
3. **Study Mode UI appears:**
   - Timer in corner
   - Progress indicator
   - Notes on left, AI on right
4. **AI Study Partner greets user:**
   ```
   "Hey! Ready to master [Topic Name]? 🚀 
   I've got 3 notes from your classmates here. 
   Want to read through them, or should I quiz you on what you already know?"
   ```
5. User can:
   - Read notes normally
   - Ask AI to explain concepts
   - Generate practice questions
   - Take a quick quiz
   - Review previous test mistakes
6. **AI tracks engagement:**
   - Notes viewed
   - Concepts discussed
   - Questions answered
   - Time spent per section
7. When user leaves:
   - Session ends
   - Duration logged
   - Progress updated

#### 4.4.2 AI Explain Concept Flow
1. User selects text or asks question
2. **RAG workflow:**
   - Embed question (Voyage AI)
   - Vector search `note_chunks` (pgvector)
   - Retrieve top 5 relevant chunks
   - Fetch original notes for context
3. **LangGraph agent decides:**
   - Enough context in notes? → Answer directly
   - Needs external info? → Web search + synthesize
4. Claude generates response with:
   - Clear explanation
   - Examples from notes
   - Related concepts to explore
   - **Personality injection based on user preferences**
5. Stream to user with citations
6. Save to `ai_messages` for conversation continuity

**Example AI Response (Encouraging tone, moderate emoji):**
```
Great question! 🎯 Let me break down the French Revolution's causes for you.

Based on Sarah's notes from Lecture 3, there were 3 main factors:

1. **Economic Crisis** 💰
   France was basically broke. Years of wars + bad harvests = angry, hungry people.
   
2. **Social Inequality** ⚖️
   The nobles paid almost no taxes while peasants got crushed. Super unfair.
   
3. **Enlightenment Ideas** 💡
   Philosophers like Rousseau were spreading wild ideas about equality and rights.

Want me to quiz you on these, or dive deeper into any specific cause?

📚 Sources: Sarah's Lecture 3 Notes, Mike's textbook summary
```

#### 4.4.3 Practice Quiz Generation
1. User clicks "Quiz Me" on topic
2. Modal: "How many questions? What type?"
3. `POST /api/ai/generate-quiz`
4. **LangGraph workflow:**
   - Gather all notes for topic
   - Analyze key concepts
   - Generate diverse questions
   - Ensure coverage of important points
5. Questions saved to `tests` table
6. User starts quiz immediately or saves for later

### 4.5 Testing & Voice Grading

#### 4.5.1 Take Test Flow
1. User starts practice test
2. Test attempt created
3. Questions displayed
4. **For each question, user can:**
   - Type answer (traditional)
   - Record voice answer (click & hold)
   - Skip and come back
5. **Voice recording:**
   - Browser captures audio (Web Audio API)
   - Waveform visualization
   - Upload to S3
   - Transcription job queued (Whisper)
6. Submit test
7. Grading jobs queued

#### 4.5.2 Voice Answer Grading (LangGraph Workflow)

**Multi-step agent workflow:**

```
Step 1: Transcribe
├─→ Whisper API transcribes audio
├─→ Save transcription to test_answers
└─→ Proceed to Step 2

Step 2: Grade Answer
├─→ LangGraph agent loads context:
│   ├─ Question text
│   ├─ Expected answer
│   ├─ Transcribed student answer
│   └─ Grading rubric
├─→ Claude analyzes:
│   ├─ Concept understanding (main focus)
│   ├─ Key points covered
│   ├─ Key points missed
│   └─ Ignore filler words ("um", "like", rambling)
└─→ Proceed to Step 3

Step 3: Generate Feedback
├─→ Calculate score
├─→ Generate constructive feedback
├─→ **Add encouragement based on score:**
│   ├─ 90-100%: "🔥 Crushing it! You really get this!"
│   ├─ 70-89%: "💪 Solid! Just a couple things to tighten up."
│   ├─ 50-69%: "You're getting there! Let me help clarify..."
│   └─ <50%: "No worries, this is tough. Let's break it down together."
└─→ Save to test_answers

Step 4: Update Progress
├─→ Calculate overall test score
├─→ Update user_progress mastery level
├─→ Update streak if daily study
└─→ Notify user: "✅ Your test is graded!"
```

**Example AI Feedback:**

```
Score: 8.5/10 💪

What you nailed:
✅ Correctly identified all 3 main causes
✅ Great explanation of economic crisis
✅ Nice connection to Enlightenment ideas

What to work on:
📝 You mixed up the Estates-General and National Assembly timeline
💡 Pro tip: The Estates-General happened BEFORE they formed the National Assembly

Overall: You clearly understand the big picture! Just tighten up those dates.

Want to practice timeline questions? I can generate some!
```

### 4.6 Fact Checking (LangGraph Multi-Agent)

#### 4.6.1 Automatic Fact Check Workflow

**Triggered when:** Note uploaded or edited

**LangGraph Workflow:**

```
Agent 1: Claim Extractor
├─→ Claude identifies factual claims in note
├─→ Focus on: dates, names, statistics, events
├─→ Output: List of claims to verify
└─→ Pass to Agent 2

Agent 2: Research Agent (for each claim)
├─→ Search web (Serper API)
├─→ Filter results:
│   ├─ Prioritize .edu, .gov, .org
│   ├─ Scholarly sources
│   └─ High-authority domains
├─→ Fetch top 3 source pages (BeautifulSoup)
├─→ Extract relevant text snippets
└─→ Pass to Agent 3

Agent 3: Verification Agent
├─→ Claude analyzes sources
├─→ Determines: "Does source support claim?"
├─→ Assigns confidence score
├─→ If unclear/contradictory:
│   └─→ Loop back to Agent 2 for more sources
├─→ Generate explanation
└─→ Save to fact_checks

Agent 4: Report Generator
├─→ Aggregate all verifications
├─→ Create user-friendly summary:
│   ├─ ✅ Verified claims (green)
│   ├─ ⚠️ Disputed claims (yellow)
│   └─ ❌ Unverified claims (red)
└─→ Store final report
```

**Fact Check Display (Side Panel):**

```
📋 Fact Check Report

✅ VERIFIED (3)
─────────────
"Napoleon became Emperor in 1804"
  Confidence: 98%
  Sources: britannica.com, napoleon.org

"The revolution began in 1789"
  Confidence: 100%
  Sources: history.com, archives.gov.fr

⚠️ NEEDS REVIEW (1)
─────────────
"Over 40,000 people executed during Reign of Terror"
  Confidence: 60%
  Note: Estimates vary 16,000-40,000 across sources
  Sources: Show conflicting data
  
  💡 What to do: Check with professor or use the
      conservative estimate (16,000) in your answers.

❌ UNVERIFIED (0)

Last checked: 2 hours ago
```

### 4.7 Pre-Class Research Agent

**Triggered when:** Topic created from course outline

**LangGraph Workflow:**

```
Agent 1: Topic Analyzer
├─→ Parse topic title & description
├─→ Extract key terms
├─→ Determine academic level
└─→ Generate search queries

Agent 2: Research Agent
├─→ Search academic sources (Serper)
├─→ Prioritize:
│   ├─ Educational sites
│   ├─ Academic papers (Google Scholar results)
│   └─ Reputable encyclopedias
├─→ Fetch and parse top 5-7 sources
└─→ Extract key information

Agent 3: Synthesizer
├─→ Claude synthesizes findings into study guide:
│   ├─ "What is this topic?" (ELI5 intro)
│   ├─ Key definitions
│   ├─ Historical context (if relevant)
│   ├─ Important people/events
│   ├─ Why it matters today
│   └─ Common misconceptions
├─→ Format for easy reading
└─→ Include source citations

Agent 4: Concept Mapper (optional)
├─→ Extract key concepts
├─→ Identify relationships
└─→ Store in structured format for AI to reference
```

**Example Pre-Class Research Output:**

```
📚 Pre-Class Primer: The French Revolution

🎯 TL;DR
The French Revolution (1789-1799) was when France went from a 
monarchy to...well, chaos, then Napoleon. Think: angry peasants, 
guillotines, and a LOT of political drama.

🔑 KEY TERMS YOU NEED TO KNOW
• Ancien Régime - The old French system (monarchy + nobles ruling)
• Estates-General - Basically French parliament (hadn't met in 175 years!)
• Tennis Court Oath - Dramatic moment where they vowed to make a constitution
• Reign of Terror - The violent phase (Robespierre goes crazy with executions)

👥 MAIN CHARACTERS
• Louis XVI - The king (spoiler: loses his head 😬)
• Robespierre - Revolutionary leader, later tyrant
• Napoleon - Shows up at the end, takes over everything

⏱️ TIMELINE CHEAT SHEET
1789 - Revolution starts (Bastille stormed)
1792 - France becomes a republic (no more king)
1793-94 - Reign of Terror (yikes)
1799 - Napoleon takes power (revolution basically over)

💡 WHY THIS MATTERS
This revolution inspired democratic movements worldwide and 
basically invented modern political left vs. right.

⚠️ COMMON CONFUSION
Students often mix up the American & French Revolutions. 
Key difference: French Revolution was WAY more violent and 
radical. Americans wanted independence; French wanted to 
completely restructure society.

📖 Want More?
Check out the notes your classmates share after lecture,
or ask me anything!

Sources: britannica.com, history.com, crash-course-history
```

---

## 5. AI Agent Workflows & RAG Implementation

### 5.1 RAG Architecture

**Why RAG?**
- Students upload lots of notes
- Can't fit all notes in every prompt (token limits)
- Need semantic search ("explain revolutions" should find French + American Revolution notes)
- Need source attribution (which notes did this answer come from?)

**RAG Stack:**
- **Embeddings:** Voyage AI (`voyage-large-2-instruct`) - 1024 dimensions, optimized for retrieval
- **Vector Store:** PostgreSQL pgvector (simpler than separate Qdrant for MVP)
- **Chunking Strategy:** 500-1000 characters with 100 char overlap
- **Retrieval:** Top-k similarity search (k=5) + reranking

#### 5.1.1 Note Ingestion Pipeline

```python
# Pseudocode for note upload → RAG
async def ingest_note_for_rag(note_id: str, content: str):
    # 1. Chunk the content
    chunks = chunk_text(
        content,
        chunk_size=800,
        overlap=100,
        respect_sentences=True  # Don't split mid-sentence
    )
    
    # 2. Generate embeddings
    embeddings = await voyage_ai.embed(
        texts=[chunk.text for chunk in chunks],
        model="voyage-large-2-instruct",
        input_type="document"  # Not query
    )
    
    # 3. Store chunks with vectors
    for chunk, embedding in zip(chunks, embeddings):
        db.insert("note_chunks", {
            "note_id": note_id,
            "chunk_text": chunk.text,
            "chunk_index": chunk.index,
            "embedding": embedding,
        })
    
    return f"Ingested {len(chunks)} chunks"
```

#### 5.1.2 RAG Query Pipeline

```python
# Pseudocode for answering user question with RAG
async def answer_with_rag(
    question: str,
    topic_id: str,
    user_preferences: dict
) -> dict:
    # 1. Embed the question
    question_embedding = await voyage_ai.embed(
        texts=[question],
        model="voyage-large-2-instruct",
        input_type="query"  # Query, not document
    )[0]
    
    # 2. Vector similarity search
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
    # Prefer: recent notes, higher similarity, notes from multiple users
    reranked = rerank_chunks(similar_chunks)
    top_5 = reranked[:5]
    
    # 4. Build context for Claude
    context = "\n\n---\n\n".join([
        f"From {chunk.uploader}'s notes ({chunk.title}):\n{chunk.text}"
        for chunk in top_5
    ])
    
    # 5. Call Claude with personality
    personality_prompt = get_personality_prompt(user_preferences)
    
    response = await claude.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        system=f"""You are a helpful study AI assistant. {personality_prompt}

The student is studying a specific topic and has access to these notes from classmates:

{context}

Answer their question using the provided notes. If the notes don't have enough info, say so and offer to search the web for more. Always cite which classmate's notes you're referencing.""",
        messages=[
            {"role": "user", "content": question}
        ],
        stream=True
    )
    
    # 6. Return with citations
    return {
        "answer": response,
        "sources": [
            {"note_id": chunk.note_id, "title": chunk.title}
            for chunk in top_5
        ]
    }
```

### 5.2 LangGraph Agent Architectures

**Why LangGraph over plain LangChain?**
- State management across multi-step workflows
- Conditional routing (if X then Y else Z)
- Human-in-the-loop optional
- Better error handling and retries
- Graph visualization for debugging

#### 5.2.1 Fact Checker Agent (Multi-Step)

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class FactCheckState(TypedDict):
    note_id: str
    content: str
    claims: List[dict]
    verifications: List[dict]
    final_report: dict

# Define the graph
workflow = StateGraph(FactCheckState)

# Step 1: Extract Claims
def extract_claims(state):
    response = claude_call(
        f"Extract factual claims from this text: {state['content']}"
    )
    claims = parse_claims(response)
    return {"claims": claims}

# Step 2: Search for each claim
def search_claim(state):
    claim = state["claims"][0]  # Process one at a time
    results = serper_search(claim["text"])
    return {"search_results": results}

# Step 3: Verify claim
def verify_claim(state):
    verification = claude_verify(
        claim=state["claims"][0],
        sources=state["search_results"]
    )
    return {
        "verifications": state.get("verifications", []) + [verification],
        "claims": state["claims"][1:]  # Remove processed claim
    }

# Conditional: More claims to process?
def should_continue(state):
    return "search" if state["claims"] else "report"

# Step 4: Generate final report
def generate_report(state):
    report = aggregate_verifications(state["verifications"])
    return {"final_report": report}

# Build the graph
workflow.add_node("extract", extract_claims)
workflow.add_node("search", search_claim)
workflow.add_node("verify", verify_claim)
workflow.add_node("report", generate_report)

workflow.set_entry_point("extract")
workflow.add_edge("extract", "search")
workflow.add_edge("search", "verify")
workflow.add_conditional_edges(
    "verify",
    should_continue,
    {
        "search": "search",  # More claims? Loop back
        "report": "report"   # Done? Generate report
    }
)
workflow.add_edge("report", END)

# Compile and run
app = workflow.compile()
result = app.invoke({
    "note_id": "uuid",
    "content": "Napoleon died in 1820 on St. Helena..."
})
```

#### 5.2.2 Question Generator Agent

```python
class QuizGenState(TypedDict):
    topic_id: str
    notes: List[str]
    question_count: int
    difficulty: str
    question_types: List[str]
    generated_questions: List[dict]
    quality_score: float

# Step 1: Gather and analyze notes
def gather_notes(state):
    notes = db.get_topic_notes(state["topic_id"])
    return {"notes": [n.content for n in notes]}

# Step 2: Generate questions
def generate_questions(state):
    prompt = f"""Generate {state['question_count']} practice questions.
    
Difficulty: {state['difficulty']}
Types: {', '.join(state['question_types'])}
Coverage: Ensure all major concepts from notes are covered.

Notes:
{chr(10).join(state['notes'])}

Return JSON array of questions with:
- question_text
- question_type
- correct_answer
- answer_options (if MCQ)
- explanation
"""
    
    response = claude_call(prompt, response_format="json")
    questions = json.loads(response)
    return {"generated_questions": questions}

# Step 3: Quality check
def quality_check(state):
    # Check: diversity, coverage, no duplicates
    score = evaluate_questions(state["generated_questions"])
    return {"quality_score": score}

# Conditional: Good enough or regenerate?
def check_quality(state):
    return "save" if state["quality_score"] >= 0.75 else "regenerate"

def regenerate(state):
    # Provide feedback to improve
    feedback = generate_feedback(state["generated_questions"])
    # Loop back with feedback...
    pass

def save_questions(state):
    db.save_test(state["generated_questions"])
    return state

# Build graph...
workflow = StateGraph(QuizGenState)
workflow.add_node("gather", gather_notes)
workflow.add_node("generate", generate_questions)
workflow.add_node("quality", quality_check)
workflow.add_node("regenerate", regenerate)
workflow.add_node("save", save_questions)

workflow.set_entry_point("gather")
workflow.add_edge("gather", "generate")
workflow.add_edge("generate", "quality")
workflow.add_conditional_edges(
    "quality",
    check_quality,
    {"save": "save", "regenerate": "regenerate"}
)
workflow.add_edge("regenerate", "generate")
workflow.add_edge("save", END)
```

#### 5.2.3 Grader Agent (Voice-Aware)

```python
class GradingState(TypedDict):
    answer_id: str
    question: str
    expected_answer: str
    student_answer: str
    is_voice: bool
    transcription_quality: float
    grading_rubric: dict
    score: float
    feedback: str
    encouragement: str

# Step 1: Assess transcription (if voice)
def assess_transcription(state):
    if not state["is_voice"]:
        return {"transcription_quality": 1.0}
    
    # Check for errors, clarity
    quality = evaluate_transcription(state["student_answer"])
    return {"transcription_quality": quality}

# Step 2: Grade content
def grade_answer(state):
    prompt = f"""Grade this student answer.
    
Question: {state['question']}
Expected Answer: {state['expected_answer']}
Student Answer: {state['student_answer']}

{"IMPORTANT: This is transcribed speech. Ignore filler words, false starts, and focus ONLY on concept understanding." if state['is_voice'] else ""}

Rubric:
- Concept understanding: 70%
- Key points coverage: 20%
- Examples/support: 10%

Return JSON:
{{
  "score": 0-100,
  "key_points_covered": [...],
  "key_points_missed": [...],
  "feedback": "..."
}}
"""
    
    result = claude_call(prompt, response_format="json")
    return json.loads(result)

# Step 3: Generate encouragement
def add_encouragement(state):
    score = state["score"]
    
    if score >= 90:
        encouragement = random.choice([
            "🔥 Absolutely crushing it!",
            "💯 You really know your stuff!",
            "⭐ This is excellent work!"
        ])
    elif score >= 70:
        encouragement = random.choice([
            "💪 Solid answer! Just a few tweaks needed.",
            "👍 You're on the right track!",
            "📈 Good progress! Keep it up!"
        ])
    elif score >= 50:
        encouragement = random.choice([
            "🌱 You're getting there! Let's clarify a few things.",
            "💡 Good effort! Here's what to focus on...",
            "📚 Not bad! You've got the basics, now let's deepen your understanding."
        ])
    else:
        encouragement = random.choice([
            "🤔 This is tricky stuff! Let's break it down together.",
            "💭 No worries, this concept takes time. Want me to explain it differently?",
            "🔄 Let's try another approach to this topic."
        ])
    
    return {"encouragement": encouragement}

# Build graph...
workflow = StateGraph(GradingState)
workflow.add_node("assess", assess_transcription)
workflow.add_node("grade", grade_answer)
workflow.add_node("encourage", add_encouragement)

workflow.set_entry_point("assess")
workflow.add_edge("assess", "grade")
workflow.add_edge("grade", "encourage")
workflow.add_edge("encourage", END)
```

### 5.3 AI Personality System

**Personality Configuration (stored in user.study_personality):**

```python
PERSONALITY_TEMPLATES = {
    "tone": {
        "encouraging": {
            "system_addon": "Be warm, supportive, and motivating. Use positive reinforcement. When the student struggles, remind them that learning takes time and they're making progress.",
            "emoji_style": "friendly and motivating (🎯, 💪, 🌟, 📚, ✨)"
        },
        "direct": {
            "system_addon": "Be clear, concise, and to the point. Focus on facts and efficiency. Skip pleasantries and get straight to helping them learn.",
            "emoji_style": "minimal and purposeful (✓, ✗, →)"
        },
        "humorous": {
            "system_addon": "Be fun, engaging, and use appropriate humor to make learning enjoyable. Use analogies, pop culture references, and keep things light while staying educational.",
            "emoji_style": "playful and expressive (😂, 🤓, 🎉, 🤯, 👀)"
        }
    },
    "explanation_style": {
        "concise": "Keep explanations brief (2-3 sentences). Use bullet points. Focus on key takeaways.",
        "detailed": "Provide comprehensive explanations with examples, context, and connections to other concepts. Use analogies where helpful.",
        "visual": "Use diagrams, step-by-step breakdowns, and visual metaphors. Format with clear sections and spacing."
    }
}

def build_personality_prompt(user_prefs: dict) -> str:
    tone = PERSONALITY_TEMPLATES["tone"][user_prefs.get("tone", "encouraging")]
    explanation = PERSONALITY_TEMPLATES["explanation_style"][user_prefs.get("explanation_style", "detailed")]
    
    emoji_usage = user_prefs.get("emoji_usage", "moderate")
    emoji_instruction = {
        "none": "Do not use emojis.",
        "moderate": f"Use 1-2 emojis per response. Preference: {tone['emoji_style']}",
        "heavy": f"Use emojis liberally to make responses engaging. Preference: {tone['emoji_style']}"
    }[emoji_usage]
    
    return f"""
{tone['system_addon']}

Explanation style: {explanation}

Emoji usage: {emoji_instruction}

Remember: You're a study companion, not a lecturer. Adapt to the student's needs and make learning feel achievable.
"""
```

### 5.4 External Integrations

#### 5.4.1 Serper API (Web Search)
```python
import httpx

async def search_web(query: str, num_results: int = 10) -> List[dict]:
    """Search the web using Serper API"""
    response = await httpx.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_API_KEY},
        json={
            "q": query,
            "num": num_results,
            "gl": "us",  # Geographic location
            "hl": "en"   # Language
        }
    )
    
    results = response.json()
    
    # Filter and prioritize educational sources
    organic = results.get("organic", [])
    filtered = [
        r for r in organic
        if any(domain in r["link"] for domain in [".edu", ".gov", ".org"])
        or "wikipedia" in r["link"]
    ]
    
    return filtered or organic[:5]  # Fallback to top 5 if no .edu/.gov
```

#### 5.4.2 BeautifulSoup (Content Extraction)
```python
from bs4 import BeautifulSoup
import httpx

async def fetch_and_extract(url: str) -> str:
    """Fetch webpage and extract main content"""
    try:
        response = await httpx.get(url, timeout=10.0)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit length
        return text[:5000]  # First 5000 chars
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"
```

#### 5.4.3 Whisper API (Transcription)
```python
from openai import AsyncOpenAI

async def transcribe_audio(audio_file_path: str) -> dict:
    """Transcribe audio using OpenAI Whisper"""
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    with open(audio_file_path, "rb") as audio_file:
        transcription = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",  # Get timestamps, confidence
            language="en"
        )
    
    return {
        "text": transcription.text,
        "duration": transcription.duration,
        "language": transcription.language,
        "segments": transcription.segments  # For word-level timing
    }
```

---

## 6. API Specifications

### 6.1 Authentication Endpoints

#### POST /api/auth/register
```typescript
// Request Body
{
  "email": "user@example.com",
  "password": "securepass123",
  "full_name": "Alex Chen",
  "study_personality": {  // Optional
    "tone": "encouraging",
    "emoji_usage": "moderate",
    "explanation_style": "detailed"
  }
}

// Response (201)
{
  "token": "jwt_token_here",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "Alex Chen",
    "study_personality": {...}
  }
}
```

#### POST /api/auth/login
```typescript
// Request Body
{
  "email": "user@example.com",
  "password": "securepass123"
}

// Response (200)
{
  "token": "jwt_token_here",
  "user": { "id": "uuid", "email": "...", "full_name": "..." }
}
```

#### PATCH /api/users/me/personality
```typescript
// Request Body
{
  "tone": "humorous",
  "emoji_usage": "heavy",
  "explanation_style": "concise"
}

// Response (200)
{
  "message": "Personality updated! 🎉",
  "study_personality": {...}
}
```

### 6.2 Course Endpoints (Peer-to-Peer)

#### GET /api/courses
```typescript
// Response (200)
{
  "courses": [
    {
      "id": "uuid",
      "code": "HIST101",
      "name": "World History",
      "semester": "Fall 2026",
      "member_count": 24,
      "created_by": "uuid",
      "joined_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

#### POST /api/courses
```typescript
// Request Body
{
  "code": "HIST101",
  "name": "World History",
  "semester": "Fall 2026",
  "description": "Optional",
  "is_public": true  // false = private (requires invite code)
}

// Response (201)
{
  "course": {
    "id": "uuid",
    "code": "HIST101",
    "name": "World History",
    "invite_code": "HIST-2F4K-9X1L",  // If private
    "share_link": "https://notesos.com/join/HIST-2F4K-9X1L"
  }
}
```

#### POST /api/courses/join
```typescript
// Request Body (option 1: search)
{
  "search": "HIST101"
}

// OR (option 2: direct)
{
  "course_id": "uuid"
}

// OR (option 3: invite code)
{
  "invite_code": "HIST-2F4K-9X1L"
}

// Response (200)
{
  "message": "Welcome to World History! 👋",
  "course": {...},
  "classmates": 23  // Other enrolled students
}
```

#### GET /api/courses/:courseId
```typescript
// Response (200)
{
  "course": {...},
  "topics": [...],
  "members": [
    { "id": "uuid", "full_name": "Alex Chen", "avatar_url": "..." }
  ],
  "recent_activity": [
    {
      "type": "note_upload",
      "user": "Sarah Kim",
      "topic": "French Revolution",
      "timestamp": "2026-02-01T14:30:00Z"
    }
  ]
}
```

#### POST /api/courses/:courseId/outline
```typescript
// Multipart form-data
// Response (202)
{
  "message": "Processing syllabus...",
  "job_id": "uuid"
}

// WebSocket notification when complete:
{
  "type": "outline:processed",
  "data": {
    "topics_created": 12,
    "research_queued": true
  }
}
```

### 6.3 Note Endpoints

#### POST /api/topics/:topicId/notes
```typescript
// Request Body (text)
{
  "title": "Lecture 3 Notes",
  "content": "# French Revolution\n\n...",
  "content_type": "text"
}

// OR multipart for file upload

// Response (201)
{
  "note": {
    "id": "uuid",
    "title": "Lecture 3 Notes",
    "uploaded_by": {...},
    "created_at": "...",
    "chunks_created": 8,  // For RAG
    "fact_check_queued": true
  }
}
```

#### GET /api/topics/:topicId/notes
```typescript
// Query: ?page=1&limit=20&sort=recent

// Response (200)
{
  "notes": [
    {
      "id": "uuid",
      "title": "Lecture 3 Notes",
      "content_preview": "First 200 chars...",
      "uploaded_by": {
        "id": "uuid",
        "full_name": "Sarah Kim",
        "avatar_url": "..."
      },
      "is_verified": true,
      "fact_check_summary": {
        "verified": 5,
        "disputed": 1,
        "unverified": 0
      },
      "created_at": "2026-02-01T14:30:00Z",
      "view_count": 42
    }
  ],
  "pagination": {...}
}
```

#### GET /api/notes/:noteId
```typescript
// Response (200)
{
  "note": {
    "id": "uuid",
    "title": "...",
    "content": "Full markdown content",
    "uploaded_by": {...},
    "versions": [
      { "version_number": 2, "edited_at": "...", "edited_by": "..." }
    ],
    "fact_checks": [
      {
        "claim": "Napoleon died in 1820",
        "status": "disputed",
        "confidence": 0.6,
        "explanation": "Sources show he died in 1821",
        "sources": [...]
      }
    ]
  }
}
```

### 6.4 Study & AI Endpoints

#### POST /api/study/sessions
```typescript
// Start a study session
// Request Body
{
  "topic_id": "uuid"
}

// Response (201)
{
  "session": {
    "id": "uuid",
    "topic": {...},
    "started_at": "...",
    "ai_greeting": "Hey! Ready to dive into French Revolution? 🚀"
  }
}
```

#### POST /api/study/sessions/:sessionId/end
```typescript
// End study session
// Response (200)
{
  "session": {
    "id": "uuid",
    "duration_seconds": 2400,
    "notes_reviewed": 5,
    "concepts_covered": ["Causes", "Timeline", "Key Figures"],
    "ai_summary": "Great session! You spent 40 minutes and covered all the major concepts. 💪"
  },
  "progress_updated": true
}
```

#### POST /api/ai/chat
```typescript
// Request Body
{
  "conversation_id": "uuid",  // Optional, for continuing conversation
  "message": "What caused the French Revolution?",
  "context": {
    "topic_id": "uuid",
    "course_id": "uuid"
  }
}

// Response: Server-Sent Events (streaming)
event: message
data: {"type": "text", "content": "Great question! "}

event: message
data: {"type": "text", "content": "🎯 Let me break down"}

event: source
data: {"note_id": "uuid", "title": "Lecture 3 Notes"}

event: done
data: {"conversation_id": "uuid", "message_id": "uuid"}
```

#### POST /api/ai/explain
```typescript
// Explain specific concept with RAG
// Request Body
{
  "question": "Explain the Tennis Court Oath",
  "topic_id": "uuid",
  "use_web": false  // true = supplement with web search if needed
}

// Response (streaming SSE)
```

#### POST /api/ai/quiz
```typescript
// Generate practice quiz
// Request Body
{
  "topic_id": "uuid",
  "question_count": 10,
  "question_types": ["mcq", "short_answer"],
  "difficulty": "medium"
}

// Response (202)
{
  "message": "Generating your quiz... This might take 30 seconds.",
  "job_id": "uuid"
}

// WebSocket notification when ready:
{
  "type": "quiz:ready",
  "data": {
    "test_id": "uuid",
    "question_count": 10
  }
}
```

### 6.5 Test Endpoints

#### POST /api/tests/:testId/attempts
```typescript
// Start test attempt
// Response (201)
{
  "attempt": {
    "id": "uuid",
    "test": {...},
    "questions": [
      {
        "id": "uuid",
        "question_text": "...",
        "question_type": "mcq",
        "answer_options": ["A", "B", "C", "D"],
        "points": 10
      }
    ],
    "started_at": "..."
  }
}
```

#### POST /api/test-attempts/:attemptId/answers
```typescript
// Submit answer (text)
// Request Body
{
  "question_id": "uuid",
  "answer_text": "The causes were..."
}

// OR for voice (multipart)
FormData:
  question_id: uuid
  audio: blob

// Response (201)
{
  "answer": {
    "id": "uuid",
    "status": "submitted",
    "transcription_status": "processing"  // If voice
  }
}
```

#### POST /api/test-attempts/:attemptId/submit
```typescript
// Complete test
// Response (202)
{
  "message": "Test submitted! Grading your answers now... ⏱️",
  "attempt_id": "uuid",
  "estimated_time": "2-3 minutes"
}

// WebSocket notification when graded:
{
  "type": "test:graded",
  "data": {
    "attempt_id": "uuid",
    "total_score": 85.5,
    "message": "Great work! 💪 You scored 85.5%"
  }
}
```

#### GET /api/test-attempts/:attemptId
```typescript
// Get results
// Response (200)
{
  "attempt": {
    "id": "uuid",
    "test": {...},
    "total_score": 85.5,
    "max_score": 100,
    "completed_at": "...",
    "answers": [
      {
        "question": {...},
        "student_answer": "...",
        "transcription": "...",  // If voice
        "score": 8.5,
        "max_score": 10,
        "feedback": "You nailed the main causes! Just missed...",
        "encouragement": "💪 Solid answer! Just a few tweaks needed.",
        "key_points_covered": ["Economic crisis", "Social inequality"],
        "key_points_missed": ["Enlightenment influence"]
      }
    ],
    "overall_feedback": "Strong performance! Focus on timeline details for next time."
  }
}
```

### 6.6 Progress Endpoints

#### GET /api/progress
```typescript
// Get overall progress
// Response (200)
{
  "overview": {
    "total_study_time": 144000,  // Seconds
    "current_streak": 7,  // Days
    "longest_streak": 14,
    "courses_enrolled": 3
  },
  "courses": [
    {
      "course": {...},
      "avg_mastery": 0.78,
      "total_study_time": 86400,
      "test_scores": {
        "avg": 82.5,
        "highest": 95,
        "latest": 85
      },
      "topics": [
        {
          "topic": {...},
          "mastery_level": 0.85,
          "status": "Advanced",  // Beginner/Intermediate/Advanced/Mastered
          "study_sessions": 5,
          "total_study_time": 7200,
          "avg_test_score": 87.5,
          "last_studied": "2026-02-01T10:00:00Z"
        }
      ]
    }
  ],
  "recommendations": [
    {
      "type": "review",
      "topic": {...},
      "reason": "You haven't reviewed this in 5 days",
      "action": "Quick 10-minute review"
    },
    {
      "type": "practice",
      "topic": {...},
      "reason": "Low mastery (45%)",
      "action": "Take a practice quiz"
    }
  ]
}
```

#### GET /api/progress/streak
```typescript
// Get study streak details
// Response (200)
{
  "current_streak": 7,
  "longest_streak": 14,
  "calendar": {
    "2026-02": [
      { "date": "2026-02-01", "studied": true, "duration": 3600 },
      { "date": "2026-02-02", "studied": true, "duration": 2400 }
    ]
  },
  "message": "🔥 7 day streak! Keep it going!"
}
```

### 6.7 WebSocket Events

**Connection:**
```typescript
ws://api.notesos.com/ws?token=JWT_TOKEN&course_id=UUID
```

**Events Received:**

```typescript
// New note uploaded
{
  "type": "note:created",
  "data": {
    "note_id": "uuid",
    "title": "Lecture 5 Notes",
    "uploaded_by": {
      "id": "uuid",
      "full_name": "Sarah Kim"
    },
    "topic": {...}
  },
  "message": "Sarah just shared notes on French Revolution!"
}

// Someone joined course
{
  "type": "user:joined",
  "data": {
    "user": {
      "id": "uuid",
      "full_name": "Mike Chen"
    }
  },
  "message": "👋 Mike Chen just joined!"
}

// Test graded
{
  "type": "test:graded",
  "data": {
    "attempt_id": "uuid",
    "total_score": 85.5
  },
  "message": "✅ Your test is graded! You scored 85.5%"
}

// Quiz generated
{
  "type": "quiz:ready",
  "data": {
    "test_id": "uuid",
    "question_count": 10
  },
  "message": "🎯 Your practice quiz is ready!"
}

// Fact check complete
{
  "type": "fact_check:complete",
  "data": {
    "note_id": "uuid",
    "verified": 8,
    "disputed": 2,
    "unverified": 0
  }
}
```

---

## 7. Frontend Components & State Management

### 7.1 State Management (Zustand)

#### 7.1.1 Auth Store
```typescript
interface AuthStore {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (data: RegisterData) => Promise<void>;
  updatePersonality: (prefs: PersonalityPrefs) => Promise<void>;
}
```

#### 7.1.2 Course Store
```typescript
interface CourseStore {
  courses: Course[];
  currentCourse: Course | null;
  fetchCourses: () => Promise<void>;
  createCourse: (data: CreateCourseData) => Promise<Course>;
  joinCourse: (identifier: string) => Promise<void>;
  selectCourse: (courseId: string) => void;
}
```

#### 7.1.3 Study Session Store
```typescript
interface StudySessionStore {
  activeSession: StudySession | null;
  startSession: (topicId: string) => Promise<void>;
  endSession: () => Promise<StudySessionSummary>;
  isStudying: boolean;
  elapsedTime: number;  // Seconds
  notesReviewed: string[];  // Note IDs
}
```

#### 7.1.4 AI Chat Store
```typescript
interface AIChatStore {
  conversations: Map<string, Conversation>;  // topic_id -> conversation
  activeConversation: string | null;
  isStreaming: boolean;
  sendMessage: (message: string, context: Context) => Promise<void>;
  clearConversation: (conversationId: string) => void;
}
```

### 7.2 Key Component Specifications

#### 7.2.1 Dashboard Component
```typescript
// app/(dashboard)/page.tsx

export default function Dashboard() {
  return (
    <div className="grid grid-cols-12 gap-6">
      {/* Left: Courses */}
      <div className="col-span-8">
        <CourseGrid courses={courses} />
        <RecentActivity limit={5} />
      </div>
      
      {/* Right: Progress & Streak */}
      <div className="col-span-4">
        <StreakCard 
          currentStreak={7} 
          longestStreak={14}
          encouragement="🔥 You're on fire! 7 days strong!"
        />
        <ProgressOverview />
        <QuickActions />
      </div>
    </div>
  );
}

interface CourseGridProps {
  courses: Course[];
}

function CourseGrid({ courses }: CourseGridProps) {
  return (
    <div className="grid grid-cols-2 gap-4">
      {courses.map(course => (
        <CourseCard 
          key={course.id}
          course={course}
          showProgress
          showMembers
        />
      ))}
    </div>
  );
}
```

#### 7.2.2 Topic Study View (Three-Column Layout)
```typescript
// app/(dashboard)/courses/[courseId]/topics/[topicId]/page.tsx

export default function TopicStudyPage() {
  const { startSession, endSession, isStudying } = useStudySession();
  
  return (
    <div className="flex h-screen">
      {/* Left Sidebar: Pre-Class Research */}
      <aside className="w-80 border-r overflow-y-auto">
        <PreClassResearchPanel topicId={topicId} />
      </aside>
      
      {/* Center: Notes Feed */}
      <main className="flex-1 overflow-y-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <h1>{topic.title}</h1>
          <StudyButton 
            isStudying={isStudying}
            onStart={() => startSession(topicId)}
            onEnd={endSession}
          />
        </div>
        
        <NotesFeed topicId={topicId} />
      </main>
      
      {/* Right Sidebar: AI Chat */}
      <aside className="w-96 border-l flex flex-col">
        <AIChat topicId={topicId} courseId={courseId} />
      </aside>
    </div>
  );
}
```

#### 7.2.3 AI Chat Component
```typescript
interface AIChatProps {
  topicId: string;
  courseId: string;
}

function AIChat({ topicId, courseId }: AIChatProps) {
  const { sendMessage, isStreaming, activeConversation } = useAIChat();
  const [input, setInput] = useState('');
  
  const handleSend = async () => {
    await sendMessage(input, { topicId, courseId });
    setInput('');
  };
  
  return (
    <div className="flex flex-col h-full">
      {/* Personality indicator */}
      <div className="p-4 border-b bg-gradient-to-r from-blue-50 to-purple-50">
        <p className="text-sm text-gray-600">
          {user.study_personality.tone === 'encouraging' && "💪 Supportive mode"}
          {user.study_personality.tone === 'direct' && "🎯 Direct mode"}
          {user.study_personality.tone === 'humorous' && "😄 Fun mode"}
        </p>
      </div>
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(msg => (
          <MessageBubble 
            key={msg.id}
            message={msg}
            personality={user.study_personality}
          />
        ))}
        
        {isStreaming && <TypingIndicator />}
      </div>
      
      {/* Input */}
      <div className="p-4 border-t">
        <QuickActions 
          actions={[
            { label: "Quiz me", icon: "🎯", action: () => handleQuickAction('quiz') },
            { label: "Explain", icon: "💡", action: () => handleQuickAction('explain') },
            { label: "Summary", icon: "📝", action: () => handleQuickAction('summarize') }
          ]}
        />
        
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything about this topic..."
          className="w-full mt-2"
        />
        
        <button onClick={handleSend} disabled={isStreaming}>
          Send
        </button>
      </div>
    </div>
  );
}
```

#### 7.2.4 Voice Recorder Component
```typescript
interface VoiceRecorderProps {
  onRecordingComplete: (audioBlob: Blob) => void;
  maxDuration?: number;
}

function VoiceRecorder({ onRecordingComplete, maxDuration = 300 }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0);
  const [audioURL, setAudioURL] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  
  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream);
    mediaRecorderRef.current = mediaRecorder;
    
    const chunks: Blob[] = [];
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = () => {
      const blob = new Blob(chunks, { type: 'audio/webm' });
      setAudioURL(URL.createObjectURL(blob));
    };
    
    mediaRecorder.start();
    setIsRecording(true);
    
    // Timer
    const interval = setInterval(() => {
      setDuration(d => {
        if (d >= maxDuration) {
          stopRecording();
          return maxDuration;
        }
        return d + 1;
      });
    }, 1000);
  };
  
  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  };
  
  return (
    <div className="voice-recorder">
      {!audioURL ? (
        <div>
          <button 
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onTouchStart={startRecording}
            onTouchEnd={stopRecording}
            className="record-button"
          >
            {isRecording ? '🔴 Recording...' : '🎤 Hold to Record'}
          </button>
          {isRecording && <WaveformVisualizer />}
          <p>{formatTime(duration)} / {formatTime(maxDuration)}</p>
        </div>
      ) : (
        <div>
          <audio src={audioURL} controls />
          <button onClick={() => onRecordingComplete(audioBlob)}>
            Submit Answer
          </button>
          <button onClick={() => setAudioURL(null)}>
            Re-record
          </button>
        </div>
      )}
    </div>
  );
}
```

---

## 8. Security & Authentication

### 8.1 Authentication Strategy
- **JWT tokens:** Access (15 min expiry) + Refresh (7 days)
- **HttpOnly cookies:** Refresh tokens stored securely
- **Password hashing:** bcrypt with cost factor 12
- **Session management:** Redis for active sessions
- **Rate limiting:** Per-user, per-endpoint

### 8.2 Authorization (Peer Model)

**Key Principle:** Everyone is a student. No hierarchical permissions.

#### 8.2.1 Course Access
- Must be enrolled to view course content
- Anyone can create a course
- Course creator can:
  - Delete the course
  - Change course settings
  - (Cannot see others' private progress)

#### 8.2.2 Note Permissions
- **Upload:** Any enrolled student
- **Edit:** Only your own notes
- **Delete:** Only your own notes
- **View:** All enrolled students
- **Fact check:** Automatic, visible to all

#### 8.2.3 Progress Privacy
- **Own progress:** Full visibility
- **Others' progress:** None (privacy by default)
- **Course aggregates:** Only anonymous stats ("23 students, avg 78%")

### 8.3 API Security

```python
# Rate limiting configuration
RATE_LIMITS = {
    "/api/auth/login": "5 per 15 minutes",
    "/api/auth/register": "3 per hour",
    "/api/ai/*": "50 per hour",  # AI calls are expensive
    "/api/notes": "100 per hour",
    "global": "1000 per hour"
}

# Input validation with Pydantic
from pydantic import BaseModel, validator

class NoteCreate(BaseModel):
    title: str
    content: str
    
    @validator('title')
    def title_length(cls, v):
        if len(v) > 255:
            raise ValueError('Title too long')
        return v
    
    @validator('content')
    def content_length(cls, v):
        if len(v) > 100000:  # ~100KB
            raise ValueError('Content too long')
        return v
```

### 8.4 File Upload Security

```python
# File validation
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/png',
    'image/jpeg',
    'image/webp',
    'audio/webm',
    'audio/mp4',
    'audio/mpeg'
}

MAX_FILE_SIZES = {
    'note': 10 * 1024 * 1024,   # 10MB
    'audio': 50 * 1024 * 1024,  # 50MB
}

import magic

def validate_upload(file: UploadFile, category: str):
    # Check size
    if file.size > MAX_FILE_SIZES[category]:
        raise ValueError(f'File too large (max {MAX_FILE_SIZES[category]} bytes)')
    
    # Check MIME type
    mime = magic.from_buffer(file.read(2048), mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        raise ValueError(f'Invalid file type: {mime}')
    
    # Scan for viruses (optional, using ClamAV)
    if ENABLE_VIRUS_SCAN:
        scan_for_viruses(file)
    
    # Generate secure filename
    ext = file.filename.split('.')[-1]
    safe_filename = f"{uuid4()}.{ext}"
    
    return safe_filename
```

### 8.5 Data Privacy & GDPR

#### User Data Rights
- **Right to access:** GET /api/users/me/data (full export)
- **Right to deletion:** DELETE /api/users/me (cascade deletes)
- **Right to portability:** JSON export of all user data

#### Data Retention
- **Notes:** Indefinite (unless user deletes)
- **AI conversations:** 90 days
- **Study sessions:** 1 year
- **Test attempts:** Indefinite (unless user deletes)
- **Deleted notes:** 30-day soft delete, then permanent

---

## 9. Deployment & Infrastructure

### 9.1 Production Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Cloudflare                          │
│           (CDN, DDoS Protection, SSL)                   │
└────────────────────┬────────────────────────────────────┘
                     │
          ┌──────────┴───────────┐
          │                      │
          ▼                      ▼
┌──────────────────┐    ┌──────────────────┐
│  Vercel          │    │  Railway/Render  │
│  (Next.js)       │    │  (FastAPI)       │
│  - Static pages  │    │  - AI workflows  │
│  - API routes    │    │  - Background    │
│  - SSR           │    │    workers       │
└──────────────────┘    └────────┬─────────┘
          │                      │
          └──────────┬───────────┘
                     │
          ┌──────────┴────────────┐
          │                       │
          ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  Supabase/Neon   │    │  Upstash Redis   │
│  (PostgreSQL)    │    │  (Queue/Cache)   │
│  + pgvector      │    │                  │
└──────────────────┘    └──────────────────┘
          │
          ▼
┌──────────────────┐
│  Cloudflare R2   │
│  (Object Store)  │
└──────────────────┘
```

### 9.2 Environment Variables

#### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=https://api.notesos.com
NEXT_PUBLIC_WS_URL=wss://api.notesos.com/ws
NEXT_PUBLIC_ENV=production
```

#### Backend (.env)
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/notesos
REDIS_URL=redis://default:pass@host:6379

# Auth
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# AI Services
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
VOYAGE_AI_API_KEY=...
SERPER_API_KEY=...

# Storage
S3_ENDPOINT=https://....r2.cloudflarestorage.com
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=notesos-files
S3_PUBLIC_URL=https://files.notesos.com

# Features
ENABLE_FACT_CHECK=true
ENABLE_PRE_CLASS_RESEARCH=true
ENABLE_VOICE_GRADING=true
ENABLE_VIRUS_SCAN=false  # ClamAV (optional)

# Monitoring
SENTRY_DSN=https://...
SENTRY_ENVIRONMENT=production
```

### 9.3 Database Migrations

Using Alembic for PostgreSQL:

```bash
# Create migration
alembic revision --autogenerate -m "Add study sessions table"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

**Critical migrations:**
```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create vector index for RAG
CREATE INDEX idx_note_chunks_embedding 
ON note_chunks 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- Full-text search
CREATE INDEX idx_notes_fulltext 
ON notes 
USING GIN(to_tsvector('english', content));
```

### 9.4 Background Workers

**Worker Types:**
1. **Transcription Worker** - Processes voice recordings
2. **Fact Check Worker** - Verifies note claims
3. **Research Worker** - Pre-class topic research
4. **Embedding Worker** - Generates vectors for RAG
5. **Grading Worker** - Grades test answers

**Worker Configuration (BullMQ + Redis):**

```python
from bullmq import Worker, Queue

# Transcription worker
async def process_transcription(job):
    audio_url = job.data['audio_url']
    answer_id = job.data['answer_id']
    
    # Download audio from S3
    audio_data = await download_from_s3(audio_url)
    
    # Transcribe with Whisper
    transcription = await transcribe_audio(audio_data)
    
    # Save to database
    await db.update_answer(answer_id, {
        'transcription': transcription['text']
    })
    
    # Queue grading
    await grading_queue.add('grade', {
        'answer_id': answer_id
    })

transcription_worker = Worker(
    'transcription',
    process_transcription,
    connection=redis_conn
)

# Fact check worker
async def process_fact_check(job):
    note_id = job.data['note_id']
    
    # Run LangGraph workflow
    from agents.fact_checker import fact_check_workflow
    result = await fact_check_workflow.invoke({
        'note_id': note_id
    })
    
    # Save results
    await db.save_fact_checks(note_id, result['verifications'])
    
    # Mark note as verified
    await db.update_note(note_id, {'is_verified': True})
    
    # Notify via WebSocket
    await ws_notify(note_id, 'fact_check:complete')

fact_check_worker = Worker(
    'fact-check',
    process_fact_check,
    connection=redis_conn
)
```

### 9.5 Monitoring & Logging

#### Application Monitoring
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=SENTRY_DSN,
    environment=SENTRY_ENVIRONMENT,
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,  # 10% of transactions
)
```

#### Logging
```python
import structlog

logger = structlog.get_logger()

# Usage
logger.info(
    "note_uploaded",
    note_id=note.id,
    topic_id=note.topic_id,
    user_id=user.id,
    chunk_count=len(chunks)
)
```

#### Metrics (Prometheus)
```python
from prometheus_client import Counter, Histogram

note_uploads = Counter(
    'note_uploads_total',
    'Total note uploads',
    ['topic', 'content_type']
)

ai_request_duration = Histogram(
    'ai_request_duration_seconds',
    'AI API request duration',
    ['agent_type']
)

# Usage
note_uploads.labels(topic='French Revolution', content_type='text').inc()
ai_request_duration.labels(agent_type='grader').observe(2.5)
```

### 9.6 CI/CD Pipeline

**.github/workflows/deploy.yml**
```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          pip install -r requirements.txt
          pytest tests/

  deploy-frontend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v20
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}

  deploy-backend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Railway
        run: |
          railway up -d
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}

  migrate:
    needs: [deploy-backend]
    runs-on: ubuntu-latest
    steps:
      - name: Run migrations
        run: |
          alembic upgrade head
```

---

## 10. Development Phases & Milestones

### 10.1 Phase 1: Foundation (Weeks 1-2)

#### Week 1: Database & Auth
**Tasks:**
- [x] Set up PostgreSQL + pgvector
- [x] Create all 18 tables with migrations
- [x] Implement JWT auth (access + refresh tokens)
- [x] Build registration/login APIs
- [x] Next.js project setup with App Router
- [x] Basic auth UI (login/register pages)

**Deliverable:** Working auth system, database ready

#### Week 2: Core Course Management
**Tasks:**
- [x] Course CRUD APIs
- [x] Peer-to-peer enrollment system
- [x] Invite codes & share links
- [x] Topic creation and management
- [x] Dashboard UI with course grid
- [x] Basic course view

**Deliverable:** Users can create/join courses, see topics

### 10.2 Phase 2: Notes & RAG (Weeks 3-4)

#### Week 3: Note Upload & Chunking
**Tasks:**
- [x] S3 integration (Cloudflare R2)
- [x] Text note creation
- [x] File upload (PDF, DOCX, images)
- [x] OCR with Tesseract
- [x] Text extraction (pdf-parse, mammoth)
- [x] **Chunking pipeline**
- [x] **Voyage AI embeddings integration**
- [x] **Store chunks in note_chunks with vectors**

**Deliverable:** Notes uploaded and chunked for RAG

#### Week 4: RAG Implementation
**Tasks:**
- [x] Vector similarity search (pgvector)
- [x] RAG query pipeline
- [x] Basic AI chat with RAG
- [x] Notes feed UI
- [x] Note card component
- [x] WebSocket real-time updates

**Deliverable:** Working RAG system, notes visible to all

### 10.3 Phase 3: AI Agents (Weeks 5-7)

#### Week 5: LangGraph Setup & Study Mode
**Tasks:**
- [x] LangGraph + LangChain setup
- [x] Study session tracking
- [x] AI personality system
- [x] Basic chat agent
- [x] Streaming responses (SSE)
- [x] Study mode UI

**Deliverable:** Students can study with AI chat

#### Week 6: Question Generator & Testing
**Tasks:**
- [x] Question generator LangGraph workflow
- [x] Test creation APIs
- [x] MCQ & short answer support
- [x] Test attempt flow
- [x] Test UI components
- [x] Answer submission

**Deliverable:** AI generates and serves practice quizzes

#### Week 7: Fact Checker & Researcher
**Tasks:**
- [x] Serper API integration
- [x] BeautifulSoup content extraction
- [x] Fact checker LangGraph workflow (multi-agent)
- [x] Researcher LangGraph workflow
- [x] Course outline parser
- [x] Background workers (BullMQ + Redis)
- [x] Fact check UI (side panel)
- [x] Pre-class research UI

**Deliverable:** Automatic fact-checking and research

### 10.4 Phase 4: Voice & Grading (Weeks 8-9)

#### Week 8: Voice Recording
**Tasks:**
- [x] Voice recorder component (Web Audio API)
- [x] Waveform visualization
- [x] Audio upload to S3
- [x] Whisper API integration
- [x] Transcription worker

**Deliverable:** Students can record voice answers

#### Week 9: AI Grading System
**Tasks:**
- [x] Grader LangGraph workflow
- [x] Voice-aware grading (ignore filler)
- [x] Personality-based encouragement
- [x] Grading worker
- [x] Results display UI
- [x] Detailed feedback UI

**Deliverable:** Full voice grading pipeline

### 10.5 Phase 5: Progress & Polish (Weeks 10-12)

#### Week 10: Progress Tracking
**Tasks:**
- [x] Progress calculation logic
- [x] Mastery level algorithm
- [x] Study streak tracking
- [x] Progress dashboard UI
- [x] Charts & visualizations (Recharts)
- [x] Recommendations engine

**Deliverable:** Students see their progress

#### Week 11: Polish & Optimization
**Tasks:**
- [x] UI/UX refinement
- [x] Mobile responsiveness
- [x] Loading states everywhere
- [x] Error handling & toasts
- [x] Performance optimization
- [x] Accessibility (a11y)
- [x] Dark mode (optional)

**Deliverable:** Polished, production-ready app

#### Week 12: Testing & Launch
**Tasks:**
- [x] E2E tests (Playwright)
- [x] Load testing (k6)
- [x] Bug fixes
- [x] Documentation
- [x] Deploy to production
- [x] Beta launch with your coursemates
- [x] Gather feedback

**Deliverable:** Live app, beta users onboarded

---

## Appendix A: Technology Decisions

### A.1 Why Next.js 14 App Router?
- **Server Components** for better performance (less client JS)
- **Streaming SSR** for AI responses
- **Built-in API routes** (don't need separate Express server)
- **File-based routing** (intuitive, scalable)
- **Vercel deployment** (zero-config, edge functions)

### A.2 Why Python FastAPI?
- **Async-first** (perfect for AI API calls, I/O-bound tasks)
- **Type hints** (better code quality, auto-documentation)
- **Fast execution** (comparable to Node.js)
- **Rich AI ecosystem** (LangChain, LangGraph, Anthropic SDK)
- **Easy integration** with ML/AI libraries

### A.3 Why LangGraph over LangChain alone?
- **State management** across multi-step workflows
- **Conditional routing** (if fact unclear → search again)
- **Debuggability** (visualize agent execution graph)
- **Error recovery** (retry failed steps)
- **Human-in-the-loop** (optional user confirmations)

### A.4 Why PostgreSQL + pgvector?
- **RAG in one database** (no separate Qdrant/Pinecone needed for MVP)
- **ACID compliance** (data integrity for grades, progress)
- **JSONB** (flexible schema for metadata, sources)
- **Full-text search** + **vector search** in one place
- **Mature ecosystem** (tools, hosting, scaling)

### A.5 Why Claude Sonnet 4.5?
- **Educational content** (excellent at explaining concepts)
- **Reasoning** (grading requires nuance, not just pattern matching)
- **Long context** (200k tokens = fit entire course notes if needed)
- **Fast** (low latency for streaming chat)
- **Personality** (can adapt tone based on user preferences)

---

## Appendix B: Future Enhancements (Post-MVP)

### B.1 Advanced AI Features
- **Spaced repetition** flashcards (auto-generated)
- **Concept maps** (visualize topic relationships)
- **Learning path** recommendations (what to study next)
- **Adaptive difficulty** (questions get harder as you improve)
- **Peer comparison** (anonymous: "You're in top 25%")

### B.2 Collaboration Features
- **Live study rooms** (video chat + shared notes)
- **Discussion threads** on notes
- **Annotations & highlights** (collaborative markup)
- **Study group creation** (private channels within course)
- **Peer tutoring** matching (connect students who excel with those who need help)

### B.3 Integrations
- **Calendar sync** (Google/Outlook - automatic study reminders)
- **LMS integration** (import from Canvas, Blackboard, Moodle)
- **Video lecture** analysis (YouTube/Zoom → auto-generate notes)
- **Notion export** (sync notes to Notion workspace)
- **Anki export** (generate Anki flashcard decks)

### B.4 Mobile App
- **React Native** (iOS + Android)
- **Offline mode** (sync when online)
- **Push notifications** (classmate uploaded notes, quiz ready)
- **Quick voice notes** (record while walking to class)

### B.5 Gamification (Optional, Privacy-Conscious)
- **Achievement badges** ("Fact Checker", "Study Streak Master")
- **Streaks** (daily study goals)
- **Anonymous leaderboards** (opt-in only)
- **Study challenges** (weekly topic mastery challenges)

---

## Document End

**This is your blueprint. Follow it, build it, and ship it. 🚀**

**Remember:**
- Students are peers, not teacher vs. student
- AI has personality, not corporate blandness  
- Study mode > summary mode
- Voice grading ignores rambling
- Facts are verified, not just displayed
- Progress is private, not public

**Good luck! Now go build NotesOS and help students actually learn. 💪**

