from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/barber_kombat"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Telegram
    telegram_bot_token: str = ""
    telegram_mini_app_url: str = ""

    # YClients
    yclients_partner_token: str = ""
    yclients_user_token: str = ""
    yclients_company_id: str = ""
    yclients_webhook_secret: str = ""

    # Yandex Forms (guest survey) webhook — shared secret sent by the form.
    yandex_forms_secret: str = ""

    # DataHeroes (Platrum BFF) scraper — pulls quality-control call tasks.
    dataheroes_enabled: bool = False
    dataheroes_email: str = ""
    dataheroes_password: str = ""
    dataheroes_company: str = ""  # workspace code in the BFF path, e.g. "GCB2"

    # WhatsApp (optional — GreenAPI)
    whatsapp_api_url: str = ""
    whatsapp_api_token: str = ""
    whatsapp_instance_id: str = ""

    # Review request
    review_form_url: str = ""
    review_request_delay_minutes: int = 30
    # When False, MAKON does not send its own WhatsApp review requests. The
    # customer collects reviews through DataHeroes (connected to the same
    # YClients), so this defaults off to avoid double-messaging clients.
    # See docs/integrations/dataheroes.md. Set REVIEW_REQUESTS_ENABLED=true
    # only if MAKON owns the review channel.
    review_requests_enabled: bool = False

    # JWT
    jwt_secret: str = "change-this-to-a-random-secret-at-least-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # App
    app_env: str = "development"
    app_debug: bool = True
    log_level: str = "INFO"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


settings = Settings()
