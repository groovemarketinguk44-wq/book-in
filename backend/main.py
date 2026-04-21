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
    auth,
    bookings,
    categories,
    client,
    email_oauth,
    financials,
    onboarding,
    services,
    settings,
    slots,
    stripe_routes,
    upload,
)
from .services.reminder_worker import start_reminder_scheduler

FRONTEND = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Ensure upload dir exists
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
    auth.router,
    onboarding.router,
    categories.router,
    services.router,
    bookings.router,
    slots.router,
    financials.router,
    settings.router,
    stripe_routes.router,
    email_oauth.router,
    client.router,
    upload.router,
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
