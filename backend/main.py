import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import engine
from .models import Base
from .middleware import TenantMiddleware
from .config import settings as app_settings
from .routers import (
    admin as admin_router,
    auth,
    bookings,
    categories,
    client,
    email_oauth,
    financials,
    hours,
    onboarding,
    staff as staff_router,
    services,
    settings,
    slots,
    stripe_routes,
    upload,
    usage,
    automations,
    twilio_webhook,
)
from .services.reminder_worker import start_reminder_scheduler

FRONTEND = Path(__file__).parent.parent / "frontend"


def _run_migrations():
    """Add any missing columns to existing tables without full Alembic setup."""
    from sqlalchemy import text, inspect
    is_sqlite = engine.dialect.name == "sqlite"

    with engine.connect() as conn:
        if is_sqlite:
            biz_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(businesses)")).fetchall()]
            for col, defn in [
                ("whatsapp_reminders", "BOOLEAN DEFAULT 0"),
                ("sms_confirmations", "BOOLEAN DEFAULT 0"),
                ("whatsapp_confirmations", "BOOLEAN DEFAULT 0"),
                ("reminder_2h", "BOOLEAN DEFAULT 1"),
                ("stripe_whatsapp_item_id", "TEXT"),
                ("stripe_sms_item_id", "TEXT"),
            ]:
                if col not in biz_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE businesses ADD COLUMN {col} {defn}"))
                        conn.commit()
                    except Exception as e:
                        print(f"[migration] {e}")

            for col, defn in [
                ("google_review_link", "TEXT"),
                ("tracking_phone_number", "TEXT"),
                ("plan", "TEXT DEFAULT 'pro'"),
            ]:
                if col not in biz_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE businesses ADD COLUMN {col} {defn}"))
                        conn.commit()
                    except Exception as e:
                        print(f"[migration] {e}")

            u_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(users)")).fetchall()]
            if "is_platform_admin" not in u_cols:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_platform_admin BOOLEAN DEFAULT 0"))
                    conn.commit()
                except Exception as e:
                    print(f"[migration] {e}")

            bk_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(bookings)")).fetchall()]
            for col, defn in [
                ("staff_id", "INTEGER REFERENCES staff(id)"),
                ("reminder_2h_sent", "BOOLEAN DEFAULT 0"),
                ("review_request_sent", "BOOLEAN DEFAULT 0"),
                ("source", "TEXT"),
            ]:
                if col not in bk_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE bookings ADD COLUMN {col} {defn}"))
                        conn.commit()
                    except Exception as e:
                        print(f"[migration] {e}")
        else:
            for sql in [
                "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS whatsapp_reminders BOOLEAN DEFAULT FALSE",
                "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS sms_confirmations BOOLEAN DEFAULT FALSE",
                "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS whatsapp_confirmations BOOLEAN DEFAULT FALSE",
                "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS reminder_2h BOOLEAN DEFAULT TRUE",
                "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS stripe_whatsapp_item_id TEXT",
                "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS stripe_sms_item_id TEXT",
                "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS google_review_link TEXT",
                "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS tracking_phone_number TEXT",
                "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS plan TEXT DEFAULT 'pro'",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS staff_id INTEGER REFERENCES staff(id)",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS reminder_2h_sent BOOLEAN DEFAULT FALSE",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS review_request_sent BOOLEAN DEFAULT FALSE",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS source TEXT",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_platform_admin BOOLEAN DEFAULT FALSE",
                "ALTER TABLE users ALTER COLUMN business_id DROP NOT NULL",
            ]:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception as e:
                    print(f"[migration] {e}")


def _seed_platform_admin():
    from .database import SessionLocal
    from .models import Business, User
    from .auth import hash_password
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "admin@book-in.online").first()
        if existing:
            # Clean up: detach from dummy business if it exists, ensure is_platform_admin is set
            if existing.business_id is not None:
                dummy = db.query(Business).filter(Business.slug == "_platform").first()
                if dummy and dummy.id == existing.business_id:
                    existing.business_id = None
                    db.flush()
                    db.delete(dummy)
            existing.is_platform_admin = True
            db.commit()
            return
        user = User(
            email="admin@book-in.online",
            password_hash=hash_password("admin123"),
            business_id=None,
            is_platform_admin=True,
        )
        db.add(user)
        db.commit()
        print("[seed] Platform admin created (no business attached)")
    except Exception as e:
        print(f"[seed] {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _seed_platform_admin()
    Path(app_settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    scheduler = start_reminder_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="Book-In API", lifespan=lifespan)

app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static assets
if (FRONTEND / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND / "static")), name="static")

# Uploaded images
_upload_path = Path(app_settings.UPLOAD_DIR)
_upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_upload_path)), name="uploads")

# API routers
for r in [
    admin_router.router,
    auth.router,
    onboarding.router,
    categories.router,
    services.router,
    bookings.router,
    slots.router,
    hours.router,
    staff_router.router,
    financials.router,
    settings.router,
    stripe_routes.router,
    email_oauth.router,
    client.router,
    upload.router,
    usage.router,
    automations.router,
    twilio_webhook.router,
]:
    app.include_router(r)


# ── Frontend HTML routes ───────────────────────────────────────────────────────

def _page(name: str):
    return FileResponse(FRONTEND / name)


@app.get("/")
def index(request: Request):
    # Serve client site if subdomain detected
    if request.state.business:
        return FileResponse(FRONTEND / "client" / "index.html")
    return _page("index.html")


@app.get("/pricing")
def pricing():
    return _page("pricing.html")


@app.get("/login")
def login():
    return _page("login.html")


@app.get("/signup")
def signup_page():
    return _page("signup.html")


@app.get("/onboarding")
def onboarding_page():
    return _page("onboarding.html")


@app.get("/admin")
def admin_page():
    return _page("admin.html")


@app.get("/dashboard")
def dashboard():
    return _page("dashboard.html")


@app.get("/bookings")
def bookings_page():
    return _page("bookings.html")


@app.get("/calendar")
def calendar():
    return _page("calendar.html")


@app.get("/financials")
def financials_page():
    return _page("financials.html")


@app.get("/settings")
def settings_page():
    return _page("settings.html")


# Client booking pages (subdomain or /book/{slug})
@app.get("/book/{slug}")
@app.get("/book/{slug}/service/{service_id}")
@app.get("/book/{slug}/confirm")
def client_book(slug: str, service_id: int = None):
    return FileResponse(FRONTEND / "client" / "index.html")


@app.get("/book/{slug}/confirmation")
def client_confirmation(slug: str):
    return FileResponse(FRONTEND / "client" / "confirmation.html")


# Client subdomain pages
@app.get("/services")
def client_services(request: Request):
    if request.state.business:
        return FileResponse(FRONTEND / "client" / "index.html")
    return _page("dashboard.html")


@app.get("/book")
def client_book_page(request: Request):
    if request.state.business:
        return FileResponse(FRONTEND / "client" / "booking.html")
    return _page("bookings.html")


@app.get("/confirmation")
def client_confirmation_page(request: Request):
    return FileResponse(FRONTEND / "client" / "confirmation.html")
