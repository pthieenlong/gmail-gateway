from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/email_gateway"

    # Email provider: "imap" or "gmail"
    EMAIL_PROVIDER: str = "imap"

    # IMAP
    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_USERNAME: str = ""
    IMAP_PASSWORD: str = ""

    # Gmail API
    GMAIL_CREDENTIALS_FILE: str = "credentials.json"
    GMAIL_TOKEN_FILE: str = "token.json"

    # Storage
    STORAGE_PATH: str = "./storage"

    # Polling
    POLL_INTERVAL_SECONDS: int = 30

    # Webhooks
    WEBHOOK_TIMEOUT_SECONDS: int = 30

    # API Key bảo vệ các endpoint quản trị (webhooks CRUD, dev inject...)
    # Để trống = không cần xác thực (chỉ dùng cho local/dev)
    ADMIN_API_KEY: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
