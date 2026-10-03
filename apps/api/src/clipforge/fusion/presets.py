"""Loader for fusion configuration presets."""

from pathlib import Path

import yaml

from clipforge.fusion.models import FuseConfig

PRESETS_DIR = Path(__file__).parent / "presets"


def load_preset(name: str = "gaming") -> FuseConfig:
    preset_file = PRESETS_DIR / f"{name}.yaml"
    if not preset_file.exists():
        preset_file = PRESETS_DIR / "gaming.yaml"

    if not preset_file.exists():
        return FuseConfig(name=name)

    data = yaml.safe_load(preset_file.read_text(encoding="utf-8"))
    return FuseConfig.model_validate(data)
