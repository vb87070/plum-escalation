"""
Manages source configurations (Gmail accounts, Slack tokens/channels).
Credentials stored in sources_config.json — never exposed in API responses.
"""
import os
import json
from typing import Optional

CONFIG_PATH = os.environ.get("CONFIG_PATH", os.path.join(os.path.dirname(__file__), "sources_config.json"))

_DEFAULT = {
    "gmail": [],
    "slack": {"bot_token": "", "channels": []}
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return _DEFAULT.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure keys exist
        data.setdefault("gmail", [])
        data.setdefault("slack", {"bot_token": "", "channels": []})
        data["slack"].setdefault("bot_token", "")
        data["slack"].setdefault("channels", [])
        return data
    except Exception:
        return _DEFAULT.copy()


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ── Gmail ──────────────────────────────────────
def add_gmail(email: str, app_password: str):
    config = load_config()
    # Remove existing entry for same email
    config["gmail"] = [g for g in config["gmail"] if g["email"] != email]
    config["gmail"].append({
        "email": email,
        "app_password": app_password,
        "last_uid": None,
        "last_polled_at": None,
        "messages_fetched": 0,
        "is_connected": False,
        "error": None,
    })
    save_config(config)


def remove_gmail(email: str):
    config = load_config()
    config["gmail"] = [g for g in config["gmail"] if g["email"] != email]
    save_config(config)


# ── Slack ──────────────────────────────────────
def set_slack_token(bot_token: str):
    config = load_config()
    config["slack"]["bot_token"] = bot_token
    save_config(config)


def add_slack_channel(channel_id: str, channel_name: str = ""):
    config = load_config()
    # Remove if already exists
    config["slack"]["channels"] = [
        c for c in config["slack"]["channels"] if c["channel_id"] != channel_id
    ]
    config["slack"]["channels"].append({
        "channel_id": channel_id,
        "channel_name": channel_name or channel_id,
        "latest_ts": None,
        "last_polled_at": None,
        "messages_fetched": 0,
        "is_connected": False,
        "error": None,
    })
    save_config(config)


def remove_slack_channel(channel_id: str):
    config = load_config()
    config["slack"]["channels"] = [
        c for c in config["slack"]["channels"] if c["channel_id"] != channel_id
    ]
    save_config(config)


# ── Safe public view (no passwords) ───────────
def public_view() -> dict:
    config = load_config()
    return {
        "gmail": [
            {
                "email": g["email"],
                "last_polled_at": g.get("last_polled_at"),
                "messages_fetched": g.get("messages_fetched", 0),
                "is_connected": g.get("is_connected", False),
                "error": g.get("error"),
            }
            for g in config["gmail"]
        ],
        "slack": {
            "has_token": bool(config["slack"].get("bot_token")),
            "channels": [
                {
                    "channel_id": c["channel_id"],
                    "channel_name": c.get("channel_name", c["channel_id"]),
                    "last_polled_at": c.get("last_polled_at"),
                    "messages_fetched": c.get("messages_fetched", 0),
                    "is_connected": c.get("is_connected", False),
                    "error": c.get("error"),
                }
                for c in config["slack"]["channels"]
            ],
        },
    }
