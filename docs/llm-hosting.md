# Hosting the chat LLM (Stage 2)

The chat's LLM brain (`app/intelligence/companion/llm_router.py`) is an **intent
router**: it reads a message and decides which existing engine handles it. It never
does the math — anything about the user's own money is answered by the deterministic
engines (the source of truth). When no model is reachable, the router is skipped and
the deterministic chat answers exactly as before. So turning the LLM on is **safe and
reversible** — flip one env var.

## How the backend reaches a model

Config (`app/core/config.py`), all overridable by env:

| Var | Dev (`.env`) | Meaning |
|-----|--------------|---------|
| `OLLAMA_ENABLED` | `true` | Master switch. The router only runs when this is true. |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Where Ollama lives. |
| `OLLAMA_MODEL` | `qwen3:8b` | The model to call. |
| `OLLAMA_TIMEOUT_SECONDS` | `25` | Hard cap per call; on timeout → deterministic fallback. |

Production (Render) currently sets `OLLAMA_ENABLED=false` (render.yaml) — there is no
model on the free tier, so the chat is deterministic there today.

## Option A — try it locally first (free, 5 min)

1. `ollama serve` and `ollama pull qwen3:8b` on your machine.
2. The dev `.env` already points the Docker backend at `host.docker.internal:11434`
   with `OLLAMA_ENABLED=true`.
3. `docker compose up` and chat: "i blew 250 on coffee" → it should route to an
   add-expense preview; "what's the difference between debit and credit?" → a direct
   answer; "weekly report" → the deterministic engine. Watch `ollama_service` metrics.

This is the fastest way to feel the brain and tune the router prompt before paying for
hosting.

## Option B — always-on hosted model (Stage 2)

Run Ollama on a small always-on GPU host so Phone → Render → Model works 24/7,
independent of your laptop.

1. **Provision** a GPU box (RunPod / Vast.ai / Paperspace / a GPU VPS). A 7–8B model
   at q4 needs ~6–8 GB VRAM. `qwen2.5:7b-instruct` is a strong, cheaper pick for
   JSON/intent-following; `qwen3:8b` also works.
2. **Run Ollama** bound publicly: `OLLAMA_HOST=0.0.0.0:11434 ollama serve` and
   `ollama pull qwen2.5:7b-instruct`.
3. **Protect it.** Ollama has no built-in auth. Put it behind a reverse proxy
   (Caddy/nginx) with **HTTPS + a bearer token or an IP allowlist** for Render's
   egress IPs. Never expose port 11434 raw to the internet.
4. **Point Render at it** (render.yaml or dashboard env):
   ```
   OLLAMA_ENABLED=true
   OLLAMA_BASE_URL=https://your-llm-host.example.com
   OLLAMA_MODEL=qwen2.5:7b-instruct
   OLLAMA_TIMEOUT_SECONDS=30      # remote hop is slower than localhost
   ```
   Redeploy. If the host is unreachable, the chat silently falls back to deterministic.

### Privacy note
With a hosted model, chat prompts (which can reference the user's finances) leave the
app to the model host. Self-hosting keeps that under your control; a third-party
inference API would not — and is also ruled out by the project's no-paid-LLM rule.

## What the router does / doesn't do today

- **Routes:** clear actions (add expense / income, move event), navigation
  ("take me to settings"), and general-knowledge / smalltalk answers.
- **Passes through** to the deterministic engines: anything about the user's own
  money, spending, savings, reports, forecasts, who owes them — or when unsure.
- The action grammar it emits (`add <amt> <cat> expense`, `received <amt> income`,
  `move <event> to <YYYY-MM-DD>`) is what the deterministic parser reliably handles.
  Lending and goal-creation pass through until the parser supports them.

- **Narrates results conversationally** (Slice 3): when the brain is on, the engine's
  plain-text answer is rephrased warmly by the model — but through a grounding guard
  that rejects any output which adds/changes a number, money amount, %, date or name,
  falling back to the exact deterministic text. So the math is always the engines';
  the model only changes the wording. Costs one extra ~2.5s model call per answer.
