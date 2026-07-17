# NotesOS — Launch Readiness (ops + compliance checklist)

> The **non-code** half of launch readiness. The buildable half is **Phase D** in
> [`v2-redesign-plan.md`](./v2-redesign-plan.md) (D1 rate limiting · D2 observability ·
> D3 account deletion · D4 review bypass · D5 report mechanism). This doc is the
> checklist for store submissions, legal docs, and owner-run infra — the things that
> reject apps and page founders.
>
> 👤 = owner action (no code) · ⚙ = covered by a Phase D queue item · 🎨 = designer/client
> concern (flag to the designer). Created 2026-07-17.

---

## 0. Locked decisions (context for everything below)

- **iOS auth is phone-only.** No Google login on iOS ⇒ Apple's Sign-in-with-Apple
  requirement (guideline 4.8) never triggers. Google OAuth may remain on Android/web.
- **Moderation process:** report → auto-quarantine (reuses merge-gate machinery) →
  owner reviews at launch scale → release or remove. This *is* the "moderation process"
  statement the stores ask for.
- **Launch is free** ⇒ IAP / Play Billing integration is deferred. When subscriptions
  arrive: digital goods **must** use Apple IAP / Play Billing in-app (external payment
  links in-app = rejection; the US link-out exception does not apply in Nigeria).
  Gifting lives on the **web** (allowed). Server-side entitlement service verifying
  store receipts — architecture decision for the architect when it lands.

---

## 1. Backend ops (before the API is publicly reachable)

| Item | Status |
|---|---|
| Rate limiting — OTP strictest (pumping fraud + brute force) | ⚙ D1 |
| Error tracking (Sentry) incl. worker dead-letter capture | ⚙ D2 |
| Queue/DLQ metrics endpoint | ⚙ D2 |
| LLM cost telemetry at the single call site | ⚙ D2 |
| JSON logs + request IDs + **PII redaction (phones/OTPs never logged)** | ⚙ D2 |
| Uptime monitoring on `/health` (UptimeRobot / Better Stack — free tier) | 👤 |
| Automated Postgres backups + **one tested restore** (the attempt log is irreplaceable) | 👤 |
| Rotate the PAT embedded in the old git remote (noted in START_HERE §0) | 👤 |
| Secrets: strong `JWT_SECRET`, required-env validation at startup, no secrets in repo | 👤 |

## 2. Apple App Store — rejection traps, in likelihood order

1. **Reviewer login (2.1).** Reviewers can't receive WhatsApp OTPs. ⚙ D4 review bypass;
   👤 supply the allowlisted phone + fixed code in App Review notes on every submission.
2. **Account deletion in-app (5.1.1(v)).** ⚙ D3; 🎨 must be findable in settings, not buried.
3. **Contacts consent (5.1.1/5.1.2).** Contact discovery is **opt-in, never required for
   core function**. 🎨 pre-permission explainer before the OS prompt; the phone-hash
   design is already right — say so in the privacy label.
4. **UGC (1.2).** Report/flag on shared content + block capability + stated moderation
   process. ⚙ D5; 🎨 report affordance on notes/resources.
5. **Purpose strings** — each must be specific and honest. 👤 write them: camera (photo
   answers), microphone + speech recognition (voice modes; STT is on-device), contacts
   (find classmates — hashed, opt-in), notifications (review reminders), photo library
   (upload notes), background audio (Listen).
6. **Privacy nutrition labels.** 👤 declare: phone number (identity), contacts (hashed,
   opt-in), user content (notes/photos/audio), usage data. **Disclose third-party
   processing: OpenAI / Deepseek / Anthropic / Voyage (AI), Cloudinary (storage),
   WhatsApp/OTP provider (verification).** Labels must match observed traffic.
7. **AI-generated content.** Notes/grading are AI-generated — disclose in review notes
   and app description; accuracy disclaimer in-app (🎨 tone: honest, not legalistic —
   fits the brand). The D5 report path doubles as the bad-AI-output report mechanism.
8. **Push consent (4.5.4).** Decay nudges are user-serving, but still opt-in; never
   marketing without explicit consent. 🎨 ask for notification permission *in context*
   (after first session, when the nudge has meaning), not at first launch.
9. **Export compliance.** Standard HTTPS/OS crypto ⇒ exempt declaration
   (`ITSAppUsesNonExemptEncryption = NO`). 👤 one-time setting.
10. **Age rating.** Likely 13+ (unrestricted web access not needed; UGC present). 👤
    questionnaire; answer the AI-content questions honestly.
11. **Background audio.** Declare the audio background mode only if Listen truly plays
    in background (it should); don't declare unused modes (that's its own rejection).

## 3. Google Play — the equivalents + Play-specific

1. **Data safety form.** 👤 mirror of Apple labels — same data types, same third-party
   disclosures. Mismatch with observed behaviour → flag/removal.
2. **Reviewer access.** 👤 same D4 credentials in the App content → App access section.
3. **UGC policy + AI-Generated Content policy.** Both satisfied by D5 (report/flag) +
   block capability + moderation statement.
4. **Prominent disclosure (User Data policy).** Contacts upload needs an **in-app
   disclosure screen before the runtime permission** — the OS dialog alone is not
   enough on Play. 🎨.
5. **Permissions declarations.** `READ_CONTACTS` triggers extra review — the use case
   (social discovery in a social-study app) is legitimate; 👤 write the declaration
   carefully. Never request permissions not yet used.
6. **Target API level.** 👤 keep within Play's current target-SDK requirement at
   submission time (moves annually).
7. **Account deletion.** Play also requires a **web link** for account deletion (not
   only in-app) — ⚙ D3 endpoint + 👤 a tiny hosted page that fronts it.
8. **Pre-launch report.** 👤 run it; fix crashes it finds before review does.

## 4. Legal / regulatory

- **Privacy policy** 👤 — hosted URL (both stores require it). Must cover: phone-primary
  identity, hashed contact discovery, AI processing by the third parties above, study
  data, retention, deletion rights, NDPA basis. Written plainly — the brand voice can
  survive a privacy policy.
- **Terms of service** 👤 — UGC license (you need rights to display shared notes to
  classmates), acceptable use (feeds the D5 process), subscription terms placeholder.
- **NDPA (Nigeria Data Protection Act 2023)** 👤 — check the NDPC registration threshold
  as users grow; breach-notification duty (72h to NDPC) — D2's Sentry is how you'd even
  know; deletion rights (D3 is the mechanism).
- **GDPR-lite posture** — if EU students appear, D3 + the privacy policy cover the
  core rights; defer anything heavier until it's real.

## 5. Submission-day checklist (both stores)

- [ ] D1–D5 all green in the queue
- [ ] Review credentials (D4 allowlist) in both consoles' review notes
- [ ] Privacy policy + ToS live at stable URLs
- [ ] Labels / Data safety form filled and matching reality
- [ ] Purpose strings / permission declarations written and specific
- [ ] Account-deletion web link live (Play)
- [ ] Export compliance + age rating set
- [ ] Uptime monitor + backups + Sentry alerts confirmed firing
- [ ] Screenshots/description mention AI honestly (no "guaranteed grades" claims)
