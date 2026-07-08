# **Learning Science — NotesOS Design Constraints**

**A living document. Last updated: May 2026\.** *These aren't just background reading — they're design constraints. Each principle has a product question the interface needs to answer.*

---

## **How to use this doc**

Every section follows the same structure: what the research says, why it matters for the product, and an open question for the interface. When new research comes in, add it. When a product question gets answered, note how. This doc should get messier over time — that's the point.

---

## **Part 1 — The myth of learning styles**

**Learning styles are not real. The research has settled this.**

The idea that students are "visual learners" or "auditory learners" — and that matching instruction to their style improves outcomes — has been tested repeatedly and consistently fails. A 2023 meta-analysis across 21 studies found that matching instruction to learning style produced an effect in only 26% of measures, and even then the effect was too small to justify the approach. No study has shown that teaching to a self-identified learning style produces better retention, better test scores, or better outcomes in children or adults.

What does exist is *preference* — people genuinely prefer certain formats. But preference and performance are different things, and the research shows they don't reliably track each other. More concerning: learning style labels have been shown to actively bias how teachers, parents, and students themselves judge academic potential — effectively capping expectations based on a fictional category.

The useful version of this insight isn't "modalities don't matter" — it's that *combining* modalities (text \+ audio \+ visuals \+ practice) is better than any single one, for everyone, regardless of preference.

**Product question**

NotesOS serves content through multiple formats — notes, audio, quizzes. The temptation is to let users pick their "mode." But if learning styles don't predict outcomes, should the app steer users toward combinations rather than letting them self-select into comfort zones? What does a "multi-modal by default" session look like?

---

## **Part 2 — The most effective learning formats (ranked by evidence)**

**Two strategies dominate everything else: retrieval practice and spaced repetition.**

A meta-analysis across 242 studies, 1,619 effect sizes, and 169,000+ participants reached a clear conclusion: distributed practice and practice testing are the most effective learning techniques by significant margins. Everything else is downstream.

The full evidence-ranked list of high-leverage strategies:

* **Retrieval practice** — actively recalling information from memory, not reviewing it. Every act of retrieval strengthens the memory trace. The effort is the mechanism.  
* **Spaced repetition** — spreading study across time with increasing gaps between sessions. Memory consolidates in the gaps, not during the sessions.  
* **Interleaving** — mixing topics or problem types within a session rather than finishing one before starting another. Feels harder, produces significantly better long-term retention.  
* **Elaborative interrogation** — asking "why is this true?" rather than just reading what is true. Forces structural encoding rather than surface familiarity.  
* **Dual coding** — pairing verbal and visual representations of the same concept. Creates redundant retrieval pathways.  
* **Concrete examples** — grounding abstract principles in specific cases the learner can reason from.

Strategies with low evidence: re-reading, highlighting, summarising, keyword mnemonics. These feel productive. They are not.

**Product question**

NotesOS currently surfaces retrieval through quizzes and audio loops. Interleaving is the least implemented — the app is organised around single topics studied in sequence. Could a "mixed session" mode serve interleaving systematically? Would users trust it, or would it feel like disorder?

---

## **Part 3 — Retrieval practice**

*(see also: Part 2\)*

**Testing yourself beats rereading. Every time.**

Research consistently shows that actively trying to recall information produces far stronger retention than rereading — even when rereading feels more productive. Students who test themselves outperform those who reread, often dramatically, on delayed recall. The effect holds across subjects, age groups, and test formats. It also holds when students generate *wrong* answers, as long as correct feedback follows — the failed attempt primes encoding when the answer arrives.

The counterintuitive part: retrieval practice feels worse than rereading during the session. It's slower, more frustrating, and produces lower confidence. But performance days or weeks later is dramatically higher. Students routinely choose the strategy that feels better and perform worse as a result.

**Product question**

How do you make retrieval feel as effortless as rereading, even though it's fundamentally harder? The Consolidated Note reads smoothly — that smoothness is a trap. What makes a user want to quiz themselves instead of just scrolling?

---

## **Part 4 — The fluency illusion**

**Recognising something is not the same as knowing it.**

When you reread notes, the brain interprets smooth processing as mastery. The material feels familiar, so you feel like you know it. This is the fluency illusion — and it's one of the most consistent findings in learning science. Students who study by rereading consistently overestimate their own performance on subsequent tests. They feel prepared. They are not.

The illusion creates a dangerous feedback loop: retrieval practice feels hard → learner interprets hardness as not knowing → learner switches back to rereading → rereading feels smooth → learner feels confident → learner fails the test. The illusion actively punishes the strategies that work and rewards the ones that don't.

The fix is calibration — closing the loop between what students think they know and what they can actually demonstrate. Frequent low-stakes testing, prediction before tests, and seeing actual vs. predicted performance over time are the interventions with the best evidence. Disfluency (making material slightly harder to process) also reduces the illusion by forcing the brain out of the familiarity heuristic.

**Product question**

How might NotesOS make the absence of retrieval feel incomplete? When a user reads through a Consolidated Note without attempting any recall, should something in the UI signal that the loop isn't closed? And what would a calibration view look like — not "how much have you studied" but "how accurate is your self-assessment"?

---

## **Part 5 — Spaced repetition**

*(see also: Part 2\)*

**Spacing study across time beats cramming — even with the same total hours.**

Memory consolidates in the gaps between study sessions, not during the sessions themselves. Students who spread their study out significantly outperform those who mass it close to an exam, even when total time is equivalent. The forgetting curve is real: without reinforcement, retention drops sharply within 24–48 hours. Spaced repetition exploits this by scheduling reviews at increasing intervals — each review at the moment of near-forgetting does more consolidation work than a review when the memory is still fresh.

The expanding interval model (gaps that grow over time: 1 day → 3 days → 1 week → 2 weeks) has strong research support. Crucially, the *difficulty* of retrieving after a longer gap is the mechanism — a harder retrieval strengthens the memory more than an easy one.

**Product question**

NotesOS has no memory of when a user last engaged with a topic. Should the app surface "it's been 5 days since you reviewed this"? Can Listen Mode become the natural daily touchpoint that spaces exposure without requiring deliberate effort?

---

## **Part 6 — Desirable difficulty**

**Learning that feels hard is the learning that sticks.**

Conditions that slow down learning and feel worse in the short term actually produce stronger, more durable retention. This is Robert Bjork's concept of "desirable difficulties" — study strategies that impair performance during practice but significantly improve delayed performance. Spacing, interleaving, and retrieval practice all qualify. They feel harder, produce more errors, and generate less confidence during a session. They also produce dramatically better outcomes a week or a month later.

This is the direct inverse of what most students believe about studying. Students consistently choose strategies that feel more productive (rereading, re-watching lectures, cramming) and perform worse. The difficulty isn't a signal of poor design or insufficient knowledge — it is the mechanism of encoding.

**Product question**

Users said quizzes were "hard" and it felt broken. But hard is correct. How should the app frame difficulty as a feature rather than a flaw? Can the design communicate "this is supposed to feel hard" in a way that builds trust rather than frustration? What would difficulty as a progress signal look like?

---

## **Part 7 — Forgetting is a feature**

**Forgetting and then recovering a memory makes it more durable than never forgetting it.**

This is one of the most important and least understood findings in learning science. Robert Bjork's theory separates memory into two independent variables: *storage strength* (how deeply encoded something is) and *retrieval strength* (how easily accessible it is right now). These are separate. The key insight: when retrieval strength drops (forgetting occurs) and you successfully recover the memory, storage strength increases more than it would have if you'd never forgotten. Forgetting and re-learning isn't starting over — it's how deep encoding actually works.

This reframes the forgetting curve entirely. The curve doesn't show failure — it shows the mechanism. Cramming keeps retrieval strength artificially high without building storage strength. Spaced repetition lets retrieval strength fall, then rebuilds it, which is what builds durable memory.

Forgetting also enables *updating*. When a memory is retrieved, it briefly becomes unstable — the reconsolidation window — and can be modified by new information encountered at that moment. Forgetting \+ retrieval \+ new input \= integration. This is how knowledge structures get refined, not just accumulated.

**Product question**

What if NotesOS surfaced a concept's retrieval history — how many times it's been forgotten and recovered — as a badge of durability rather than a record of failure? A concept you've forgotten and recovered three times is your most battle-tested knowledge. Does the architecture track retrieval attempts per concept in a way that could support this kind of display?

---

## **Part 8 — Metacognitive calibration**

**Students are bad at knowing what they don't know. This is trainable.**

Research on metacognition consistently shows that low-performing students overestimate their knowledge, while high performers are better calibrated. The core problem isn't just not knowing — it's not knowing that you don't know. Calibration is the gap between predicted and actual performance, and it's one of the largest single barriers to effective self-regulated learning.

The good news: calibration is a skill, not a trait. Interventions that improve it are well-documented. Having students predict their performance before a test, then compare prediction to result, improves calibration over time — especially for students who start with the worst accuracy. Repeated exposure to the gap between perceived and actual mastery is the training mechanism.

The fluency illusion (Part 4\) is the most common source of miscalibration: smooth rereading inflates confidence without building recall. Students who use retrieval practice tend to have better-calibrated confidence, because the difficulty of retrieval gives them more accurate signal about what they actually know.

**Product question**

The current progress page shows a number that users can't interpret. What if progress was reframed as calibration — showing not just "how much you've studied" but "how accurate your self-assessment has been"? What would that actually look like on a screen? And how do you show improvement in calibration over time as a meaningful metric?

---

## **Part 9 — Elaborative interrogation**

**Asking "why" forces deeper encoding than re-reading facts.**

Prompting learners to explain why a fact is true — rather than just reading it — significantly improves retention. The act of connecting new information to existing knowledge is what creates durable memory structure. Passive exposure delivers facts into isolation. "Why" questions force the brain to build structure around them — relating the new fact to prior knowledge, finding mechanisms, constructing causal chains.

This matters differently across subjects. In history, "why did this happen?" forces narrative structure. In biology, "why does this process work this way?" forces mechanistic understanding. In maths, "why does this method work?" forces conceptual grounding rather than procedural mimicry. In each case, the elaboration is what distinguishes remembering a fact from understanding a concept.

**Product question**

NotesOS currently generates factual quizzes. Could it also generate "why" questions — prompts that ask users to explain connections rather than recall definitions? How does that change what the quiz feedback screen needs to show? And how do you evaluate a "why" answer — there's no clean right/wrong binary?

---

## **Part 10 — Passive learning (when it works)**

**Passive learning is real. It is not a replacement for retrieval, but it performs a specific function.**

The research distinguishes between two types of passive learning. Passive as in no active recall (re-reading, re-watching) — this performs poorly and has been studied extensively. Passive as in low-effort exposure (listening, background repetition, incidental contact) — this is different, and the evidence is more favourable than commonly assumed.

The mechanism: repeated passive exposure to material that has already been actively encoded reinforces weak memory traces. It doesn't build new memories from scratch effectively, but it significantly strengthens existing ones. Vocabulary research shows measurable retention from incidental exposure alone, with linear improvement as the number of encounters increases — without any intentional memorisation effort.

Three conditions determine whether passive learning works: (1) *prior active encoding* — there must be at least one active encounter first; (2) *repetition across varied contexts* — single-pass passive exposure has weak effects; (3) *proximity to sleep* — passive exposure in the hour before sleep hits a neurologically distinct consolidation window. The brain replays encoded material during NREM sleep, and material encountered close to sleep is preferentially consolidated.

Audio specifically: studies using EEG to measure actual brain attention found that podcast learning while walking produced equivalent attention to textbook reading while seated, and better immediate learning gain on two of three topics tested.

**Product question**

NotesOS's Listen Mode is already audio-based and low-friction. Does the app have any awareness of *when* in a user's day the loop is running? If it did, could it weight evening sessions differently — prioritising concepts the user has had prior active encounters with, to maximise what sleep consolidates?

---

## **Part 11 — Starting friction (activation energy)**

**The barrier to starting is neurological, not motivational. Reducing it is a design problem.**

The amygdala registers novel or uncertain tasks as mild threats before the prefrontal cortex has assessed whether they're actually hard. The result: avoidance kicks in before engagement begins. Once started, the Zeigarnik effect takes over — incomplete tasks create an open loop in working memory that the brain is motivated to close. Sustained effort is rarely the problem. Starting is.

Implementation intentions research (Gollwitzer) shows that specifying *when, where, and how* you'll start (not just *that* you will) dramatically reduces starting friction. The specificity pre-loads the decision: when the moment arrives, there's almost no activation energy required because the choice has already been made. "I'll study tonight" fails. "I'll open NotesOS on the bus after work" has a dramatically higher completion rate.

The practical implication: the front door of any learning tool should require the minimum possible decision. The more a user has to *decide* to study, the higher the drop-off. The goal is to make the first action so small it bypasses the threat response entirely, then let momentum carry the session.

**Product question**

Does the current entry flow into NotesOS feel more like "opening a notebook" or "deciding to study"? What is the smallest possible first action — one question, one card, one concept — that could serve as a micro-entry point and let the Zeigarnik loop do the rest?

---

## **Part 12 — Skill-based vs. content-heavy vs. language learning**

**Different subjects engage different memory systems, which means different strategies apply.**

The brain uses fundamentally different memory systems for different types of learning, and optimal strategy follows that distinction:

**Skill-based (maths, coding, STEM problem-solving)** encodes primarily into *procedural memory* — the same system used for riding a bike. Slow to build, highly durable once established, resistant to forgetting. The optimal strategy is *varied practice over repetitive practice*: interleaving problem types beats drilling a single type, even though it feels less efficient. Pre-testing (working a problem before seeing the solution, even without prior knowledge) also significantly improves retention.

**Content-heavy (history, psychology, biology facts)** encodes primarily into *declarative memory* — explicit, verbalizable knowledge. Faster to acquire but far more vulnerable to forgetting without reinforcement. The highest-leverage strategy is *elaborative interrogation* — asking why, building causal structure, connecting facts to existing knowledge networks. Facts stored in isolation decay. Facts stored in a relational network survive.

**Language learning** is split across both systems. Vocabulary and meaning: declarative. Grammar, syntax, phonology: procedural. This is why you can't explain rules you use fluently — the grammar is procedural and outside conscious access. The implication: grammar study (declarative approach) produces knowledge you can discuss but not use automatically. Exposure-based learning (listening, reading, output) produces communicative competence. The goal is to move grammar from the declarative to the procedural system, which only happens through volume of meaningful input and output — not rule memorisation.

All three subjects share the same high-level principles: retrieval practice, spaced repetition, and interleaving work across the board. What changes is what *counts* as retrieval — problem-solving for skills, self-testing for content, speaking and writing for language.

**Product question**

NotesOS currently treats all topics identically. Should the app recognise subject type and adjust its approach — more output-oriented sessions for language topics, more problem-generation for STEM topics, more "why" questions for content-heavy topics? What would subject-aware session design look like?

---

## **Part 13 — Study apps: what the research actually shows**

**Most study apps optimise for engagement, not learning. These are not the same thing.**

The apps that work are the ones built on retrieval practice and spaced repetition. The apps that don't work are the ones that allow users to stay passive. Effect sizes for apps like Quizlet in vocabulary learning are moderate and real (g \= 0.62–0.74). Apps that are essentially spaced retrieval systems (Anki) show some of the strongest real-world outcomes of any study tool — but also some of the worst retention and churn, because they are deliberately uncomfortable.

The fluency illusion hits hardest in app design: smooth, frictionless, rewarding sessions feel like learning and often aren't. One study found that spaced repetition flashcard software left exam performance statistically unchanged while significantly improving student confidence. The app made students *feel* like better learners without making them *perform* like better learners.

Churn data is the clearest verdict on the industry. Duolingo — the best-performing edtech app by retention — has a 28% monthly churn rate in Western markets. Simply Piano: 64%. Babbel: 58%. Duolingo's retention is closer to Roblox and Candy Crush than to any other learning app. Educational apps as a category have the lowest user retention rates of all mobile app categories.

The drop-off pattern: almost 50% churn by day 7\. Users who complete 3+ lessons on day 1 have a 50% higher retention rate at day 30\. The first few sessions are almost entirely determinative.

**Product question**

Most apps measure the wrong thing — streaks, time spent, sessions completed. These are engagement proxies, not learning proxies. What if NotesOS tracked knowledge decay — whether a concept encountered three days ago can still be recalled today — rather than study streaks? Would that change how Listen Mode is structured?

---

## **Part 14 — Personalised vs. group learning**

**Personalised learning works in theory. In practice, the group does more than it gets credit for.**

Bloom's "2-sigma problem" is the ceiling case: one-on-one tutoring produces learning gains two standard deviations above the classroom average. That's the maximum case for personalisation. Most adaptive learning software delivers 0.2–0.3 sigma — because the *social scaffolding* of a classroom is doing work that software doesn't replicate. Peer explanation, social stakes, observational learning from watching others struggle — these are real mechanisms that group settings activate.

The research verdict: personalised pacing combined with group accountability outperforms either alone. The problem with traditional schooling isn't the group structure — it's the fixed pace (locked to the median student) and the absent feedback loops.

Self-paced learning specifically tends to underperform structured learning for a systematic reason: metacognitive illusion. When learners control their own pace, they unconsciously speed through hard material (it's uncomfortable) and slow down on easy material (it feels productive). This is backwards. External structure forces time on hard content; self-direction allows avoidance of it.

**Product question**

NotesOS is built on shared resources — students in the same class contribute materials to a shared topic, and the Consolidated Note and quizzes are class-level assets, not personal ones. This is already closer to the optimal model than most tools get. The question is whether the *experience* communicates this. Beta users were surprised to discover quizzes were shared — they assumed personal. If the shared-resource nature were felt as a feature rather than discovered by accident, would it change contribution behaviour? Would students upload more materials knowing their notes become the class's shared intelligence?

---

## **Part 15 — Collaborative and peer learning**

**Learning with and from peers is not a soft benefit — it's a hard mechanism.**

The research on collaborative learning consistently shows that explaining concepts to others is one of the highest-leverage encoding strategies available. The "protégé effect" is well-documented: students who teach material outperform students who study for themselves, because teaching forces retrieval, reorganisation, and identification of gaps in understanding. You can only explain what you actually understand. The act of finding an explanation is itself the learning event.

Peer discussion activates something solo studying cannot: *socially-triggered elaboration*. When someone challenges or questions your understanding, it forces you to rebuild the explanation from a different angle — which strengthens the memory trace in ways self-review doesn't. This is distinct from just studying in a group; the mechanism requires genuine exchange, not parallel solo studying in the same room.

The other key finding: social comparison drives effort. Students calibrate their own effort against what they perceive their peers are doing. This isn't just motivational — it's metacognitive. Knowing that classmates are contributing to a shared resource, or that a topic has multiple contributors, changes how seriously an individual takes their own engagement with it.

There's also a *collective intelligence* effect on the resource itself. When multiple students contribute notes on the same topic from different lectures, different note-taking angles, different prior knowledge — and those are synthesised — the resulting resource is often more complete and accurate than any individual's notes. The Merge Agent is doing something epistemically significant here, not just organisationally useful.

The risk: social loafing — individuals contributing less when they believe others will carry the load. This is well-studied and shows up reliably in group contexts without accountability structures. The counter is *visibility of individual contribution*, not just collective output.

**Product question**

The Consolidated Note already embeds collaborative intelligence — many students' materials merged into one. But does the UI make that visible? Does a student know how many people contributed to the note they're reading, and what they contributed? Visibility of peer contribution could function as both social proof ("this topic is well-covered") and accountability ("I haven't added anything yet"). What would contribution transparency look like without becoming a leaderboard?

---

## **Open questions (unresolved)**

These are threads worth pulling on. No clear product answer yet.

* **Cognitive load management**: Working memory is the bottleneck for new encoding. How much information should NotesOS surface per session before it hits diminishing returns? Is there a "session size" that the research can inform?

* **Subject-aware design**: Should the app detect or ask about subject type and adapt accordingly? What's the minimum signal needed to do this usefully?

* **The calibration UI**: Calibration as a metric (predicted score vs. actual score over time) is well-supported in the research. Nobody has built a great UI for it. What would that screen look like?

* **The forgetting badge**: If a concept has been forgotten and recovered multiple times, it's more durable than one reviewed without forgetting. Can this be surfaced in a way that feels rewarding rather than exposing?

* **Timing-aware sessions**: The sleep consolidation research suggests the hour before sleep is a neurologically different window. Can the app know what time it is relative to the user's likely sleep schedule and adjust what it serves?

---

*Add new sections below as research accumulates.*

