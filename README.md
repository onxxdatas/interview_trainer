# Python Interview Trainer — Telegram Bot

An adaptive, AI-powered Telegram bot that trains you for Python
Software Engineer / Backend Engineer interviews. It asks questions on a
schedule, evaluates your answers with Gemini, tracks per-concept mastery,
and uses spaced repetition to bring weak concepts back more often.

## 1. What it does

- Sends you an interview question every N minutes (default 15, configurable).
- You answer by replying with plain text.
- Gemini evaluates the answer (correctness, missing concepts, incorrect
  claims, a score out of 10) and may ask a sharp follow-up question.
- Per-concept mastery is updated and a spaced-repetition schedule decides
  when that concept should come up again.
- `/interview` starts a live mock-interview session: one question at a
  time, minimal in-the-moment feedback, and a structured assessment at
  the end.
- An unanswered question is never lost — it's marked `OVERDUE` and stays
  in the review queue; it never blocks the next scheduled question.

## 2. Architecture

```
app/
├── bot/
│   ├── handlers/       # start, training loop, stats, interview mode
│   ├── keyboards/      # inline keyboards
│   └── middleware/     # optional single-user access control
├── ai/
│   ├── gemini.py       # google-genai wrapper: structured output + 1 repair retry
│   ├── prompts.py      # all prompt text, centralized
│   ├── schemas.py      # pydantic schemas Gemini's JSON is validated against
│   └── evaluator.py    # evaluation orchestration + safe fallback on API failure
├── training/
│   ├── question_bank.py     # curated question bank (topics/concepts/questions)
│   ├── seed.py               # loads the bank into the DB
│   ├── question_engine.py    # adaptive selection algorithm
│   ├── spaced_repetition.py  # mastery + interval update logic
│   ├── scheduler.py          # APScheduler per-user interval jobs + overdue handling
│   ├── progress.py           # /stats /topics /weak message formatting
│   └── question_rendering.py
├── database/
│   ├── models.py        # SQLAlchemy ORM models
│   ├── database.py      # async engine/session
│   └── repositories.py  # all data access
├── config.py             # environment-based settings
└── main.py                # entrypoint
tests/                      # pytest, Gemini is mocked
```

Responsibilities are kept separate on purpose: Telegram handlers never talk
to the database or Gemini directly except through the `database.repositories`
and `ai.evaluator` modules.

## 3. Adaptive learning, in one paragraph

Every (user, concept) pair has a `ReviewSchedule` row: a mastery score
(0–1), a review interval, and a "next review at" timestamp. On each tick,
the question engine scores every concept by `(1 - mastery)`, how overdue
it is, and whether it's never been asked, then picks a question from that
concept in a difficulty band matched to the current mastery (so it won't
jump straight to CPython internals if fundamentals are still weak).
After each answer, `spaced_repetition.apply_result()` adjusts mastery and
the next interval — correct answers push the interval out (up to 30 days),
incorrect ones reset it to the minimum (15 min by default), and two
incorrect answers in a row floors the interval regardless of the formula,
so a genuinely struggling concept keeps coming back soon.

## 4. Installation (Ubuntu/Linux)

```bash
git clone <your-repo-url> interview_trainer
cd interview_trainer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` and fill in:

```env
TELEGRAM_BOT_TOKEN=...
GEMINI_API_KEY=...
```

### Creating a Telegram bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram.
2. `/newbot`, follow the prompts, copy the token into `TELEGRAM_BOT_TOKEN`.
3. Message [@userinfobot](https://t.me/userinfobot) to get your own numeric
   Telegram user ID, and put it in `ALLOWED_TELEGRAM_USER_ID` so only you
   can use the bot.

### Creating Gemini API access
1. Go to [Google AI Studio](https://aistudio.google.com/apikey) and create
   an API key.
2. Put it in `GEMINI_API_KEY`. Set `GEMINI_MODEL` to whichever current
   Gemini model you have access to (default: `gemini-2.5-flash`).

## 5. Running locally

```bash
mkdir -p data   # sqlite file lives here
python -m app.main
```

The bot uses long polling — no public URL is needed locally.

## 6. Running tests

```bash
pytest
```

Gemini is fully mocked in tests — no API key or network access is required
to run the suite (`tests/conftest.py` sets dummy env vars automatically).

## 7. Database

SQLite by default (`data/interview_trainer.db`), via `DATABASE_URL`. To
move to Postgres later, install `asyncpg` and change:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/interview_trainer
```

No application code changes are needed — SQLAlchemy models and queries
are backend-agnostic. `init_db()` creates tables if they don't exist; for
real schema migrations on Postgres you'd want to introduce Alembic later.

## 8. Commands

| Command | Description |
|---|---|
| `/start` | register and show the main menu |
| `/help` | list commands |
| `/question` | get a question right now |
| `/answer` | reminder: just reply with your answer text |
| `/stats`, `/progress` | overall training stats |
| `/topics` | mastery per topic/concept |
| `/weak` | your weakest concepts right now |
| `/history` | last 10 attempts |
| `/review` | force-review your single weakest concept |
| `/interview` | start a mock interview session |
| `/interval <minutes>` | change question frequency (5–1440 min) |
| `/pause` / `/resume` | pause/resume scheduled questions |
| `/settings` | show current interval/status |

## 9. Security

- Tokens/keys are read only from environment variables, never hardcoded.
- `.env` is gitignored; `.env.example` has no real secrets.
- If `ALLOWED_TELEGRAM_USER_ID` is set, every other Telegram account is
  silently ignored by `AllowedUserMiddleware` — the bot doesn't even
  acknowledge their messages.
- Errors are never surfaced to Telegram with raw exception text that could
  leak internals; Gemini/API failures fall back to a safe, generic message
  and the attempt is still recorded rather than lost.

## 10. Reliability notes

- A restart doesn't lose progress: all state lives in the DB, and on
  startup `TrainingScheduler.load_jobs_from_db()` rebuilds one interval
  job per active user with a deterministic job id, so jobs are never
  duplicated across restarts.
- If Gemini's structured output fails validation once, the evaluator
  retries with a repair prompt; if that also fails, a neutral fallback
  evaluation is recorded instead of losing the attempt or crashing the bot.
- Overdue questions are marked, not deleted, and stay eligible for
  re-selection by the adaptive engine.

## 11. Future work (architected for, not built yet)

- **Voice answers**: `evaluate_answer()` takes plain text, so a voice
  handler just needs to transcribe (e.g. via a speech-to-text API) and
  call the same function — no evaluator changes needed.
- **PostgreSQL**: change `DATABASE_URL`; add Alembic for migrations.
- Web dashboard, richer analytics, more AI-generated question variety.

## 12. Deployment

See `DEPLOYMENT.md` for a step-by-step Render deployment guide.
