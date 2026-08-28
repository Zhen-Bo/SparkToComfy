from pydantic_settings import SettingsConfigDict

from app.settings import TomlSettings


class ComfyUISettings(TomlSettings):
    model_config = SettingsConfigDict(
        toml_table_header=("comfyui",), env_prefix="COMFYUI__"
    )

    url: str


SETTINGS = ComfyUISettings()  # pyright: ignore[reportCallIssue]  # values come from app.toml, not constructor arguments
