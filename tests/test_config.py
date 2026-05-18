import os
import tempfile
import pytest


def test_load_config_defaults():
    from src.config import load_config
    config = load_config("/nonexistent/config.yaml")
    assert "download_dir" in config
    assert config["telegram"]["enabled"] is False
    assert config["gallery_dl"]["username"] == ""


def test_load_config_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
download_dir: /tmp/x-media-test
telegram:
  enabled: true
  bot_token: "123:abc"
  chat_id: "456"
""")
        tmp_path = f.name

    from src.config import load_config
    config = load_config(tmp_path)
    assert config["download_dir"] == "/tmp/x-media-test"
    assert config["telegram"]["bot_token"] == "123:abc"
    assert config["telegram"]["chat_id"] == "456"
    os.unlink(tmp_path)


def test_config_env_override():
    os.environ["XM_TELEGRAM_BOT_TOKEN"] = "env-token"
    os.environ["XM_X_USERNAME"] = "env-user"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            "telegram:\n"
            "  bot_token: file-token\n"
            "  chat_id: '1'\n"
            "gallery_dl:\n"
            "  username: file-user\n"
        )
        tmp_path = f.name

    from src.config import load_config
    config = load_config(tmp_path)
    assert config["telegram"]["bot_token"] == "env-token"
    assert config["gallery_dl"]["username"] == "env-user"
    os.environ.pop("XM_TELEGRAM_BOT_TOKEN")
    os.environ.pop("XM_X_USERNAME")
    os.unlink(tmp_path)
