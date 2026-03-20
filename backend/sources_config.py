"""
Manages source configurations (Gmail accounts, Slack tokens/channels).
Credentials can come from:
  1. Environment variables (preferred for Railway deployment)
  2. sources_config.json (used when added via dashboard UI)
"""
import os
import json

CONFIG_PATH = os.environ.get("CONFIG_PATH", os.path.join(os.path.dirname(__file__), "sources_config.json"))

_DEFAULT = {
    "gmail": [],
    "slack": {"bot_token": "", "channels": []}
}


def load_config() -> dict:
    # Start with file config
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("gmail", [])
            data.setdefault("slack", {"bot_token": "", "channels": []})
            data["slack"].setdefault("bot_token", "")
            data["slack"].setdefault("channels", [])
        except Exception:
            data = _DEFAULT.copy()
    else:
        data = _DEFAULT.copy()

    # ── Merge Gmail from env vars ──────────────────────────────
    # Supports: GMAIL_EMAIL, GMAIL_APP_PASSWORD
    # Also supports multiple accounts: GMAIL_EMAIL_1/GMAIL_APP_PASSWORD_1, etc.
    env_gmail_accounts = []

    # Single account
    if os.environ.get("GMAIL_EMAIL") and os.environ.get("GMAIL_APP_PASSWORD"):
        env_gmail_accounts.append({
            "email": os.environ["GMAIL_EMAIL"],
            "app_password": os.environ["GMAIL_APP_PASSWORD"],
        })

    # Multiple accounts (GMAIL_EMAIL_1, GMAIL_EMAIL_2, ...)
    for i in range(1, 6):
        email_key = f"GMAIL_EMAIL_{i}"
        pass_key = f"GMAIL_APP_PASSWORD_{i}"
        if os.environ.get(email_key) and os.environ.get(pass_key):
            env_gmail_accounts.append({
                "email": os.environ[email_key],
                "app_password": os.environ[pass_key],
            })

    # Merge: env accounts override file accounts with same email
    existing_emails = {g["email"] for g in data["gmail"]}
    for env_acc in env_gmail_accounts:
        if env_acc["email"] not in existing_emails:
            data["gmail"].append({
                "email": env_acc["email"],
                "app_password": env_acc["app_password"],
                "last_uid": None,
                "last_polled_at": None,
                "messages_fetched": 0,
                "is_connected": False,
                "error": None,
            })
        else:
            # Update password from env (env takes priority)
            for g in data["gmail"]:
                if g["email"] == env_acc["email"]:
                    g["app_password"] = env_acc["app_password"]

    # ── Merge Slack from env vars ──────────────────────────────
    # Supports: SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, SLACK_CHANNEL_NAME
    if os.environ.get("SLACK_BOT_TOKEN"):
        data["slack"]["bot_token"] = os.environ["SLACK_BOT_TOKEN"]

    if os.environ.get("SLACK_CHANNEL_ID"):
        channel_id = os.environ["SLACK_CHANNEL_ID"]
        channel_name = os.environ.get("SLACK_CHANNEL_NAME", channel_id)
        existing_ids = {c["channel_id"] for c in data["slack"]["channels"]}
        if channel_id not in existing_ids:
            data["slack"]["channels"].append({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "latest_ts": None,
                "last_polled_at": None,
                "messages_fetched": 0,
                "is_connected": False,
                "error": None,
            })

    return data


def save_config(config: dict):
    # Only save non-env entries to file (env entries are always reloaded from env)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"[Config] Could not save config: {e}")


# ── Gmail ──────────────────────────────────────
def add_gmail(email: str, app_password: str):
    config = load_config()
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
