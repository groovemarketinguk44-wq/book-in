from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.orm import Session

from .database import SessionLocal
from .config import settings


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.business = None
        request.state.business_slug = None

        host = request.headers.get("host", "").split(":")[0]
        domain = settings.APP_DOMAIN.split(":")[0]

        slug = None

        # Subdomain detection for production
        if host.endswith(f".{domain}"):
            subdomain = host[: -len(f".{domain}")]
            if subdomain and subdomain not in ("www", "api"):
                slug = subdomain

        # Dev fallback: header or query param
        if not slug:
            slug = request.headers.get("X-Business-Slug") or request.query_params.get(
                "business_slug"
            )

        if slug:
            request.state.business_slug = slug
            db: Session = SessionLocal()
            try:
                from .models import Business
                business = db.query(Business).filter(Business.slug == slug).first()
                request.state.business = business
            finally:
                db.close()

        response = await call_next(request)
        return response
