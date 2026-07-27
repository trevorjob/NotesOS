# NotesOS — Design System

**Living document. v0.4 — 2026-07-25.**
Direction: **risograph as the print-soul of the Notebook brand** — one craft direction, not a
pivot (reconciled with `CLAUDE.md` / system-spec: notebook grain + riso halftone, amber
highlighter as the spot ink, misregistration as depth).
Rebuilt against `system-spec.md` §4/§6, `product-map.md` (through the **2026-07-25 mastery
restoration**), `v2-redesign-plan.md` Phase C, and the companion [`page-map.md`](./page-map.md).

This is a **contract, not a look.** It defines the slots that must exist, the rules that
can't be broken, and the semantics that are reserved. **Claude Design owns every visual
value** — palette, faces, forms, spacing, motion. Its job is to decide them; this doc's job
is to make sure it decides them **once**, and that every screen after the first inherits them.

**How to use it:** brief screen one with §1–§7 → Claude Design resolves the open values →
write them into §8 → every later brief ships §8 as fixed context. **§8 is the whole point of
the document.**

> ### Changed in v0.4 — read this first (supersedes v0.3)
>
> v0.3 was rebuilt against the **2026-07-21 amendments, which had *removed* mastery colouring
> from the note. That was reversed on 2026-07-25** — so several v0.3 rules are now inverted.
> Corrected here:
>
> **1. The note IS lit by mastery.** Full heat-map — solid / fading / shaky, per concept. The
> note reads as a live map of what you know vs. what's decaying. This reverses v0.3's R1.
> §1 R1, §2, §3, §5.
>
> **2. The note lit by mastery IS the progress surface.** Progress is *spatial* — the note
> itself — not a separate screen. A dedicated stats view is optional depth only. §4.
>
> **3. The note has two coupled signatures.** It *shows* you what's fading (mastery lighting)
> **and** lets you *act* on it in place (launch a retrieval on a concept/paragraph). Together
> they are the anti-fluency-illusion mechanic. §3.
>
> **4. The note is structure-first, not prose** *(B12)*. Sections take whatever form their
> material calls for, prose only where an idea needs flow. The layout has to hold all of them. §5.
>
> **5. Every note and tutor surface is always math-capable** *(B10)*. Not a STEM mode. §5.
>
> **6. Direction: risograph as the print-soul of the Notebook brand.** One craft vocabulary —
> notebook grain + riso halftone, amber highlighter as the spot ink, misregistration as depth.
> **Night Journal dark ships at launch** as an inversion (dark stock, same inks). §1 R4/R10, §2, §8.
>
> **7. Offline covers reads *and* objective retrieval**, not reads alone. §7.

---

## 1. Rules (locked — not Claude Design's call)

From the product, not from taste. A design that breaks one is wrong even if it's beautiful.

**R1 · The note is lit by mastery — that's the colour it spends.**
The note carries one reserved colour system: **knowledge state** (solid / fading / shaky), per
concept, so the note reads as a live map of what you know vs. what's decaying. This *is* the
spatial progress surface (§4) and the ambient half of the anti-fluency mechanic (§3). Colour is
still rationed — no *decorative* colour, no second semantic system — but state colour belongs
**on the note**, not banished from it. Everything that isn't `state`, `confirm`, or rendered
content (figures) is ink on stock. Per R9, state is never carried by hue alone.

**R2 · Structure is the primary read.**
A student must be able to lift every core idea *at a glance*, with no filler to read past.
Sections lead with their recallable core. The layout has to hold itemised labelled entries,
grouped and ordered lists, the occasional real table, step-structured worked examples, and
prose — chosen per section by the system. **No single shape can be the default**; a
prose-shaped layout and a forced-grid layout are the same bug.

**R3 · Always math-capable.**
Every note surface and the tutor chat render inline and block maths, and hold worked examples
as step-structured first-class elements. Subject is a *density hint*, never a capability
switch — a humanities note with one stray formula renders it properly.

**R4 · Texture is chrome-only.**
Grain, halftone, ruled lines, and misregistration — the notebook-through-riso texture — are
decoration. Never under body prose, an equation, a worked example, or a figure. The amber
highlighter is the one *spot ink*, used for meaning (active / selected), not as background
texture. Nothing about the texture animates.

**R5 · Nothing punitive.**
Wrong, overconfident, offline, behind, fading — all information, never failure. No red for a
wrong answer, no warning colour for offline, no alarm for decay. **Wilting is gentle and
reversible**; that's the entire argument against streaks and it has to survive contact with
the visual language.

**R6 · Difficulty reads as the mechanism, not breakage.**
Retrieval *should* feel hard. The design frames hardness as the thing working, never as the
app failing.

**R7 · Form follows the job, not the component library.**
Cards, tabs, modals, chips, drawers are *answers, not defaults*. A rule, a change of ground, a
spacing break, a label, or plain hierarchy usually separates content more quietly than a box —
so every component has to earn its place in the brief (say the job, say why a lighter device
won't do it) or it doesn't ship. This is a print language: it separates with rules, weight, and
space far more often than with boxes. §6 is the working list.
**Default-deny, and here's the teeth:** the card is the *presumed-wrong* choice — a screen that is
a **stack of cards** (a feed of boxed rows, a grid of boxed tiles) has failed this rule, full stop.
A boxed container is justified only when content genuinely floats on the page *and* nothing lighter
(a hairline rule, a ground shift, whitespace, a heading) groups it — which is **rare**, not the norm.
Rough heuristic: **more than one or two boxed containers on a screen is a smell**; a page of them is
a bug to send back, however polished. Print groups a list with a rule and space, not by putting every
item in its own bordered box — build that way.

**R8 · Performance floor.**
60fps on a 2GB Android. Texture is the first thing cut from any screen that can't hold it.

**R9 · Accessibility floor.**
AA on every text/ground pair. 44×44pt minimum targets, including inline retrieval affordances.
Dynamic Type to 200% without breaking the grid. `prefers-reduced-motion` respected.
Decorative layers hidden from assistive tech. State never carried by hue alone.

**R10 · Both modes at launch — Night Journal is an inversion, not a redesign.**
Dark ships at launch (the market studies at night). It is **dark stock with the same inks** — a
near-mechanical inversion of the light values, not a bespoke second design. Resolve light first
in §8, then derive dark from it; don't design two separate systems.

---

## 2. Colour: roles, not values

Claude Design picks the hexes. These are the jobs to fill and the constraint on each.

| Role | Job | Constraint |
|---|---|---|
| `ground` | The stock every screen sits on | Warm. Paper, not white. |
| `ground.recessed` | Wells, panels, worked-example blocks, source-read view | Same family, one step down |
| `ground.edge` | Rules, hairlines, borders | An ink tint, never a neutral grey |
| `ink` | All body text, headings, maths, icons | AA+ on `ground`. Worth considering: a coloured dark rather than black — it reads as *printed* rather than as a document viewer |
| `ink.secondary` | Metadata, labels, inactive | ≥4.5:1 on `ground` |
| `ink.tertiary` | Non-essential only | Never the sole carrier of meaning |
| `state` | **Reserved — knowledge state** | Solid / fading / shaky. Spent **on the note** (the mastery map, §3/§4) and any optional stats view — same semantic. Pairs hue with a second channel (R9), so it survives the spot-ink budget. |
| `confirm` | Correct, co-presence, confirmation | Rationed hard. Never a navigation colour, never a primary fill. |

**Budget: one stock, three inks + the reserved `state` ramp.** The riso constraint keeps it
tight — ration hard, no decorative colour. The `state` ramp (solid / fading / shaky) is the one
reserved system that legitimately colours *content* (the note is the mastery map); `confirm` and
figures are the only other colour. If a surface reaches for colour that isn't one of those, it's
wrong. **Dark (Night Journal):** every role resolves a light value first; dark is its inversion
on dark stock, same inks (R10).

**Not in the system:** a semantic red, a semantic amber, a success/warning/error triad. R5
removes the need and their absence is the point.

---

## 3. The signature — the note as a launch point

The one thing the product is remembered by. **Claude Design decides the form.** These are the
constraints.

The note is a *reading* surface, and reading-instead-of-retrieving is the fluency illusion the
whole product exists to fight. So the note does two coupled things — it **shows** you your state
and lets you **act** on it in place:

- **(a) Lit by mastery.** Every concept in the note is tinted by its `state` (solid / fading /
  shaky), so the note is a live map — you *see* what's decaying as you read. This is the ambient
  half of the anti-fluency mechanic, and it *is* the progress surface (§4).
- **(b) Launch retrieval in place.** You can trigger a retrieval on a concept or paragraph
  **right there, without leaving the note** — the active half. Seeing what's fading and testing
  it are one gesture apart.

Constraints on both:

- **Quiet.** Lighting and affordance are ambient, not interruptions. The reading experience has
  to survive them being present on every section.
- **In place.** Reading flows into testing with no screen change; the return-to-reading gesture
  must not lose the user's position.
- **Can't be buried.** It's the anti-fluency mechanic — discoverable without nagging.
- **44pt target minimum** for the launch affordance, however quiet it looks (R9).
- **State is shown, never scored.** The lighting reports *"this is fading,"* never *"you failed
  this"* (R5). Wilting, not a red mark.

---

## 4. Progress — spatial, the note lit by mastery

**The note lit by mastery IS this surface** — progress is *spatial*, read across your own
notebook, not a separate screen. A dedicated stats view is optional *depth*, never the headline.
This is where `state` (§2) is spent.

Three values from `ConceptState`: **solid · fading · shaky.**

- **A glimpse, not a dashboard.** Deliberately un-busy. No vanity number, no stats wall, no
  chart of your week. The *note* carries the state; any summary view stays minimal.
- **Continuous and forgiving.** Concepts fade *gradually*; any retrieval revives one; nothing
  ever breaks. Structurally the opposite of a streak, and the visual treatment has to argue
  that — **wilting, not shattering.**
- **Lead with growth, whisper the fading.** "4 got more durable today" foregrounded; "3 are
  slipping" present and gentle. Never anxiety-farmed (R5).
- **No comparison, ever.** Personal and absolute. No leaderboard, no cohort average, no
  percentile. The social layer is *contribution*, never a knowledge ranking.
- **Calibration is signature-but-quiet** — "you're getting better at knowing what you actually
  know." Surfaced when relevant, not in the user's face.
- Three redundant channels for the three states (R9) — **especially on the note**, where hue
  alone would fail colour-blind readers and strain the spot-ink budget; none may read as an alert.

---

## 5. The note surface — what the layout must hold

R2 and R3 in concrete terms. The system picks each section's form; the layout has to be able
to hold any of them, and make the studiable shape the primary read.

| Section form | Notes |
|---|---|
| Itemised labelled entries | e.g. each site as its own block — *date · finds · why it matters*. Probably the most common structured form. |
| Grouped / ordered lists | Taxonomies, sequences |
| Table | Only real multi-axis comparison. Reads dense, so rare. |
| Worked example | **Step-structured, steps intact.** The steps *are* the content. First-class, not a quoted block. |
| Rendered maths | Inline and block. Native, no WebView. |
| Prose | Where an idea genuinely needs flow |
| Figure | Preserved and referenced inline, not flattened. *(Backend promise currently unmet — the client must be designed to hold them so it isn't a retrofit.)* |

These sit **next to each other inside one note**, section by section. A note may be all prose,
all worked examples, or a mix.

**Also on this surface:**

- **Lit by mastery** — each concept tinted by its knowledge `state` (§3/§4); the note is a live
  map, not a flat document. Part of the reading surface, never a separate mode.
- **"Says who?"** — an on-demand provenance X-ray on a single line, for the sceptic. Never a
  debate: the note is always one authoritative voice and never shows sources disagreeing.
- **"Read the original"** — the verbatim source layer, reachable as a readable view. This is
  the guarantee that lets the note go lean. A sibling of "says who?", not the same thing.
- **"Your cohort built this"** — a warm social trust signal. Aggregate ("N built this note"),
  never ranked.
- **What changed since you last read**, and **"Ada added this section."** The note grows by
  merge, so it has history and both are real surfaceable states.
- **States:** `empty` (scaffold, no material) · `synthesizing` (**streams in — it visibly
  writes itself**) · `ready` · `updated` (changed since last view).

---

## 6. Component vocabulary — earn it

**R7.** Cards, tabs, modals, chips, spinners, drawers are answers, not defaults. Before any
ships, the brief says what job it's doing and why a lighter device doesn't do it as well.
Often one does — a rule, a change of ground, a spacing break, a label, or plain hierarchy.
This is a print language, and print separates content with rules, weight, and space far more
often than with boxes.

**Reach for these *first* — the grouping/separation vocabulary that isn't a box.** When you feel the
pull to card something, the answer is almost always one of these:

- **Whitespace** — a bigger gap is the most common "these are separate groups." Costs nothing, adds
  no chrome.
- **A hairline rule** (`ground.edge`) — a single ink line separates a list far more quietly than
  boxing every row.
- **A ground shift** (`ground.recessed`) — one recessed well sets a region apart without four borders.
- **Type hierarchy + a label** — a heading (or a Caveat annotation) tells you what a block is; you
  rarely also need to fence it.
- **Alignment / indentation** — a hanging indent or a shared left edge groups items structurally.

A **list of things is a list**, not a stack of cards — render it as rows separated by rules or space.
Reserve the boxed container for the exception where content truly floats free and none of the above
groups it.

Defaults to interrogate rather than accept:

- **A card** usually means "this is grouped." A rule or ground change often says it more quietly.
- **A tab bar** means "these are peers." The home is a doorway that removes the choice of what
  to study, so persistent global tabs argue against the product's own thesis. **Resolved**
  (page-map *Navigation model*): **no** persistent tab bar / dashboard; **yes** a persistent,
  one-gesture, *flat* switcher — an *invoked* quick-switch (recents-first, search for the tail) that
  jumps straight to any course/topic/note, never a drawn-chrome bar and never a drill-down tree. It
  coexists with the doorway because it's summoned, not always-on.
- **A blur shadow** is unprintable. Misregistration is the native depth device.
- **A spinner** is a shrug. The system streams (synthesis writes itself) or is optimistic
  (queued attempts), so a determinate mark almost always beats one.
- **A modal** interrupts. Most of what wants one here is a sheet or an inline expansion.
- **An illustrated empty state** is decoration. Every empty surface owes a next action instead.
- **A progress bar or percentage** on the progress surface. It's a glimpse, not a dashboard (§4).

**The jobs that need a named form.** Name each once, reuse everywhere:

| Job | Where |
|---|---|
| Launch retrieval from inside the note | §3 — the signature |
| Section forms | §5 — entries, lists, table, worked example, maths, prose, figure |
| Provenance X-ray ("says who?") | Note |
| Source-read ("show me the original") | Note |
| Contribution signal ("N built this") | Note, recognition |
| What-changed / who-added | Note, updated state |
| Knowledge state at three levels | On the note (the mastery map) + optional stats view |
| The single next-best action | Home hero |
| The flat quick-switcher | Invoked from every screen — jump to any course/topic/note, recents-first |
| The quiet escape hatch ("or something else") | Home |
| What's new from classmates | Home secondary — **never the hero** |
| Pose a challenge, take an answer | Every retrieval mode, text **and voice** |
| Build a practice test (scope · count · type → generate) | The deliberate study door (C9) — distinct from the C1 doorway |
| A shared test in a course | The communal test list — "Ada made a 20-q mock," no score ranking |
| Capture confidence before a reveal | **Optional** — §7 |
| Deliver the calibration verdict | The personality beat |
| Self-grade a worked answer | STEM launch flow |
| Warm session close | End of every session |
| Async work in flight | Capture, synthesis, grading |
| Needs-connection | Online-only surfaces — §7 |
| Ambient co-presence | "3 classmates studying Alkenes right now" |
| The "did you mean this?" offer | Course creation, coordination — a **branch of creation, not an error** |
| In-context permission ask + graceful denial | Mic, camera, contacts, push |
| Notification inbox item | Read/unread, grouped |
| Empty + next action | Every empty surface |

---

## 7. Semantic coverage — every state needs a treatment

One treatment each, defined once, so no screen invents its own. R5 governs all of them.

| Set | Values |
|---|---|
| Knowledge state | `solid` · `fading` · `shaky` — **on the note** (mastery map, §4) + optional stats view |
| Grade | `again` · `hard` · `good` · `easy` — self-grading shouldn't feel scored |
| Calibration verdict | `calibrated` · `overconfident` · `underconfident` |
| Answer status | `correct` · `partial` · `needs-review` |
| Note state | `empty` · `synthesizing` · `ready` · `updated` |
| Resource state | `uploading` · `processing` · `ready` · `failed` (→ retry or remove) · `needs-review` · `quarantined` |
| Sync state | `fresh` · `stale` · `syncing` · `offline` · `queued` · `attempt-didn't-sync` |

Four that are easy to get wrong:

- **`overconfident` must not read as a scolding.** It's the honest catch the product is built
  on. A failure badge kills the thesis at the point of delivery.
- **`offline` is not an error.** It's the normal condition of the core market.
- **`quarantined`** is uploader-only and it's a *held* state, not a rejection.
- **`fading`** is wilting, not warning.

### The offline boundary (design has to show it correctly)

| Works offline | Online only |
|---|---|
| All reads — note, key points, source layer, downloaded audio | Capture (needs server processing) |
| **Objective retrieval** — pre-generated MCQ/pretest banks, FSRS scheduling, self-graded worked examples | AI-graded modes (ramble, teach) |
| Attempts, which **queue and union-merge on reconnect** | Voice |

Offline is not a degraded read-only mode. A student in a dead zone can still *retrieve*, which
is the point — read-only offline would leave them with the fluency-illusion activity and block
the real one.

### The confidence beat is optional

Forcing "how sure are you?" on every attempt turns a signature moment into a nag. It earns its
place on **pretests, new or shaky concepts, and deliberate open-ended modes**; it's a tax on
rapid review of near-mastered concepts. **Design both flows** — asked, and just-answer — not
one with the prediction bolted on.

---

## 8. Resolved values — Claude Design fills this in

**Empty on purpose.** This is where consistency actually comes from. Claude Design resolves
these on the first screens, the values get written here, and every later brief ships this
section as fixed context.

```
GROUND
  ground                      #______
  ground.recessed             #______
  ground.edge                 #______

INK
  ink                         #______
  ink.secondary               #______
  ink.tertiary                #______

RESERVED
  state (note map + progress) #______   ramp: solid ______ / fading ______ / shaky ______
  confirm                     #______

DARK  (Night Journal — inversion of the light values above, R10)
  ground / ink / state        derive by inverting light; verify AA holds on the dark ground

TYPE
  display                     face ______  sizes ______
  body                        face ______  size ______ / line ______
  utility                     face ______  size ______  tracking ______
  math                        face ______  (must sit on the baseline below)

GRID
  base unit                   ______
  page gutter                 ______
  section gap                 ______
  baseline                    ______
  corner                      ______

DEPTH  (print-native — no blur)
  device                      ______
  levels                      ______

TEXTURE
  grain                       ______ @ ______ opacity
  halftone                    ______ pitch @ ______ opacity
  applied to                  ______   (chrome only — R4)

MOTION
  press / toggle              ______
  reveal                      ______
  navigation                  ______
  synthesis streaming         ______
  calibration beat            ______

SIGNATURE (§3)
  mastery lighting on note    ______   (solid / fading / shaky, per concept)
  retrieval affordance        ______
  resting state               ______
  active state                ______
  return-to-reading           ______

PROGRESS (§4)
  solid / fading / shaky      ______
  channel 2                   ______
  channel 3                   ______
  growth-first framing        ______

SECTION FORMS (§5)
  labelled entry              ______
  list (grouped / ordered)    ______
  table                       ______
  worked example (steps)      ______
  maths (inline / block)      ______
  figure + caption            ______
  prose                       ______

OTHER FORMS (§6)
  says who?                   ______
  read the original           ______
  contribution signal         ______
  what changed / who added    ______
  home hero                   ______
  quick-switcher              ______   (invocation gesture · resting affordance · recents/search)
  test builder                ______   (scope · count · type · generate-with-progress)
  shared-test list            ______   (communal, un-ranked)
  or-something-else           ______
  challenge + answer          ______
  confidence capture          ______
  calibration verdict         ______
  self-grade                  ______
  session close               ______
  async progress              ______
  needs-connection            ______
  co-presence                 ______
  did-you-mean-this offer     ______
  permission ask + denied     ______
  inbox item                  ______
  empty + next action         ______
```

---

## 9. Briefing template

For every screen after the first:

> **Context:** §1 rules, §2 colour roles, §8 resolved values (paste in full).
> **Screen:** what it is, its single job, what the user just came from.
> **Content:** the real content, in full. No lorem, no placeholder counts. For a note, include
> at least three *different* section forms so the layout gets stress-tested.
> **States:** which of §7 appear here.
> **Behaviour:** the relevant part of `system-spec.md`.
> **Constraint:** which §6 forms to reuse, and what it may not invent.
> **Component gate (R7 — state it in every brief, don't assume §1 carries it):** *default-deny on
> boxed containers.* For **each** card / tab / modal / drawer in the output, the deliverable must name
> the job it does and why whitespace / a rule / a ground shift / hierarchy (§6) won't. **A screen
> that's a stack of cards is a rejected deliverable, not a first draft** — send it back. Lists render
> as rows separated by rules or space, not boxed tiles.

Don't re-describe the style. If a brief has to restate the direction, §8 isn't doing its job
and the values need tightening rather than repeating. **The one thing to repeat every time is the
component gate above** — the card default is strong enough that stating R7 once in §1 doesn't hold;
name it per brief and check the output against it.

**Brief the note screen first** — it's the surface that kills most visual styles, and R2/R3
mean it now has to hold six or seven different section forms at once.

---

## 10. Open

- **Math rendering.** Native, no WebView (Phase C). It constrains the note grid more than
  anything else here and it's **still blocking the note screen.**
- **Note↔concept span anchoring.** The prose isn't span-linked yet; `TopicKnowledge.concepts`
  is a flat list and attribution is topic-level by design. **Both the mastery lighting (§3) and
  claim-level "says who?" (§7 escalation) stand on this.** The design can proceed on
  concept/paragraph-level granularity; don't design for word-level until this lands.
- **The mastery map on a spot-ink budget.** Three states (solid / fading / shaky) rendered
  legibly across a limited riso palette, using hue *plus* a second channel (weight, underline,
  halftone density) per R9 — without a rainbow or an alert read. The hardest colour problem in
  the system; resolve it on the note screen.
- **~~Whether a persistent global nav exists at all.~~** **Resolved** (page-map *Navigation
  model*, 2026-07-25): no persistent tab bar / dashboard; a persistent *one-gesture, flat, invoked
  switcher* instead (recents-first, jumps straight to any course/topic/note). Open sub-problem for
  design: the switcher's *invocation gesture and resting affordance* — reachable from every screen,
  ≤1 gesture, without becoming always-drawn chrome that competes with the doorway.
- **Grain cost on a 2GB device.** R8 sets the floor; unmeasured.
- **Figures.** Client designed to hold them; backend delivery deferred. Don't let that become
  a UI retrofit.