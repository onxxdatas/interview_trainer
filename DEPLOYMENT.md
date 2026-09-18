# Deploying to Render — for free, no card

Render's **Background Worker** service type (what the original Blueprint
used) has no free tier — that's why it asked for payment details. This
guide uses Render's **free Web Service** plan instead, which costs
nothing and normally doesn't require a card at all.

Two adjustments come with using the free tier, both already handled by
the code in this repo:

1. **A free Web Service must bind a port and answer HTTP requests**, or
   Render considers the deploy unhealthy. The bot's actual job (Telegram
   long polling) doesn't need this, so `app/web.py` runs a one-route
   health-check server (`/health`) alongside the polling loop just to
   satisfy that requirement. `app/main.py` starts it automatically
   whenever a `PORT` environment variable is present (Render sets this
   for you).
2. **Free Web Services have no persistent disk** — the filesystem resets
   on every restart/redeploy, which would wipe a local SQLite file. So on
   this plan you point `DATABASE_URL` at a free *external* Postgres
   instead (Supabase or Neon both have a real free-forever tier with no
   card). Locally, or on any host that does have a disk, SQLite still
   works exactly as before — no code changes either way.

## Step 1 — Free Postgres (Supabase, no card)

1. Go to [supabase.com](https://supabase.com) → sign up (GitHub login is
   fine) → **New project**. No payment method is requested for the free
   tier.
2. Once it's created: **Project Settings → Database → Connection string**
   → copy the **URI** (it looks like
   `postgresql://postgres:[password]@[host]:5432/postgres`).
3. Rewrite the scheme for SQLAlchemy's async driver:
   ```
   postgresql+asyncpg://postgres:[password]@[host]:5432/postgres
   ```
   That's your `DATABASE_URL` for the next step.

   *(Neon.tech is a fine alternative — same idea, same free tier, same
   URL rewrite.)*

## Step 2 — Deploy the bot on Render (free Web Service)

1. Push this project to GitHub.
2. Render Dashboard → **New → Web Service** (not Background Worker) →
   connect your repo.
3. Settings:
   - **Runtime**: Python 3
   - **Plan**: **Free**
   - **Build Command**: `pip install -e ".[postgres]"`
   - **Start Command**: `python -m app.main`
   - **Health Check Path**: `/health`
4. Environment variables:

   | Key | Value |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | from BotFather |
   | `ALLOWED_TELEGRAM_USER_ID` | your numeric Telegram user ID |
   | `GEMINI_API_KEY` | from Google AI Studio |
   | `GEMINI_MODEL` | `gemini-2.5-flash` |
   | `DATABASE_URL` | the `postgresql+asyncpg://...` URL from Step 1 |
   | `DEFAULT_INTERVAL_MINUTES` | `15` |
   | `LOG_LEVEL` | `INFO` |

   (Render sets `PORT` itself — don't add it manually.)
5. Deploy. Watch the **Logs** tab for `Starting polling...` and
   `Health-check server listening...`. Message your bot and confirm
   `/start` works.

Alternatively, click **New → Blueprint** and point it at this repo —
`render.yaml` already describes the free Web Service above, so Render
will propose it directly; you'll still be asked to paste in `DATABASE_URL`
and the two secrets since those are marked `sync: false`.

## Step 3 — Keep it awake (free, no card)

Free Web Services sleep after 15 minutes with no inbound HTTP traffic,
which would pause your scheduled questions. Keep it awake with a free
pinger:

1. Go to [cron-job.org](https://cron-job.org) → free account (no card).
2. Create a job that GETs `https://<your-app>.onrender.com/health` every
   10 minutes.

That's it — the ping hits the health-check route from `app/web.py`,
which keeps the service warm without touching the bot logic at all.

## Verifying it's working

- `/start` in Telegram replies immediately.
- `/question` returns a question within a couple seconds.
- Replying with an answer gets a scored evaluation back (confirms Gemini
  connectivity).
- Restart the service manually from the Render dashboard and confirm
  `/stats` still shows your prior history — this proves the external
  Postgres persistence is actually working (a local SQLite file would
  NOT survive this on the free plan).

## If you'd rather not use any third-party host at all

The genuinely simplest $0 option is running it on your own machine:

```bash
cd interview_trainer
source .venv/bin/activate
mkdir -p data
python -m app.main
```

This uses local SQLite (no Postgres needed) and just needs the machine to
stay on and connected. No account, no card, no sleeping — but it's only
running while your machine is.

## Troubleshooting

- **Render still asks for a card**: double check you picked **Web
  Service**, not **Background Worker**, and **Free** plan — Background
  Workers require a paid plan even at the smallest size.
- **Deploy fails health checks**: confirm `PORT` isn't manually
  overridden in your env vars (Render injects it) and that
  `healthCheckPath` is `/health`.
- **`/stats` resets after every restart**: `DATABASE_URL` isn't actually
  pointing at Postgres (check for a stray default `sqlite+aiosqlite://`
  left in the environment variables).
- **Evaluations always fail with the fallback message**: check
  `GEMINI_API_KEY` / `GEMINI_MODEL`.
- **Someone else can use your bot**: set `ALLOWED_TELEGRAM_USER_ID`.

## If you want the paid Background Worker version instead

It's simpler in one way (no health server, no external DB needed — a
persistent disk just works) and was the original approach. It needs
Render's Starter plan (~$7/mo) and a card. If you ever want it, the
pieces are: service `type: worker` instead of `web`, no `PORT`/health
server involved, a `disk` block mounted at `data/`, and
`DATABASE_URL=sqlite+aiosqlite:///./data/interview_trainer.db`. Not
included here since you're avoiding payment for now.
