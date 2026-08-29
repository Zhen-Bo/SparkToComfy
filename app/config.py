"""Load the settings and workflows under config/.

Settings are read once at startup, so a bad path or format fails the boot outright.
A WorkflowCatalog holds the workflow declarations and a background task reloads them periodically: the catalog is part of the Runtime, not a module global.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic_settings import SettingsConfigDict

from app.jobs import controls
from app.settings import ROOT, TomlSettings

# The registry a deployment edits.
# It is git-ignored, so the tests read the shipped example instead.
REGISTRY = ROOT / "config" / "workflow.yaml"


class ServerSettings(TomlSettings):
    model_config = SettingsConfigDict(
        toml_table_header=("server",), env_prefix="SERVER__"
    )

    host: str
    port: int
    database: str
    docs: bool
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    log_format: Literal["console", "json"]


SETTINGS = ServerSettings()  # pyright: ignore[reportCallIssue]  # values come from app.toml, not constructor arguments


def load_workflows(registry: Path = REGISTRY) -> dict:
    """Return {workflow_id: {name, parameters, graph}}. All workflows share the size presets."""
    presets = yaml.safe_load(
        (ROOT / "config" / "size.yaml").read_text(encoding="utf-8")
    )["presets"]
    data = yaml.safe_load(registry.read_text(encoding="utf-8"))
    workflows = {}
    for wid, w in data["workflows"].items():
        parameters = yaml.safe_load((ROOT / w["parameter"]).read_text(encoding="utf-8"))
        for _, control in controls.all_of_type(parameters, "size"):
            control["presets"] = presets
        workflows[wid] = {
            "name": w["name"],
            "parameters": parameters,
            "graph": json.loads((ROOT / w["workflow"]).read_text(encoding="utf-8")),
        }
        controls.check_declaration(parameters, wid)
    return workflows


class WorkflowCatalog:
    def __init__(self, registry: Path = REGISTRY) -> None:
        self._registry = registry
        self._workflows = load_workflows(registry)

    def all(self) -> Mapping[str, dict]:
        return self._workflows

    def get(self, workflow_id: str) -> dict | None:
        return self._workflows.get(workflow_id)

    def reload(self) -> None:
        """Swap the whole set. A failed load propagates; the caller decides whether to keep the old one."""
        self._workflows = load_workflows(self._registry)


if __name__ == "__main__":
    wfs = load_workflows()
    assert wfs, "no workflows loaded"
    for wid, w in wfs.items():
        assert w["name"], wid
        assert {"hidden", "basic", "advanced"} <= set(w["parameters"]), wid
        assert isinstance(w["graph"], dict) and w["graph"], wid
        print(f"{wid} OK: {w['name']} — {len(w['graph'])} nodes")
