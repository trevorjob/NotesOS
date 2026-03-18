# NotesOS — Product Specification (v3)

## 1. Product Overview

NotesOS is an **AI-powered collaborative learning system** that transforms messy class materials into **structured knowledge and study experiences**.

Instead of being a note-taking tool, NotesOS acts as:

* a **shared knowledge hub for students**
* an **AI learning engine**
* a **memory reinforcement system**

### Core Idea

Students upload materials from class:

* notes
* lecture recordings
* slides
* PDFs
* whiteboard photos

The system processes them using AI and generates:

* structured knowledge
* explanations
* quizzes
* audio learning
* active recall prompts

These materials are **shared across the class**, allowing one student’s upload to benefit everyone.

---

# 2. Core Product Philosophy

NotesOS follows four principles:

### 1. Topic First

Users study **topics**, not files.

Files are just raw inputs.

### 2. AI Does the Organization

Students should not manage:

* folders
* file systems
* links

AI automatically organizes knowledge.

### 3. Learning > Storage

The system is optimized for:

```
learning
understanding
memory
exam preparation
```

Not document storage.

### 4. Shared Knowledge

Courses act as **shared knowledge hubs** where students contribute materials.

---

# 3. Core User Types

### Students

Primary users.

Capabilities:

* join courses
* upload materials
* study topics
* take quizzes
* record spoken answers

---

### Course Creators

Students or instructors who create courses.

Capabilities:

* create course spaces
* invite students
* manage topics

---

### Contributors

Students who upload materials.

Their contributions improve the shared knowledge base.

---

# 4. System Structure

Visible structure:

```
Workspace
   → Courses
        → Topics
```

Example:

```
School

Biology 201
   Photosynthesis
   Cell Structure
   DNA Replication

Chemistry 101
   Organic Reactions
   Energy Transfer
```

This hierarchy is intentionally simple to reduce friction.

---

# 5. Topic Page (Core Surface)

The **topic page** is where users spend most of their time.

Example:

```
Biology / Photosynthesis
```

Topic page sections:

### Knowledge Layer

AI-generated summary of the topic.

Example:

Key ideas

* Photosynthesis converts light energy into chemical energy
* Occurs in chloroplasts
* Light reactions produce ATP
* Calvin cycle produces glucose

---

### Study Tools

AI-generated learning tools.

```
▶ Learn Mode
🎧 Listen Mode
❓ Quiz
🎤 Speak Answer
🧠 Key Points
```

These tools are automatically created when materials are added.

---

### Sources (Collapsed)

Original materials.

Example:

Sources (4)

* Lecture recording
* Slides PDF
* Whiteboard photo
* Personal notes

These exist for reference but are not the main interface.

---

# 6. Resource Types

Topics support multiple input types.

### Text

* typed notes
* pasted notes

### Documents

* PDFs
* slides
* lecture documents

### Images

* whiteboard photos
* handwritten notes

Processed using OCR.

### Audio

* lecture recordings
* voice notes

Processed using transcription.

---

# 6. The Final Product Architecture

```
Home
↓

Courses
↓

Topics
↓

Knowledge
↓

Study Tools
```

Everything else supports this flow.


---

# 7. AI Processing Pipeline

When materials are uploaded, the system performs the following:

### Step 1: Ingestion

Content is uploaded.

### Step 2: Processing

The system performs:

```
transcription (audio)
OCR (images)
text extraction (PDF)
```

### Step 3: Knowledge Extraction

AI extracts:

```
concepts
definitions
relationships
important facts
```

### Step 4: Knowledge Merging

All information becomes **topic knowledge**.

### Step 5: Learning Asset Generation

AI generates:

```
key points
quiz questions
audio scripts
recall prompts
```

---

# 8. Study Tools

## Learn Mode

Primary learning feature.

AI provides structured mini-lesson.

Flow:

```
concept explanation
example
highlight key point
ask question
pause
reveal answer
```

Duration:

2–5 minutes.

---

## Listen Mode

Passive learning system.

Memory loop format:

```
concept
definition
question
pause
answer
```

Designed for studying while:

* walking
* commuting
* exercising

---

## Quiz Mode

Generates questions from topic knowledge.

Possible formats:

* multiple choice
* short answer
* concept identification
* definition recall

---

## Speak Answer

User records spoken explanation.

AI evaluates answer.

Example output:

```
Score: 7/10

Missing concepts:
- Calvin cycle
- ATP production
```

This simulates oral exam preparation.

---

## Key Points

Quick summary of important facts.

Used for fast review sessions.

---

# 9. Automatic Topic Connections

AI extracts concepts from each topic.

Example:

Photosynthesis concepts:

```
chloroplast
ATP
light reactions
Calvin cycle
```

If other topics share concepts, the system displays:

```
Related Topics

Cell Respiration
ATP Cycle
Energy Reactions
```

This creates a **second-brain style knowledge network**.

Users never manage links manually.

---

# 10. Shared Learning System

Courses act as **shared knowledge hubs**.

Example:

Biology 201

Members:

```
72 students
1 lecturer
```

Students can upload materials to topics.

Example contributions:

```
Lecture slides (Alex)
Voice recording (Sarah)
Whiteboard photo (Daniel)
Personal notes (Emma)
```

The AI merges these into topic knowledge.

One upload benefits the entire class.

---

# 11. Personal Learning Layer

Even though materials are shared, learning progress is personal.

Each student tracks:

```
quiz results
review history
voice answer scores
studied topics
```

Shared knowledge, personal learning.

---

# 12. Home Screen Design

The app opens like a **notebook you left open**, not a SaaS dashboard.

Example:

Continue Studying

```
Biology / Photosynthesis
▶ Resume Learn Mode
```

Below:

Recent Topics

```
Photosynthesis
Cell Structure
Derivatives
```

Quick Action:

```
+ Add Material
```

Minimal interface.

---

# 13. Exam Packs (Optional Feature)

Exam packs allow students to group topics across courses.

Example:

Biology Midterm

Topics:

```
Photosynthesis
Cell Structure
Cell Respiration
```

Exam pack generates:

```
review sessions
quiz flows
audio recap
practice explanations
```

This supports exam preparation.

---

# 14. Data Architecture

Internal system structure:

```
Course
   → Topic
        → Resources
        → Extracted Concepts
        → Knowledge Summary
        → Study Assets
```

Study assets include:

```
quiz questions
audio scripts
recall prompts
key points
```

---

# 15. Core Learning Loop

The platform reinforces memory through repetition.

Study flow:

```
Learn
↓
Recall
↓
Test
↓
Review
```

Example session:

```
Learn Mode
↓
Quiz
↓
Speak Answer
↓
Listen Review
```

---

# 16. Network Effect

The system improves as more students contribute.

```
more uploads
↓
better topic knowledge
↓
better quizzes
↓
better learning
```

Courses become **collective knowledge bases**.

---

# 17. Product Positioning

NotesOS is positioned as:

**“The AI that turns class materials into something you actually remember.”**

Not:

* note-taking software
* file storage
* AI chatbot

---

# 18. MVP Scope

First version should include:

Core features:

```
courses
topics
material upload
AI knowledge extraction
Learn Mode
Quiz
Listen Mode
```

Later features:

```
voice answer grading
exam packs
advanced review systems
contribution ranking
```

---

# 19. Long-Term Vision

NotesOS evolves into:

* a **shared academic knowledge network**
* an **AI learning companion**
* a **memory reinforcement system**

Goal:

Reduce the effort required to turn class materials into **true understanding and recall**.

