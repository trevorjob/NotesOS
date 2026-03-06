# NoteOS — Backend Implementation Prompt (v2)
*Corrected and updated following architecture decisions*

Give this prompt to Copilot in full. Implement all sections in order, following existing codebase patterns and conventions.

---

### 1. AUTH — Forgot / Reset Password

**Model changes on `User`:**
- Add `password_reset_token: string | null`
- Add `password_reset_expires: datetime | null`

**New endpoints:**
- `POST /api/auth/forgot-password`
  - Accepts: `{ email: string }`
  - Generates a secure time-limited reset token, stores it on the user record, sends a reset email
  - Always returns 200 regardless of whether email exists (do not leak user existence)
  - Returns: `{ message: "If that email exists, a reset link has been sent." }`

- `POST /api/auth/reset-password`
  - Accepts: `{ token: string, new_password: string }`
  - Validates token (exists + not expired), hashes and updates password, invalidates token
  - Returns: `{ message: "Password updated successfully." }`

---

### 2. AUTH — Google OAuth

**Model changes on `User`:**
- Add `google_id: string | null` (unique, nullable)
- Add `avatar_url: string | null` if not already present

**New endpoints:**
- `GET /api/auth/google` — Redirects to Google OAuth consent screen
- `GET /api/auth/google/callback` — Handles callback, finds or creates user by google_id/email, returns access + refresh tokens same as standard login

---

### 3. SEMESTERS — New Core Model

This is a new optional grouping layer that sits above courses. Courses can exist without a semester, but a semester always contains courses.

**New model: `Semester`**
```
id: uuid (primary key)
owner_id: uuid (foreign key → User) — the user who created this semester
name: string — free text, user defined (e.g. "Fall 2025", "2025/2026 First Semester", "Term 1")
start_date: date | null
end_date: date | null
invite_code: string (unique, auto-generated on creation, non-expiring)
created_at: datetime
updated_at: datetime
```

**New join model: `SemesterMember`**
```
id: uuid
semester_id: uuid (foreign key → Semester)
user_id: uuid (foreign key → User)
joined_at: datetime
role: enum("OWNER", "MEMBER") — owner is the user who created it
```

**Model changes on `Course`:**
- Add `semester_id: uuid | null` (foreign key → Semester, nullable — courses can exist without a semester)

**New endpoints:**

- `POST /api/semesters`
  - Accepts: `{ name, start_date?, end_date? }`
  - Creates the semester, auto-generates invite_code, adds creator as OWNER in SemesterMember
  - Returns: full semester object including invite_code

- `GET /api/semesters`
  - Returns all semesters the current user is a member of (owned + joined)
  - Includes member count and course count per semester

- `GET /api/semesters/{semester_id}`
  - Returns semester detail: name, dates, invite_code (only visible to OWNER), members list, courses list

- `PATCH /api/semesters/{semester_id}`
  - Owner only. Accepts: `{ name?, start_date?, end_date? }`
  - Updates semester metadata

- `DELETE /api/semesters/{semester_id}`
  - Owner only. Deletes semester (courses become standalone — set semester_id to null, do not delete courses)

- `POST /api/semesters/join`
  - Accepts: `{ invite_code: string }`
  - Finds semester by invite_code, adds user as MEMBER in SemesterMember
  - Automatically enrolls user in all courses currently inside that semester
  - Returns: semester object + list of courses joined

- `GET /api/semesters/{semester_id}/members`
  - Returns list of all members in the semester with their name and joined_at

- `POST /api/semesters/{semester_id}/courses/{course_id}`
  - Assigns an existing standalone course to a semester (owner only)

- `DELETE /api/semesters/{semester_id}/courses/{course_id}`
  - Removes a course from a semester (makes it standalone again, does not delete course)

---

### 4. COURSE — Aggregate Completion + Last Studied

**Endpoint changes:**
- Update `GET /api/courses` to include per course:
  - `completion_percentage: number` — derived from UserProgress across all topics
  - `last_studied: { topic_id, topic_name, studied_at } | null` — most recent UserProgress entry
  - `semester_id: uuid | null` — so the frontend can group by semester

**New endpoint:**
- `GET /api/courses/{course_id}/summary`
  - Returns: `{ completion_percentage, last_studied_topic: { id, name, studied_at } | null }`

---

### 5. TOPIC — Aggregate Completion + Status

**Endpoint changes:**
- Update `GET /api/topics/{topic_id}` to include:
  - `completion_percentage: number` — derived from UserProgress for this topic
  - `status: "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED"` — derived from completion_percentage

---

### 6. TEST ANSWERS — Status Field + Key Points

**Model changes on `TestAnswer`:**
- Add `status: enum("CORRECT", "PARTIAL", "NEEDS_REVIEW") | null`

**Grading worker changes:**
- After grading, derive and store status based on score:
  - `CORRECT` = score >= 0.85
  - `PARTIAL` = score >= 0.5 and < 0.85
  - `NEEDS_REVIEW` = score < 0.5
- Properly populate `key_points_covered` and `key_points_missed` — remove hardcoded empty arrays

---

### 7. TESTS — Aggregate Stats Endpoint

**New endpoint:**
- `GET /api/tests/stats?course_id=`
  - Returns: `{ average_score: number, tests_completed: number, study_streak: number }`
  - `study_streak` = consecutive days user has taken at least one test for this course

---

### 8. TESTS — Save Draft

**New endpoint:**
- `POST /api/tests/{test_id}/draft`
  - Accepts: `{ answers: [ { question_id, answer_text?, answer_audio_url?, selected_option? } ] }`
  - Saves without submitting or grading
  - Returns: `{ saved_at: datetime }`

---

### 9. NOTIFICATIONS

**New model: `Notification`**
```
id: uuid
user_id: uuid (foreign key → User)
type: enum("TEST_GRADED", "AI_SUMMARY_READY", "INVITE_ACCEPTED", "GENERAL")
title: string
body: string
is_read: boolean (default false)
metadata: jsonb | null (e.g. { test_id, course_id, semester_id })
created_at: datetime
```

**New endpoints:**
- `GET /api/notifications` — Returns all notifications for current user, newest first
- `PATCH /api/notifications/{id}/read` — Mark single notification as read
- `PATCH /api/notifications/read-all` — Mark all as read

**WebSocket changes:**
- When grading worker completes: create a Notification record and push via WebSocket as:
  `{ type: "notification", data: { id, type, title, body, metadata } }`
- When a user joins a semester via invite: send notification to semester owner
  `{ type: "notification", data: { type: "INVITE_ACCEPTED", title: "...", body: "..." } }`

---

### 10. USER PREFERENCES + PERSONALITY TAGS

**Model changes on `User`:**
- Add `preferences: jsonb | null`
  ```json
  {
    "email_notifications": true,
    "focus_mode": false,
    "dark_theme": false
  }
  ```
- Add `personality_tags: string[] | null` (e.g. `["visual_learner", "night_owl", "pomodoro"]`)

**New endpoint:**
- `PATCH /api/users/me/preferences`
  - Accepts: `{ preferences?, personality_tags? }`
  - Updates and returns the updated user object

---

## Implementation Notes

- Follow existing model conventions, migration patterns and file structure throughout
- All new endpoints must be protected by existing auth middleware unless explicitly marked public
- All datetime fields stored as UTC
- `invite_code` on Semester should be a short, readable, unique string (e.g. 8 char alphanumeric)
- Run and apply all migrations after model changes
- When a semester is deleted, courses become standalone (semester_id → null) — never cascade delete courses
- Update API documentation if it exists in the codebase
