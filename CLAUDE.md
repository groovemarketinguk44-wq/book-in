# Book-In

Booking SaaS for salons: online booking pages, Stripe £9.99/mo subscriptions, SMS/WhatsApp reminders (Twilio), email (SendGrid), Google/Microsoft calendar sync. Domain book-in.online.

## Stack

FastAPI + SQLAlchemy (PostgreSQL in prod, SQLite locally), frontend in /frontend, docker-compose for local

## Commands

```bash
# install
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
# run
uvicorn backend.main:app --reload --port 8000
# test
(no automated tests yet: run it and check the changed pages by hand)
```

## Deploy

Fly app `book-in` via GitHub Action `.github/workflows/fly-deploy.yml` on push to main (needs FLY_API_TOKEN repo secret).

## Environment variables (names only; values live in Fly secrets / local .env, never in git)

DATABASE_URL SECRET_KEY ALGORITHM STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET STRIPE_PRICE_ID SENDGRID_API_KEY SENDGRID_FROM_EMAIL SENDGRID_FROM_NAME TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_PHONE_NUMBER GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GOOGLE_REDIRECT_URI MICROSOFT_CLIENT_ID MICROSOFT_CLIENT_SECRET MICROSOFT_TENANT_ID MICROSOFT_REDIRECT_URI APP_DOMAIN APP_URL

Needed in a cloud session: SECRET_KEY (any dev value); others only for those integrations. Pushing to main deploys!

## Conventions

- Work on a branch and open a PR; Ben merges. Never commit secrets or .env files.
- Keep changes small and explain them in plain words.
- Ben's defaults for his apps: OneSignal push alerts, an admin Visitors tab, full SEO (landing pages, sitemap) where it fits.
