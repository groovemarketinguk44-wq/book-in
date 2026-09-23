import re
import unicodedata
from sqlalchemy.orm import Session


def render_template(template: str, variables: dict) -> str:
    for key, value in variables.items():
        template = template.replace("{{" + key + "}}", str(value or ""))
    return template


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def unique_slug(name: str, db: Session) -> str:
    from .models import Business

    base = slugify(name)
    if not base:
        base = "business"

    slug = base
    counter = 1
    while db.query(Business).filter(Business.slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug
