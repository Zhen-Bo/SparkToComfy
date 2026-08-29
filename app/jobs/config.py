from pydantic import Field
from pydantic_settings import SettingsConfigDict

from app.settings import TomlSettings


class EtaSettings(TomlSettings):
    model_config = SettingsConfigDict(toml_table_header=("eta",), env_prefix="ETA__")

    upscale_seconds_per_megapixel: float


class ReconcileSettings(TomlSettings):
    model_config = SettingsConfigDict(
        toml_table_header=("reconcile",), env_prefix="RECONCILE__"
    )

    interval_seconds: float = Field(gt=0)


class RateLimitSettings(TomlSettings):
    model_config = SettingsConfigDict(
        toml_table_header=("rate_limit",), env_prefix="RATE_LIMIT__"
    )

    enabled: bool
    window_minutes: int = Field(ge=1)
    max_generations: int = Field(ge=1)


ETA = EtaSettings()  # pyright: ignore[reportCallIssue]  # values come from app.toml, not constructor arguments
RECONCILE = ReconcileSettings()  # pyright: ignore[reportCallIssue]  # values come from app.toml, not constructor arguments
RATE_LIMIT = RateLimitSettings()  # pyright: ignore[reportCallIssue]  # values come from app.toml, not constructor arguments
