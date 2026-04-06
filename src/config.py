"""Configuration loader: YAML config + env var overrides."""

import os
import yaml


DEFAULT_CONFIG = {
    "download_dir": "~/Downloads/x-media",
    "db_path": "downloads.db",
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
    },
    "xurl": {
        "likes_per_fetch": 100,
        "bin": "",
    },
}

ENV_MAP = {
    "XM_DOWNLOAD_DIR": "download_dir",
    "XM_TELEGRAM_BOT_TOKEN": "telegram.bot_token",
    "XM_TELEGRAM_CHAT_ID": "telegram.chat_id",
}


def _deep_set(d: dict, key_path: str, value):
    keys = key_path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        # Default to config.yaml in project root
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml"
        )

    config = {
        "download_dir": DEFAULT_CONFIG["download_dir"],
        "db_path": DEFAULT_CONFIG["db_path"],
        "telegram": dict(DEFAULT_CONFIG["telegram"]),
        "xurl": dict(DEFAULT_CONFIG["xurl"]),
    }

    if os.path.exists(config_path):
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
        for key in file_config:
            if isinstance(file_config[key], dict) and isinstance(config.get(key), dict):
                config[key].update(file_config[key])
            else:
                config[key] = file_config[key]

    for env_key, config_key in ENV_MAP.items():
        val = os.environ.get(env_key)
        if val:
            _deep_set(config, config_key, val)

    config["download_dir"] = os.path.expanduser(config["download_dir"])

    # Resolve db_path relative to project root
    if not os.path.isabs(config["db_path"]):
        config["db_path"] = os.path.join(
            os.path.dirname(config_path) if config_path else "",
            config["db_path"]
        )

    return config
