import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".messygit"
CONFIG_FILE = CONFIG_DIR / "config.json"

def save_api_key(key: str):
    CONFIG_DIR.mkdir(exist_ok=True)
    config = {"api_key": key}
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def load_api_key():
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    return config.get("api_key")

