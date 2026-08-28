"""Shared base for every domain setting: read one table of config/app.toml, env wins."""

from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

ROOT = Path(__file__).resolve().parent.parent
TOML = ROOT / "config" / "app.toml"


class TomlSettings(BaseSettings):
    model_config = SettingsConfigDict(toml_file=TOML, extra="forbid")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (env_settings, TomlConfigSettingsSource(settings_cls))
