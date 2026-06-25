import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "config.json"
_DEFAULTS: dict = {"advance_minutes": 15}


def get_config() -> dict:
    if not _CONFIG_PATH.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        return {**_DEFAULTS, **data}
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def save_config(data: dict) -> None:
    current = get_config()
    current.update(data)
    _CONFIG_PATH.write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
