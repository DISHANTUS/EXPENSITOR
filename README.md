# Expensitor

**A calendar-first personal-finance companion that observes how you actually
spend, models it, and helps you plan — deterministically, and offline when it
has to be.**

Expensitor isn't another form to fill in. It watches the shape of your money
over time, tells you what today did for your goals, notices when a habit shifts,
and helps you decide whether a planned purchase is actually affordable — using a
domain-specific intelligence engine written as plain, explainable code. No paid
LLM APIs; an optional local model adds conversational polish but is never
required.

---

## What it does

**Everyday money**
- Multi-currency income & expenses, each stored with its original amount,
  currency, and an exchange-rate snapshot — money is never a float.
- A calendar-first home with a living companion (a custom-painted animated
  face with moods) instead of a dashboard of numbers.
- An **end-of-day report**: what you kept against today's allowance, your
  current streak, and what's left to reach your nearest goal.

**Capture with less typing**
- **Scan a receipt** → on-device OCR (Google ML Kit, offline) reads the total
  and line items and fills the expense for you. The image never leaves the
  phone.
- **Bank-SMS understanding** → parses the "Rs 50 debited … UPI to …" texts every
  UPI/card payment triggers into a transaction you confirm (provider-agnostic:
  works whatever app you paid with).
- **Adaptive reasons** → the reasons you give for spends become one-tap chips,
  ranked for the amount you're entering. Type a new one today, tap it tomorrow.
- **Price learning** → each confirmed receipt teaches what *you* usually pay:
  "Milk 1L — ₹60 (you usually pay ₹58)."

**Understanding & planning**
- A behavioural profile derived from real activity; savings goals with an
  honest three-scenario (worst / expected / best) projection and user-driven
  recovery.
- **Future-Me forecasting** — levers, opportunity cost, and multiple paths to a
  goal.
- A **diary** with branching follow-ups ("you said fruits — which ones?") and
  pattern learning ("you've mentioned mango on 5 of the last 12 days — usually a
  Thursday"), reported as facts, never motives.
- **Festival awareness** for India (incl. Tamil Nadu) and Japan — real,
  cross-checked dates, with "last time this cost you ₹X more than a normal
  fortnight" measured from *your own* ledger.

**Voice & presence**
- Speak to the companion and hear it back (on-device TTS / STT), with a mood and
  personality system.

---

## Design principles

- **Deterministic first.** The financial reasoning is real, testable, explainable
  code — not a prompt. It runs offline and gives the same answer twice. An
  optional local model (Ollama) is used only for conversational phrasing and
  free-text understanding, always with a rules-based fallback, and never a paid
  API.
- **Never invent a number.** Every figure a user sees is read from their own
  data. With no history, the app says so rather than guessing.
- **Your data is yours.** Learning (reasons, prices, patterns) improves *your*
  experience on *your* account — it is not pooled into a shared model.
- **Confirm, don't auto-record.** Captured transactions and scanned receipts are
  candidates the user confirms; a misread costs a tap, never a phantom expense.

---

## Tech stack

**Backend** — FastAPI · SQLAlchemy 2.0 (async) · Pydantic v2 · Alembic ·
PostgreSQL 16 · Docker. Deployed on Render with a managed Postgres.

**Mobile** — Flutter · Material 3 · Riverpod · GoRouter · Google ML Kit
(on-device text recognition) · flutter_tts / speech_to_text · local
notifications.

**Intelligence** — pure-Python deterministic engines (projection, feasibility,
behavioural profiling, savings, pattern detection). Optional local Ollama for
narration and free-text intent, gated behind a rules fallback.

**Quality** — 1,100+ backend tests and 220+ Flutter tests; every schema change
covered by an Alembic migration verified for fresh-install and downgrade.

---

## Project layout

```
EXPENSITOR/
├── backend/                 # FastAPI service
│   ├── app/
│   │   ├── api/v1/          # HTTP routers
│   │   ├── core/            # config, database, security
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── services/        # business logic (derive-on-read)
│   │   ├── intelligence/    # deterministic engines + optional model layer
│   │   └── seed/            # idempotent currency/category seeds
│   ├── alembic/             # migrations
│   └── tests/
├── mobile/                  # Flutter app
│   └── lib/
│       ├── core/            # theme, companion, nav, api client, cache
│       └── features/        # home, ledger, diary, capture, budget, …
├── docker-compose.yml
└── render.yaml              # deployment blueprint
```

---

## Getting started

### Backend (Docker)

```bash
cp .env.example .env         # set SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build    # migrations + seeds run on start
```

- API docs: http://localhost:8000/docs
- Health:   http://localhost:8000/api/v1/health

Run the backend tests:

```bash
docker compose exec api python -m pytest -q
```

### Mobile (Flutter)

```bash
cd mobile
flutter pub get
# point the app at your backend (defaults to the hosted API otherwise)
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
```

Run the Flutter tests:

```bash
cd mobile && flutter test
```

---

## Notes

- Money is stored as `NUMERIC`, never a float. Every income/expense keeps its
  original amount, currency, exchange-rate snapshot, and base-currency value.
- The intelligence layer is **derive-on-read** — no background scheduler; reports
  and patterns are computed from stored facts when requested.
- Exchange rates come from a free provider (Frankfurter); no API key required.
