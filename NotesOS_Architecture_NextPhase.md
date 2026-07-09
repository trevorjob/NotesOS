# NotesOS — Architecture & Governance
Next-phase planning doc. July 2026.

## The reframe

We kept treating the cohort as a level in the hierarchy (School → Cohort → Semester → Course) and it kept breaking, because it doesn't behave like one. Parent nodes own what sits under them. The cohort owns nothing, has no owner, and is optional. It was wearing a costume that didn't fit.

There are two graphs here, and we'd been drawing them as one.

The institutional map is objective: school, course, topic, resources. It exists whether or not a single student signs up. The enrolment layer is subjective and per-student: the courses you're actually in, and the classmates that produces. It's not a map, it's your position on the map.

Set / degree lives in the second layer. That's why it can't own courses and can't sit above them in the tree. A course is an institutional fact. A set is a lens onto those facts. They reference each other; neither contains the other.

## The set is emergent, not computed

The earlier model computed the set top-down from program plus entry year plus school. That only holds where everyone in "Computer Science 2027" takes the same courses in lockstep. True in Nigeria, true in India's batch system, weak in the UK, basically false in the US where students pick freely and declare a major late. Build on it and the product only works in one kind of country.

Invert it. Don't compute the set from attributes. Let it emerge from shared course enrollment. Your classmates are the people in your courses, and that's true everywhere. Where education is cohort-based, the graph clusters tight on its own (the same fifty people keep appearing across your courses, so the set is dense). Where it's credit-based, it stays loose and per-course, which is how an American student actually experiences school. One design, no country branching. It responds to how much people's course-loads overlap instead of assuming they overlap.

This kills the two-set problem too. There's no rigid container to belong to one or two of. There's your course memberships and the graph they produce. Your feed is your courses. If those courses split into two friend-groups, the graph shows both, and nobody decides which set "owns" a course.

## Entity model

The universal spine:

School → Course → Topic → Resources

Course is the atomic join unit and the only thing you actively join. It's keyed on an opaque internal ID, never on the course code (see below). Topic is the atomic learning unit; Consolidated Note, Listen Mode, Quizzes, and AI Chat all live there, unchanged. A term / semester is an arrangement label that groups the courses you're taking in a period so you can plan around exams. It's born with the first course, no creation flow.

Everything Nigeria-shaped moves to optional metadata: program, level, entry year, code structure, tight lockstep cohorts. The design uses these signals when they're present and ignores them when they aren't. School and program still get collected at signup as grouping signals, they're just no longer load-bearing for correctness.

## Why the course code can't be the key

Codes aren't structured or consistent, even in Nigeria, and they disagree completely across borders. "CS 101," UK module codes, Indian formats, none line up. So the code can't be a primary key, and it can't tell you the level. It's one hint among several, nothing more.

Dedup runs on fuzzy matching instead, which is the proximity check below. Level leaves the spine entirely: it's local metadata, a tag where a country uses it, absent where it doesn't. The thing level was going to buy us (surfacing next term's relevant courses in the dead season) comes from behaviour instead: "courses your classmates are enrolling in for next term." No parsing.

## The proximity check (core primitive)

One move, applied to everything creatable: before something gets made, check whether it already exists nearby, and offer that instead. Course, quiz, test, likely topics and notes too. Same instinct every time.

"Nearby" is a ranked stack of signals, not one attribute. Same school is the hard filter (nothing outside your school surfaces). Inside that, closeness is ordered: same program ranks above same entry year ranks above courses you already share. So when someone creates Semiconductors, a person from their school, their program, who enrolled the same year floats to the top of "did you mean this?", and someone from the same school but a different department sinks. Nobody's excluded by a rigid rule; they're ordered by how close they are. That softness is what makes it travel. In the US where "same entry year" barely means anything, that signal just carries less weight and the others make up for it.

The check never forces the merge. Every check ends in an offer, and "no, make my own" is always live. That protects the small-group case (five friends who want their own private Semiconductors away from the 200-person course) without a single rule about when a course may fork. The user decides every time. The system's only job is to make sure the nearby option is visible, so duplicates happen on purpose instead of by accident.

That reframes dedup. We're not preventing duplicates, we're making them informed. Two Semiconductors courses coexisting is fine if both creators saw the other and chose to split. The failure we actually care about is a second one made because the first was never seen. The check kills the accidental fork, not the deliberate one.

## Two modes of the check

The primitive resolves two different ways depending on what it's checking against.

Creating a course checks against something finished that already exists. Resolution: "did you mean this?" and a possible merge.

Creating a quiz or test checks against something in progress, someone building a test for these same topics right now. Resolution isn't a merge, it's "someone's already on it, want in?" and it drops you into the notification for when it's done. Same instinct, different ending: one dedupes against what's done, the other coordinates against what's happening. Built as one system, the check has to know which of the two it's doing, because the offer at the end differs.

## Cold start

The emergent model has one weakness the attribute model didn't: a brand-new user with no courses has no overlap, so no graph, so the app risks feeling dead on arrival, exactly what we're avoiding.

Two seeds cover it before any course exists. Contact discovery fires immediately ("3 of your contacts are on here"). And the attributes still collected at signup (school, program if they'll give it, rough entry window) give a coarse starting set to display. They seed day zero; the real set accretes on top from actual course overlap.

## Governance

Two separate problems, not one.

Junk courses mostly solve themselves. The proximity check collapses accidental duplicates on creation, and a nonsense course nobody joins or uploads to is invisible weight that costs nothing. The rule for discovery: a course earns visibility in a classmate's feed by having activity. No activity, no surfacing. Spam nobody sees isn't a moderation problem.

Junk uploads inside a real course is the actual risk, and it's where the instinct to regulate is right. But regulating doesn't mean appointing a moderator. The moment someone can approve or reject uploads, they're an owner with a different job title, and ownerless is load-bearing for the whole shared-resource model.

The Merge Agent is the regulator, because it isn't a person. It already runs embedding similarity to synthesize. Give it a gate: an upload coherent with the topic gets merged; one wildly off (embedding distance from everything else in the topic) gets quarantined, held aside, visible to whoever uploaded it, kept out of the shared note until it corroborates with something. It's a gate on a worker that already exists, not a new system.

Corroboration is the second filter, and the crowd gives it for free. A claim five uploads support is trusted. A lone upload contradicting everything else gets down-weighted, not deleted by anyone. The mechanism that makes the merged note better than any individual's is the same one that catches garbage.

So three regulators, none a person with authority: the proximity check holds structure, the Merge Agent gate holds quality, contribution visibility holds behaviour (people upload less junk when their name is on it).

## Discovery and join behaviour

Notify, don't enroll. When a classmate creates a course, it appears in "courses your classmates are taking" with a join affordance. That's discovery, ambient, a choice the user makes. Auto-adding turns every membership list into noise and has the app deciding for the user, which kills the notebook feeling. Discovery flows through the emergent graph, so it needs no public search or browse and no new join primitive.

One correction to that ambient rule for the connection case. Discovery earns visibility through activity — but a course is *born* with zero activity, so a course a person you're connected to just created wouldn't surface, which is exactly backwards. So a course created by a connection **bypasses the activity gate and surfaces immediately and prominently** ("Ada started Organic Chem — join?"); the trust comes from the connection, not from accrued activity. The activity gate stays on for *strangers'* same-school courses, which is where spam actually lives.

Joins propagate too, and they matter more than creations — creation fires once per course, joining fires once per member, so joins are the actual diffusion engine. The trap is doing it per-event: every join pushing a prompt to the joiner's connections is the notification firehose this whole model is built to avoid, and it's redundant (three connected classmates joining one course would be three prompts for the same course). So **propagation is by course, aggregated, never per join-event**: one surface, "Organic Chem — N of your classmates joined," that gets *stronger* as N climbs instead of spamming a new nudge each time. It stays an ambient feed item until **two** connected classmates are in, at which point it escalates to a prompt. Aggregate and anonymous by default (warmth rule — a count, not a name), with names revealed on inspection once you're looking at the course. Propagation is **classmate-scoped** (people you already share a course with), the tightest and highest-signal loop.

The deeper point: creation-visibility, join-propagation, and the recognition loop (§7 of the product map) are **one system, not three** — they're all consume/activity events flowing through the emergent graph, aggregated and warmth-tuned, differing only in how loud and how aggregated. They ride the same attribution/consumption substrate (§11), which is unbuilt. Build that event layer once; each of the three is a policy on top of it. Three separate notification pipelines doing 90% the same work is the thing to avoid.

## The invitation model (finalized 2026-07-09)

Two doors into a course, and they are not symmetric. Discovery is the **inbound, ambient** door (above). Invitation is the **outbound, deliberate** one — how you actively bring someone in, and the only door that reaches a private fork the emergent graph can't (and shouldn't) discover. The invite link is, in fact, the *only* access control the system has: no public/private flag, no roles, no approval, no moderators. A valid link means you're in.

The key move: **you don't invite someone to a course, you invite a person.** Redeeming an invite lands them on the inviter's roster — the inviter's **current-term courses** — as a checklist: "here's what Trevor's taking this semester, join the ones that are yours." Multi-select, one action, nothing auto-enrolled. This is what makes inviting a cohort sane (ten classmates who share nine courses is one invite each landing on a select-all, not ninety separate course invites), and it dissolves the set/cohort tension: in a cohort school the whole roster shows and "select all" *feels* like the old class-code auto-join, but it's chosen, and there is still no `Class` entity — the cohort is emergent, the people who picked the same set. In a non-cohort school the invitee just ticks the two courses they actually share. Same screen, degrades gracefully. Scoping the roster to the current term is what makes the cohort *surface* without a container: the term does the grouping softly, and it also keeps you from exposing your whole course history to everyone you invite.

The permanent **per-course `invite_code` stays** alongside the personal roster link — it's the surgical tool for "join *this one* course" (the five-friend private fork), where the roster link is the broad "come study with me." Two intents, two tools. Both auto-enroll on a valid link with no approval step (privacy is a property of who holds the link, not a gate), and neither runs the proximity check — an invite is explicit intent, so there's nothing to dedupe against. A logged-out redemption flows through signup and lands on the same picker, which makes the invite link the platform's primary top-of-funnel, not merely an access control.

Decided and not revisited for launch: link is **permanent** (no rotation/expiry — accepted leak-recovery gap), **per-course** granularity (no single-use per-invite tokens), **auto-enroll** on redemption (no approval queue), any member can share. Open only as UI weight: how loud the connection-created prompt and the roster picker should be — the instinct is "in your face, but never forced."

## Open decisions

The matcher's reach. It's fuzzy ("semiconductors" vs "Semiconductor Physics" vs "PHY401"). Reach too far and every creation throws five "did you mean" prompts, people start clicking past them, and they're trained to ignore the exact prompt we most want seen. Reach too short and the accidental forks slip through. That threshold is a product-feel question you only get right by watching it run. Start loose and tighten, or start strict and loosen? (Undecided.)

How much to ask at onboarding. Program / major is a clean grouping signal in most of the world, but a US first-year often can't answer it. Make it optional and let contact discovery carry cold start when program is blank, or treat "undeclared" as a real bucket people sit in and join from? (Undecided.)

Coherent-but-wrong uploads. The Merge Agent gate catches incoherence, not subtle wrongness. It'll merge a confident, well-written, wrong upload that sits close to the topic. Corroboration catches it eventually, but only once a topic has enough contributors. Do we care now, or leave it until there's density to crowd-correct?
