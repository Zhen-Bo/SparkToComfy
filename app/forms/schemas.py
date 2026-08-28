from typing import Literal

from app.jobs.controls import ControlType
from app.models import CustomModel


class DropOption(CustomModel):
    label: str
    disabled: bool | None = None


class Size(CustomModel):
    width: int
    height: int


class SizePreset(CustomModel):
    label: str
    icon: str
    standard: Size
    highres: Size


class LoraStrength(CustomModel):
    min: int | float
    max: int | float
    step: int | float
    default: int | float


class Control(CustomModel):
    type: ControlType
    value_kind: Literal["int", "float"] | None = None
    display: str | None = None
    default: str | int | float | None = None
    options: dict[str, str | DropOption] | None = None
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    strength: LoraStrength | None = None
    presets: dict[str, SizePreset] | None = None
    max_length: int | None = None


class Parameters(CustomModel):
    basic: dict[str, Control]
    advanced: dict[str, Control]


class WorkflowItem(CustomModel):
    id: str
    name: str
    parameters: Parameters
