import copy
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, get_args

ControlType = Literal[
    "dropdown",
    "multiline",
    "size",
    "input",
    "seed",
    "lora",
]


class InvalidControlValue(ValueError):
    def __init__(self, name: str, reason: str):
        super().__init__(f"{name}: {reason}")


_SEED_MAX = 2**53 - 1  # JS number precision limit. Do not raise this to 2**64 - 1.


def _check_dropdown(name: str, raw: object, control: dict) -> object:
    if not isinstance(raw, str) or raw not in control["options"]:
        raise InvalidControlValue(name, "invalid")
    option = control["options"][raw]
    if isinstance(option, dict) and option.get("disabled"):
        raise InvalidControlValue(name, "invalid")
    return raw


def _check_multiline(name: str, raw: object, control: dict) -> str:
    if not isinstance(raw, str):
        raise InvalidControlValue(name, "invalid")
    if len(raw) > control["max_length"]:
        raise InvalidControlValue(name, "too long")
    return raw


def _check_input(name: str, raw: object, control: dict) -> object:
    kinds = (int,) if control["value_kind"] == "int" else (int, float)
    if isinstance(raw, bool) or not isinstance(raw, kinds):
        raise InvalidControlValue(name, "invalid")
    if not (control["min"] <= raw <= control["max"]):
        raise InvalidControlValue(name, "invalid")
    return raw


def _check_seed(name: str, raw: object, control: dict) -> object:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise InvalidControlValue(name, "invalid")
    if not (raw == -1 or 0 <= raw <= _SEED_MAX):
        raise InvalidControlValue(name, "invalid")
    return raw


def _check_size(name: str, raw: object, control: dict) -> object:
    if not isinstance(raw, dict) or set(raw) != {"preset", "highres", "landscape"}:
        raise InvalidControlValue(name, "invalid")
    if not isinstance(raw["preset"], str) or raw["preset"] not in control["presets"]:
        raise InvalidControlValue(name, "invalid")
    for flag in ("highres", "landscape"):
        if not isinstance(raw[flag], bool):
            raise InvalidControlValue(name, "invalid")
    return raw


def _lora_file(name: str, file: object, allowed: set[str], seen: set[str]) -> str:
    """One lora file: it must be a declared option, and it must not repeat."""
    if not isinstance(file, str) or file not in allowed:
        raise InvalidControlValue(name, "invalid")
    if file in seen:
        raise InvalidControlValue(name, "duplicate")
    return file


def _lora_strength(name: str, strength: object, limits: dict) -> float:
    """One lora strength: a real number inside the declared range."""
    if isinstance(strength, bool) or not isinstance(strength, (int, float)):
        raise InvalidControlValue(name, "invalid")
    if not (limits["min"] <= strength <= limits["max"]):
        raise InvalidControlValue(name, "invalid")
    return strength


def _check_lora(name: str, raw: object, control: dict) -> object:
    if not isinstance(raw, list):
        raise InvalidControlValue(name, "invalid")
    allowed = set(control["options"])
    limits = control["strength"]
    seen: set[str] = set()
    entries = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"file", "strength"}:
            raise InvalidControlValue(name, "invalid")
        file = _lora_file(name, item["file"], allowed, seen)
        seen.add(file)
        entries.append(
            {"file": file, "strength": _lora_strength(name, item["strength"], limits)}
        )
    return entries


def _patch_direct(g: dict, p: dict, value: object) -> None:
    g[p["node"]]["inputs"][p["target"]] = value


def size_dims(control: dict, value: object) -> tuple[int, int]:
    assert isinstance(value, dict)
    preset = control["presets"][value["preset"]]
    dims = preset["highres" if value["highres"] else "standard"]
    width, height = dims["width"], dims["height"]
    return (height, width) if value["landscape"] else (width, height)


def _patch_size(g: dict, p: dict, value: object) -> None:
    width, height = size_dims(p, value)
    g[p["node"]]["inputs"]["custom_width"] = width
    g[p["node"]]["inputs"]["custom_height"] = height


def _patch_lora(g: dict, p: dict, value: object) -> None:
    entries = value
    assert isinstance(entries, list)
    g[p["node"]]["inputs"]["loras"] = {
        "__value__": [
            {"name": e["file"], "strength": e["strength"], "active": True}
            for e in entries
        ]
    }
    g[p["node"]]["inputs"]["text"] = ""


@dataclass(frozen=True, slots=True)
class _Kind:
    validate: Callable[[str, object, dict], object]
    patch: Callable[[dict, dict, object], None]
    required: tuple[str, ...]
    default_factory: Callable[[], object] | None = None


_KINDS: dict[ControlType, _Kind] = {
    "dropdown": _Kind(_check_dropdown, _patch_direct, ("node", "target", "options")),
    "multiline": _Kind(
        _check_multiline, _patch_direct, ("node", "target", "max_length")
    ),
    "input": _Kind(
        _check_input, _patch_direct, ("node", "target", "value_kind", "min", "max")
    ),
    "seed": _Kind(_check_seed, _patch_direct, ("node", "target")),
    "size": _Kind(_check_size, _patch_size, ("node", "presets")),
    "lora": _Kind(
        _check_lora, _patch_lora, ("node", "options", "strength"), default_factory=list
    ),
}

if set(_KINDS) != set(get_args(ControlType)):
    raise RuntimeError("control types and behaviors are out of sync")


def _user_controls(parameters: dict) -> dict:
    return {**parameters["basic"], **parameters["advanced"]}


def _kind(control: dict) -> _Kind:
    kind = _KINDS.get(control["type"])
    if kind is None:
        raise RuntimeError(f"unknown control type {control['type']!r}")
    return kind


def validate(parameters: dict, params: dict) -> dict:
    controls = _user_controls(parameters)
    extra = [k for k in params if k not in controls]
    if extra:
        raise InvalidControlValue(extra[0], "unexpected")
    values = {}
    for name, control in controls.items():
        kind = _kind(control)
        if name in params:
            raw = params[name]
        elif kind.default_factory is None:
            raise InvalidControlValue(name, "missing")
        else:
            raw = kind.default_factory()
        values[name] = kind.validate(name, raw, control)
    return values


def _apply_bypass(g: dict, p: dict, value: object) -> None:
    bypass = p.get("bypass")
    if bypass is None or value != bypass["at"]:
        return
    rewire = bypass["rewire"]
    g[rewire["node"]]["inputs"][rewire["input"]] = [
        rewire["to"]["node"],
        rewire["to"]["slot"],
    ]


def patch(graph: dict, parameters: dict, values: dict) -> dict:
    g = copy.deepcopy(graph)
    for p in parameters["hidden"].values():
        g[p["node"]]["inputs"][p["target"]] = p["value"]
    for name, p in _user_controls(parameters).items():
        _kind(p).patch(g, p, values[name])
        _apply_bypass(g, p, values[name])
    return g


def all_of_type(parameters: dict, typ: ControlType) -> list[tuple[str, dict]]:
    return [
        (name, control)
        for name, control in _user_controls(parameters).items()
        if control["type"] == typ
    ]


def one_of_type(parameters: dict, typ: ControlType) -> tuple[str, dict]:
    matches = all_of_type(parameters, typ)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one {typ!r} control, found {len(matches)}"
        )
    return matches[0]


def resolve_seed(seed: int) -> int:
    if seed == -1:
        return random.randint(0, _SEED_MAX)
    return seed


def _check_positive_int(where: str, control: dict, key: str) -> None:
    if key not in control:
        return
    value = control[key]
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RuntimeError(f"{where}: {key} must be a positive int, got {value!r}")


def check_declaration(parameters: dict, workflow_id: str) -> None:
    for name, control in _user_controls(parameters).items():
        where = f"{workflow_id}.{name}"
        for key in _kind(control).required:
            if key not in control:
                raise RuntimeError(f"{where}: {control['type']} control needs {key}")
        _check_positive_int(where, control, "max_length")
