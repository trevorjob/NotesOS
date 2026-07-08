# **NotesOS — Product Brief**

*Living document. Last updated: May 2026\.*

---

## **1\. What NotesOS Is**

A research-backed study partner built on proven principles of how memory and learning actually work. Not a note-taking app — a learning app that uses notes as raw material.

Students already take notes. NotesOS takes those notes, merges them into a shared class intelligence, and turns them into active learning tools — audio, quizzes, AI chat. The notebook is the input. The learning is the output.

**Vision:** Be the first tool students reach for when trying to understand something in school.

**Current focus:** University students. Nigeria-first, with global expansion planned.

**Planned offshoot:** NotesOS for general learners — same engine, no class/course structure.

---

## **2\. Core Philosophy**

Two things that inform every product decision:

**Shared resources, personal progress.** One person uploads notes — everyone in the class gets them. One person generates a quiz — everyone can attempt it. The Consolidated Note is the class's shared intelligence. Scores, personal progress, and study history are private to each user. This is non-negotiable.

**Built on learning science.** The features exist because of research on how memory works — retrieval practice, spaced repetition, passive reinforcement. Difficulty is a feature, not a flaw. The product is not trying to feel like a game.

---

## **3\. Entity Architecture**

School → Cohort/ degree (optional) → Semester → Course → Topic \-\> resources

**School** Students pick from a curated list of universities. If their university isn't on the list, they can type it in — the input is formatted consistently before saving to prevent duplicates (e.g. "University of Lagos" not "Unilag" or "UNILAG").

**Cohort, set, classmates (dont really know what to call it yet)** \- DEGREE / MAJOR PROGRAM  *(g*roup of students moving through school together, identified by graduation/starting year — e.g. "2026 Set", "computerscience@2027 Set". Self-organizing, no owner. Students in the same cohort share a social layer: they see each other's activity, contributions, and class memberships.

Cohort is optional. Students can join courses directly without being part of a named cohort. But if a cohort exists and they're in it, course discovery and social context flow through it.

How it works:

* When a new course is created within a cohort, cohort members are notified and can choose to join.  
* Students can join all courses at once or pick individually.  
* Anyone can create a course — there is no cohort ownership of a course.

**Semester** A label only. Born automatically when the first course is created. No separate creation flow. Organises courses chronologically — "Second Semester 2024/2025" etc.

**Course** The atomic shared unit. Defined by name \+ course code \+ semester. Anyone can create one. On creation, the app checks for existing courses at the same school with a similar name or code and surfaces them — "Did you mean this?" — to keep the class in one shared space rather than fragmented across duplicates.

**Topic** The primary study unit. Everything happens here: Consolidated Note, Listen Mode, Quizzes, AI Chat. Topics live inside courses.

Resources the upload made by students, the raw materials

---

## **4\. Discovery**

NotesOS is not a discovery app. There is no public search or browse.

The two ways to access a course or cohort:

1. You create it.  
2. You join via contact discovery or a direct invite.

**Contact Discovery** On signup, users sync their contacts. The app shows which contacts are already on NotesOS and what classes they're in — modelled on how TikTok and Snapchat handle contact visibility. The app feels alive before a user has done anything.

The pull: "3 of your contacts are in BIO201 — join them?", "Muna is in computer science@2021 set— join them?"

For contacts not yet on the platform, users can invite directly. The incentive is built-in — the more classmates join, the richer the shared notes and the lower the group pricing.

**Growth loop:** Contact import → see classmates → join their class → invite those not on yet → notes get richer → group pricing drops → everyone has more reason to stay.

---

## **5\. Shared Resource Model**

**Shared (class-level):**

* Consolidated Note  
* Quizzes (anyone generates, anyone attempts)  
* Uploaded notes and resources  
* Notifications about new additions

**Private (user-level):**

* Quiz scores and performance history  
* Personal study progress and time  
* Any personal notes or annotations

**On social signals:** Activity that is visible — "3 classmates have already attempted this quiz", "Adaeze added new notes to Photosynthesis" — is always aggregate or action-based, never score-based. No score is ever surfaced to another user as a product feature. Students can show each other their own screens, but the app does not facilitate it.

---

## **6\. Learning Tools**

The current set of learning tools:

**Consolidated Note** AI-merged knowledge from all materials uploaded to a topic. Multiple students upload different angles of the same lecture — the Merge Agent synthesises them into one document. Updated in the background whenever new materials arrive.

**Listen Mode** Audio loop: concept → definition → question → \[pause\] → answer. Designed for commutes, walks, background listening. Generated from the Consolidated Note.

**Quizzes** AI-generated retrieval practice per topic. Anyone can generate a quiz; everyone can attempt it. Scores are private. Difficulty is intentional.

**AI Chat** Ask questions about a topic's material. Grounded in the Consolidated Note.

**Focus Mode** Full-screen reading view of the Consolidated Note.

**Merge Agent** Background worker. Re-synthesises the Consolidated Note when new uploads arrive. Not a user-facing feature.

The set of learning tools is not fixed. New tools, formats, and features will be added over time. The above is what exists or is being built now.

---

## **7\. Social Layer**

**Activity Feed** Class-level activity: who added notes, who created a quiz, how many classmates have attempted something. Always aggregate or action-based — never score-based.

**Notifications** High-signal only:

* New notes added to a topic  
* New quiz available  
* Classmates online / studying

No generic nudges. Notifications reflect things classmates actually did.

**Contribution Visibility** Students can see how many people contributed to a Consolidated Note. This creates social proof ("this topic is well-covered") and natural accountability — without rankings or leaderboards.

---

## **8\. Pricing**

**Structure: group-dynamic individual pricing** Individual price that drops automatically as more paying classmates join the same class. No group plan to coordinate.

| Paying members in class | Price per user |
| ----- | ----- |
| 1 | $5.00 |
| 5 | $3.50 |
| 15+ | $2.00 (floor) |

Floor is hard. Discount counts paying members only — not just anyone in the class.

**Localised pricing** Pricing to local purchasing power — same model as Netflix, Spotify, Notion. Nigeria: \~₦2,000. US: \~$8. Tiers and floors are market-adjusted.

**Gifting** Users can pay for other people's subscriptions. Supports peer gifting and parent-pays-for-student.

**Pioneer incentive** The first person to create a class pays full price before others join. A reward for being first — exact mechanic not yet defined.

---

## **9\. MVP Scope**

Full product, no payment gate. All features above are either built or being built for the first mobile release.

Payment infrastructure and logic are present but not actively pushed. The product launches in free early access — build the user base and the flywheel first.

---

## **10\. Non-Negotiables**

1. **Notebook feel.** The product feels like opening a notebook, not launching an app.

2. **Minimum entry friction.** One action to start a session. The goal is to make starting so small it happens before the brain decides not to.

3. **Difficulty is a feature.** Quizzes are hard on purpose. The product does not apologise for this or hide it.

4. **Shared resources are felt, not discovered.** It should always be clear that the Consolidated Note and quizzes come from collective class intelligence — not just the user's own materials.

5. **No gamification.** No streaks, no points, no daily check-in rewards. Progress means calibration — how well what you think you know matches what you can actually recall.

6. **Performance is always private.** Contribution is visible. Scores never are.

