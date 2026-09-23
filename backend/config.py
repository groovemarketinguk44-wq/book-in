from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:password@localhost/bookin"
    SECRET_KEY: str = "changeme-in-production-use-random-256-bit-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID: str = ""          # legacy — maps to Pro
    STRIPE_PRO_PRICE_ID: str = ""      # £14.99/month
    STRIPE_ULTRA_PRICE_ID: str = ""    # £39.99/month
    STRIPE_WHATSAPP_PRICE_ID: str = ""
    STRIPE_SMS_PRICE_ID: str = ""
    STRIPE_TRIAL_DAYS: int = 14        # free trial (signup only)
    STRIPE_FIRST_MONTH_COUPON: str = ""  # 50% off first month coupon ID for Pro/Ultra

    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@book-in.online"
    SENDGRID_FROM_NAME: str = "Book-In"

    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""  # e.g. whatsapp:+14155238886

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/email/google/callback"

    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT_ID: str = "common"
    MICROSOFT_REDIRECT_URI: str = "http://localhost:8000/api/email/microsoft/callback"

    APP_DOMAIN: str = "localhost"
    APP_URL: str = "http://localhost:8000"
    UPLOAD_DIR: str = "./uploads"

    class Config:
        env_file = ".env"


settings = Settings()
