# Changelog

Notable changes to Advary, per beta build. Newest first. Dates are YYYY-MM-DD.

The companion is **deterministic by default** — every engine works with no LLM. The
conversational LLM layer is *gated off* (`OLLAMA_ENABLED=false`) until explicitly
rolled out, so builds below behave identically whether or not a model is reachable.

## [Unreleased] — committed on `beta-prep`, not yet deployed

### Added
- **Slice 3 — grounded conversational narration.** When a model is reachable, the
  deterministic engine's answer is rephrased warmly by the LLM, but only through a
  guard that rejects any output which adds/changes a number, money amount, %, date,
  time or name — falling back to the exact deterministic text. The model phrases; the
  engines own every figure.

### Pending
- Push `beta-prep` (deploys the backend action layer + router code; LLM stays off).
- LLM rollout: run the laptop bridge (`scripts/start-llm-bridge.ps1`) and set the
  `OLLAMA_*` env on Render — see `docs/llm-hosting.md`.

---

## [v1.0.0-beta1] — 2026-06-28

First friends-beta baseline. A stable, deterministic-by-default checkpoint taken
**before** the LLM rollout.

### Fixed (from real beta use)
- Login no longer drops every launch — the session is kept through a cold start /
  network blip; only a genuine 401 signs you out.
- Hardware **Back** no longer closes the whole app — non-Home screens return Home,
  and Back during the first-run tour steps through it instead of exiting.
- Chat answers **help & navigation** questions ("take me to settings", "how do I add a
  goal?") instead of replying "add an expense first".
- **Voice audio-session leak** that could silence the phone's ringtones/notifications:
  the mic (STT) and speaker (TTS) are now released on navigation and whenever the app
  is backgrounded.
- Onboarding **name field** is editable again (no stuck backspace / runaway text).
- Budget "Get to know you" **Yes/No** steps (scholarship, part-time) now show their
  question; wizard money fields keep their cursor while typing.

### Added (present but dormant — LLM gated off)
- **Chat → Action Layer:** the text chat can *do* things — "add 250 coffee",
  "got 5000 income", "move trip to Jul 1" → a Yes/Cancel preview → done (deterministic).
- **LLM intent router** that understands a message and routes to the existing engines,
  never inventing numbers; falls back to the deterministic chat on any failure.
- **Laptop LLM bridge** launcher + hosting runbook (`docs/llm-hosting.md`).

### Platform
- Flutter UI (aurora theme + living orb), FastAPI + Neon Postgres, deployed on Render.
- Intervention loop, Timeline, Future Me forecasting, budget setup, payables,
  backup/restore, theme system.
- 794 backend tests, 117 client tests green.
