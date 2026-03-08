import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_parse_cors_origins_from_csv():
    settings = Settings(
        environment="development",
        secret_key="dev-secret-key-1234567890",
        cors_allowed_origins="http://localhost:5173, https://app.example.com",
    )

    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "https://app.example.com",
    ]


def test_settings_reject_default_secret_key_in_production():
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            secret_key="your-secret-key-change-in-production",
            cors_allowed_origins='["https://app.example.com"]',
        )


def test_settings_reject_wildcard_cors_in_production():
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            secret_key="prod-secret-key-1234567890",
            cors_allowed_origins="*",
        )
