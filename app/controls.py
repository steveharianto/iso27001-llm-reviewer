import yaml
from pathlib import Path
from .config import DATA_DIR


def load_controls():
    controls_path = DATA_DIR / "iso27001_controls.yaml"
    with open(controls_path, "r") as f:
        return yaml.safe_load(f)


def get_control(control_id: str):
    controls = load_controls()
    for c in controls:
        if c["id"] == control_id:
            return c
    return None
