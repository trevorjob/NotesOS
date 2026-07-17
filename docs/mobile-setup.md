# NotesOS — Mobile Dev Infra Setup (macOS)

> **Infra only.** This documents the toolchain for building the v2 native client. No app
> code exists yet — scaffolding comes later. The framework is **locked**: Expo / React
> Native against the existing v2 backend API (see
> [`v2-redesign-plan.md`](./v2-redesign-plan.md) §Phase 5).
>
> Last updated: 2026-07-13. Machine: this Mac. Dev target: **Expo Go on a physical phone.**

---

## Why Expo Go (and what it saves you)

The dev loop is: run Metro on the Mac → scan a QR code with the **Expo Go** app on your
phone → app loads with live reload over Wi-Fi. That path needs **no Xcode and no Android
Studio**. You only need those heavier toolchains later if you switch to a
simulator/emulator, or add a native module Expo Go doesn't bundle (then you build a *dev
build* — see [When you outgrow Expo Go](#when-you-outgrow-expo-go)).

---

## Toolchain status on this machine

| Tool | Status | Purpose |
|---|---|---|
| Node 26.4.0 | ✅ installed | JS runtime + Metro bundler (Expo needs 18+; 26 works, expect harmless "unsupported engine" warnings) |
| npm 11.17.0 | ✅ installed | Package manager |
| Homebrew | ✅ installed | System package manager |
| **watchman** 2026.07.06 | ✅ installed | File watcher Metro uses; prevents "too many open files" |
| **eas-cli** 20.5.1 | ✅ installed | Expo Application Services CLI — account, builds, OTA updates |
| Java 21 | ✅ present | Only needed for the Android-emulator path |
| Swift 6.3 CLI | ✅ present | Only needed for the iOS-simulator path |
| Full Xcode | ❌ not installed | **Not needed** for Expo Go |
| Android Studio | ❌ not installed | **Not needed** for Expo Go |

### What was installed for this setup

```bash
brew install watchman        # done
npm install -g eas-cli       # done
```

### Still to do by hand (needs your accounts/devices)

1. **Install Expo Go on your phone** — App Store (iOS) or Play Store (Android).
2. **Create a free Expo account** at https://expo.dev
3. **Log in the CLI:**
   ```bash
   eas login
   ```

That completes the infra. Nothing else is required before scaffolding the app.

---

## Networking: phone ↔ Mac (read before wiring the API)

Expo Go runs on your **phone**, so `localhost` / `127.0.0.1` point at the phone, not the
Mac. Two consequences when the app starts talking to the backend:

- **App points at the Mac's LAN IP**, not localhost. This Mac is currently
  **`192.168.1.38`** — so the API base URL will be `http://192.168.1.38:8000`.
  ⚠️ This IP is DHCP-assigned and can change on reconnect/reboot. Re-check with:
  ```bash
  ipconfig getifaddr en0        # Wi-Fi; try en1 if blank
  ```
- **Backend must bind to all interfaces**, not just loopback. Start uvicorn with
  `--host 0.0.0.0` so the phone can reach it:
  ```bash
  cd backend && source .venv/bin/activate
  uvicorn app.main:app --reload --host 0.0.0.0
  ```
- **Same Wi-Fi network** for phone and Mac. Corporate/campus networks that isolate
  clients ("AP isolation") will block this — use a phone hotspot or a home network.
- **CORS:** React Native's native `fetch` does **not** enforce CORS (that's a browser
  rule), so the native app is unaffected. If you ever run the app in Expo's *web* preview,
  the Mac's LAN origin would need to be allowed in the backend CORS config.

---

## When you outgrow Expo Go

You'll need to move off the plain Expo Go runtime — and install the matching toolchain —
when you either:

- want to run on the **iOS Simulator** → install **Xcode** from the App Store (several GB),
  then `xcode-select` + accept the license; or
- want to run on the **Android Emulator** → install **Android Studio**, an SDK, and an AVD
  image (Java 21 is already present); or
- add a **native module not bundled in Expo Go** (e.g. certain audio/secure-storage/native
  SDKs) → build a **dev build** with `eas build --profile development` (cloud build, no
  local toolchain needed) or `npx expo run:ios` / `run:android` (needs the local toolchain
  above).

None of this is needed to start. Revisit when a feature actually requires it.

---

## Next step (not part of infra)

When you're ready to scaffold: an Expo TypeScript + expo-router app lands in `mobile/`
alongside `backend/` and `frontend/` (monorepo). It will carry an API client wired to the
v2 auth flow (`register → verify-otp → tokens`, `login`, `refresh`, `logout`, `me`) with
secure token storage. The `frontend/` Next.js app stays untouched per the v2 conventions.
