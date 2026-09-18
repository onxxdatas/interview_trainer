# Deploying to Render

This bot uses Telegram long polling (no public HTTP endpoint needed), so it
runs as a Render **Background Worker** — the right service type for a
long-running process that isn't answering HTTP requests.

Two things worth knowing about Render before you deploy (current as of
this writing — check Render's own docs/pricing page if anything looks
different, since plans/pricing do change):

- **Background Workers require a paid instance** — there's no free-tier
  background worker on Render. The cheapest instance (Starter, ~$7/mo) is
  enough for this bot.
- **The filesystem is ephemeral by default.** Since this project uses
  SQLite, your training history would be wiped on every redeploy/restart
  unless you attach a **persistent disk** (also paid-plan only) or switch
  to a managed database. Both options are covered below — pick one.

## Option A — Background Worker + persistent disk (simplest, keeps SQLite)

1. Push this project to a GitHub (or GitLab) repository.
2. In the Render Dashboard: **New → Blueprint**, point it at your repo.
   Render will read `render.yaml` (included in this project) and propose
   a Background Worker service. Alternatively, create the service
   manually with **New → Background Worker** and configure by hand using
   the values below.
3. Service settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -e .`
   - **Start Command**: `python -m app.main`
4. Add a **Disk** (Service → Disks → Add Disk):
   - **Mount path**: `/opt/render/project/src/data`
   - **Size**: 1 GB is plenty for a personal bot.
   - This matches `DATABASE_URL=sqlite+aiosqlite:///./data/interview_trainer.db`,
     since the app's working directory on Render is the repo root.
5. Set environment variables (Service → Environment):

   | Key | Value |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | from BotFather |
   | `ALLOWED_TELEGRAM_USER_ID` | your numeric Telegram user ID |
   | `GEMINI_API_KEY` | from Google AI Studio |
   | `GEMINI_MODEL` | `gemini-2.5-flash` (or whatever you have access to) |
   | `DATABASE_URL` | `sqlite+aiosqlite:///./data/interview_trainer.db` |
   | `DEFAULT_INTERVAL_MINUTES` | `15` |
   | `LOG_LEVEL` | `INFO` |

   Never commit these — set them only in the Render dashboard.
6. Deploy. Check the **Logs** tab for `Starting polling...`. Message your
   bot on Telegram and confirm `/start` responds.
7. Every subsequent `git push` to your connected branch auto-redeploys
   (if `autoDeploy: true`, as in `render.yaml`). Because the disk is
   persistent, your training data survives redeploys.

**Note on the disk:** adding a disk disables zero-downtime deploys — a
redeploy briefly stops the old instance before starting the new one.
For a personal bot that's irrelevant (you'll just miss a scheduled
question by a few seconds if it lands exactly then).

## Option B — Background Worker + managed Postgres (more robust)

If you'd rather not depend on a disk at all, use Render's managed
Postgres instead of SQLite (Render's free Postgres expires after 30 days;
a paid instance is persistent indefinitely):

1. In Render: **New → PostgreSQL**. Note the **Internal Database URL** it
   gives you.
2. In your Background Worker's environment variables, set:
   ```
   DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>/<dbname>
   ```
   (take Render's internal connection string and swap the scheme to
   `postgresql+asyncpg`).
3. Add `asyncpg` to the project's dependencies:
   ```bash
   pip install asyncpg
   ```
   and add `"asyncpg"` to the `dependencies` list in `pyproject.toml`,
   then commit and push.
4. No other code changes are needed — the SQLAlchemy models and every
   query in `app/database/repositories.py` are database-agnostic.
5. Skip the disk step from Option A entirely; you don't need one.

## Verifying it's actually working

- `/start` in Telegram should get an immediate reply.
- `/question` should return a question within a couple of seconds
  (confirms Gemini connectivity isn't needed for question selection).
- Reply to that question with any text; you should get a scored
  evaluation back within a few seconds (confirms Gemini connectivity).
- Wait for (or temporarily set `/interval 5` to shorten) the scheduled
  interval and confirm a question arrives on its own.
- Restart the service manually from the Render dashboard (Manual Deploy
  → Deploy latest commit, or the restart button) and confirm `/stats`
  still shows your prior history — this proves persistence is working.

## Troubleshooting

- **Bot doesn't respond at all**: check Render logs for a crash on
  startup — usually a missing/incorrect `TELEGRAM_BOT_TOKEN`.
- **Evaluations always fail with the fallback message**: check
  `GEMINI_API_KEY` and `GEMINI_MODEL` — an invalid model name is the
  most common cause.
- **History resets after every deploy**: you're on Option A without a
  disk attached (or the disk's mount path doesn't match `DATABASE_URL`),
  or on Option B without `DATABASE_URL` actually pointing at Postgres.
- **Someone else can use your bot**: set `ALLOWED_TELEGRAM_USER_ID`.
