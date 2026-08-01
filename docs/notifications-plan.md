# NotesOS — Notifications System Plan (§2.9)

> Scoped plan for the **notifications** flow of the mobile↔backend integration
> ([`mobile-integration-plan.md`](./mobile-integration-plan.md) §2.9). Owns the full build:
> in-app live feed **and** OS-level push. Update the tracking doc's §2.9 + log as phases land;
> this doc holds the design and the phase breakdown.
>
> Created 2026-07-31. Branch: `v2`. Decision: **full system incl. OS push** (user, 2026-07-31).

---

## 1. Findings — where the system actually stands

The backend in-app + live path is **already built and wired to real emitters**. The gap is
almost entirely mobile, plus one infra piece (OS push).

### Already built (backend — no rework)

| Piece | Location | State |
|---|---|---|
| `Notification` + `NotificationPreference` models | `models/notification.py` | ✅ |
| REST: list / unread-count / mark-read / mark-all / delete / delete-all / prefs | `api/notifications.py` | ✅ |
| `create_and_push_notification` (DB row + Redis `user_notifications` publish) | `services/notifications.py` | ✅ |
| Redis→WS bridge (`_listen_user_notifications` → `send_to_user`) | `services/websocket.py` | ✅ |
| `/ws/user/{user_id}` endpoint (JWT-auth, virtual room) | `main.py:145` | ✅ |
| Habit digest (decay nudge + recognition), APScheduler tick | `services/digest.py`, `workers/notification_scheduler.py` | ✅ |
| **Real emitters** already calling it | course join (`courses.py:353`), resource upload (`resources.py:1159`), note synthesis (`knowledge_worker.py:156`), digest | ✅ |

**Consequence:** a wired feed shows real content immediately — this is not an empty pipe.

### Missing

- **Mobile feed is 100% mock** — `notifications.tsx` uses a hardcoded `ITEMS` array + local read state.
- **Mobile client** — `lib/notifications.ts` has *preferences only*; no list/read/delete.
- **No user-scoped WS client** — `lib/courseSocket.ts` is course-only; §2.9's user-channel + AppState-aware reconnect is unbuilt.
- **No unread badge** — the home bell (`home.tsx:111`) is a static `●`.
- **No OS push at all** — `expo-notifications` not installed (only `expo-device`); backend has no device-token model or Expo push-send. Nothing arrives when the app is backgrounded/killed.

---

## 2. Architecture

Two delivery lanes off the **same** `create_and_push_notification` call — no new emitter code:

```
event (course join / upload / synthesis / digest)
      │
      ▼
create_and_push_notification()  ── writes Notification row (source of truth for the feed)
      │
      ├─▶ Redis publish "user_notifications"  ── LANE 1: in-app live
      │        └─▶ _listen_user_notifications → send_to_user → /ws/user/{id}
      │                └─▶ mobile userSocket → prepend to feed + bump unread badge
      │
      └─▶ Expo push fan-out (NEW)             ── LANE 2: OS push (app closed/bg)
               └─▶ POST exp.host/--/api/v2/push/send to the user's DeviceTokens
                       └─▶ OS notification → tap → deep link via meta_data
```

**Lane 1** = app-open, instant, free (WS already there). **Lane 2** = app-closed reach.
Both fire from one place, so every existing and future emitter gets both for free.

### Foreground de-dup
When the app is foregrounded, Lane 1 (WS) is the authority for the in-app feed. The
`setNotificationHandler` suppresses the **OS banner** while foregrounded (`shouldShowBanner:
false`) so a live event doesn't double-surface (WS row + OS banner). Backgrounded/killed →
only Lane 2 runs (no WS), banner shows.

---

## 3. Build phases

Sequenced so each phase is independently shippable and testable. Phase A delivers a real feed
on its own (backend already supports it); B+C add OS reach.

### Phase A — In-app live feed (mobile only, no backend change)
- **A1** `lib/notifications.ts` — add `NotificationItem` type + `fetchNotifications`
  (paginated), `fetchUnreadCount`, `markRead`, `markAllRead`, `deleteNotification`,
  `deleteAll`. Keep the existing preferences fns.
- **A2** `lib/userSocket.ts` — a `/ws/user/{user_id}?token=` client generalized from
  `courseSocket.ts`, **AppState-aware**: disconnect on `background`, reconnect on `active`
  (RN drops sockets when backgrounded). Same heartbeat/backoff/1008-stop discipline.
- **A3** `notifications.tsx` — drop the mock. Fetch on focus, real loading/empty/error,
  group by recency (Today / Earlier), tap → `markRead` + deep-link via `meta_data`,
  Mark-all-read, swipe/long-press delete. Subscribe to `userSocket` → **prepend live**.
- **A4** Unread badge — a tiny shared store (`stores/notifications` or a hook) holding the
  unread count, seeded by `fetchUnreadCount`, **bumped live** by the same `userSocket`
  message, cleared on mark-all. Home bell renders the count.

### Phase B — OS push infrastructure (backend)
- **B1** `models/notification.py` — `DeviceToken` (`id`, `user_id` FK, `token` unique,
  `platform` ios|android, `created_at`, `last_seen_at`). Register in `models/__init__.py`.
- **B2** `alembic revision --autogenerate -m "device tokens"` (never hand-write — CLAUDE.md).
- **B3** `api/notifications.py` — `POST /notifications/devices` (upsert token for the
  current user; move token to caller if it was another user's — reinstall/handoff),
  `DELETE /notifications/devices/{token}` (unregister on logout).
- **B4** `services/push.py` — `send_expo_push(tokens, title, body, data)` over httpx to
  `exp.host/--/api/v2/push/send` (chunked ≤100). Call it from
  `create_and_push_notification` after the Redis publish (best-effort, non-blocking of the
  DB write). **Prune** tokens Expo reports as `DeviceNotRegistered`. Gate on
  `settings.ENABLE_PUSH` (default on) so tests/local can silence it.
- **B5** Tests (real Postgres): device upsert/handoff/delete + ownership; push fan-out with
  httpx mocked (asserts payload shape, chunking, invalid-token pruning); feed unaffected
  when push disabled.

### Phase C — OS push (mobile native)
- **C1** Install `expo-notifications` (`npm install expo-notifications@~... --ignore-scripts
  --save`, per the `npx expo install` EALLOWSCRIPTS trap). Add the plugin + an
  **`extra.eas.projectId`** to `app.json` (see owner action). Android channel config.
- **C2** `lib/push.ts` — request permission, `getExpoPushTokenAsync({projectId})`, register
  via `POST /notifications/devices`. Called after login / on app-start when authed; deregister
  on sign-out + account-delete. `expo-device` guards against simulators (no push token there).
- **C3** `setNotificationHandler` (foreground-suppress banner, see §2 de-dup) +
  `addNotificationResponseReceivedListener` → route from `meta_data`
  (`course_id`/`topic_id`/`mode`/`concept_ids`) into the right screen. Cold-start tap handled
  via `getLastNotificationResponseAsync`.

---

## 4. Deep-link contract (meta_data → route)

The emitters already stamp `meta_data`. Tap routing reads it:

| type | meta_data keys | route |
|---|---|---|
| `DECAY_NUDGE` | `course_id`, `topic_id`, `mode`, `concept_ids`, `est_minutes` | `/retrieval` (or `/note?topicId=`) |
| `AI_SUMMARY_READY` | `topic_id`, `course_id` | `/note?topicId&courseId` |
| `RESOURCE_UPLOADED` | `course_id`, `topic_id?` | `/topics?courseId` or `/note` |
| `CLASSMATE_JOINED` / recognition | `course_id` | `/topics?courseId` |
| `GENERAL` / unknown | — | `/notifications` (safe fallback) |

One `routeForNotification(meta_data, type)` helper, shared by the in-app tap (A3) and the OS
tap (C3), so both lanes land identically.

---

## 5. Owner actions

- **EAS project id.** `getExpoPushTokenAsync` needs a `projectId`. `app.json` has no
  `extra.eas.projectId` yet → run `eas init` (or paste the id into
  `expo.extra.eas.projectId`). Without it, C2 can't mint a token.
- **Dev-client rebuild.** `expo-notifications` is a native module → rebuild the dev client
  after C1 (`npx expo prebuild` + `run:ios`/`run:android`). Push only works on a **physical
  device** (iOS simulators can't receive remote push).
- **APNs / FCM credentials.** Expo push needs the app's APNs key (iOS) + FCM setup (Android)
  registered with EAS (`eas credentials`). One-time.

---

## 6. Explicitly out of scope (this pass)

- Notification categories / actionable buttons (reply-from-notification).
- Rich/media push. Grouping/threading on the OS side.
- Web push (Next.js frontend is separate; v2 client is native).
- Quiet-hours / per-type push toggles beyond the existing `digest_enabled` /
  `recognition_enabled` prefs — revisit if the user asks.

---

## 7. Log

- **2026-07-31** — Doc created. Traced current state (§1): backend in-app+WS path fully built
  and wired to real emitters; gap is mobile feed + user WS client + unread badge + all OS push.
  User chose **full system incl. OS push**. Phased build above; starting Phase A.
- **2026-07-31** — All phases (A/B/C) shipped in one session. See the matching
  [`mobile-integration-plan.md`](./mobile-integration-plan.md) §2.9 entry (2026-07-31) for the
  full file list, the two traps caught (push `data` missing `type`; unregister-before-
  `deleteAccount` ordering), and verify results. Remaining before push is testable on-device:
  owner runs `eas init` (project id), `eas credentials` (APNs/FCM), and a dev-client rebuild.
