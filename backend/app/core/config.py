from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./pxnn_it.db"
    JWT_SECRET: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    COOKIE_NAME: str = "pxnn_session"
    APP_URL: str = "http://localhost:8000"
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    # Active plans: pay-per-single ($1) and monthly unlimited ($7.99/mo)
    STRIPE_SINGLE_EXPORT_PRICE_ID: Optional[str] = None
    STRIPE_MONTHLY_UNLIMITED_PRICE_ID: Optional[str] = None
    # Legacy price IDs (kept so existing .env files stay valid; no longer offered)
    STRIPE_CREATOR_PACK_PRICE_ID: Optional[str] = None
    STRIPE_LABEL_PACK_PRICE_ID: Optional[str] = None
    STRIPE_STARTER_MONTHLY_PRICE_ID: Optional[str] = None
    STRIPE_PRO_MONTHLY_PRICE_ID: Optional[str] = None
    STRIPE_LABEL_MONTHLY_PRICE_ID: Optional[str] = None
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    ADMIN_BOOTSTRAP_EMAIL: str = "sjpenn@gmail.com"
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    AI_CLUSTERER_PROVIDER: str = "auto"
    REPLICATE_API_TOKEN: Optional[str] = None
    RESEND_API_KEY: Optional[str] = None
    EMAIL_FROM_ADDRESS: str = "notifications@gedsio.com"

    # Upload guardrails (founder-tunable via site settings; these are the defaults)
    MAX_UPLOAD_FILES: int = 200
    MAX_UPLOAD_FILE_MB: int = 300
    MAX_UPLOAD_BATCH_MB: int = 2048
    ALLOWED_UPLOAD_EXTENSIONS: str = (
        "mp3,wav,aif,aiff,flac,ogg,oga,m4a,aac,wma,alac,opus,mid,midi,"
        "mp4,mov,m4v,zip,ptx,als,flp,logicx,band,rpp,cpr,np3,seq,sesx,stems"
    )

    # Simple per-IP rate limiting for auth endpoints
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REGISTER_PER_WINDOW: int = 10
    RATE_LIMIT_LOGIN_PER_WINDOW: int = 15
    RATE_LIMIT_FORGOT_PER_WINDOW: int = 5
    RATE_LIMIT_WINDOW_SECONDS: int = 300

    # Password reset
    PASSWORD_RESET_TOKEN_MINUTES: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
