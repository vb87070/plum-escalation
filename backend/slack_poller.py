"""
Slack Web API Poller — polls configured channels every 30 seconds.
Requires a Slack Bot Token (xoxb-...) with scopes:
  channels:history, users:read, channels:read

To create a Slack App:
  1. Go to api.slack.com/apps → Create New App → From scratch
  2. OAuth & Permissions → Bot Token Scopes → Add:
       channels:history, users:read, channels:read
  3. Install to Workspace → copy Bot User OAuth Token
  4. Invite bot to each channel: /invite @YourApp
"""
import asyncio
import datetime
import httpx

import sources_config

import os
_PORT = os.environ.get("PORT", "8000")
API_BASE = f"http://localhost:{_PORT}"
POLL_INTERVAL = 30  # seconds


async def ingest_message(source_channel, source_message_id, received_at, sender_name, sender_contact, raw_message):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{API_BASE}/webhook/ingest", json={
                "source_channel": source_channel,
                "source_message_id": source_message_id,
                "received_at": received_at,
                "sender_name": sender_name,
                "sender_contact": sender_contact,
                "raw_message": raw_message,
            })
            return resp.status_code == 201
    except Exception as e:
        print(f"[Slack] Ingest error: {e}")
        return False


async def poll_slack_forever():
    """Background task: poll all configured Slack channels indefinitely."""
    print("[Slack] Poller started.")

    while True:
        config = sources_config.load_config()
        slack_cfg = config.get("slack", {})
        token = slack_cfg.get("bot_token", "")
        channels = slack_cfg.get("channels", [])

        if not token or not channels:
            await asyncio.sleep(POLL_INTERVAL)
            continue

        try:
            from slack_sdk import WebClient
            from slack_sdk.errors import SlackApiError
        except ImportError:
            print("[Slack] slack_sdk not installed. Run: pip install slack_sdk")
            await asyncio.sleep(60)
            continue

        client = WebClient(token=token)

        for i, ch in enumerate(channels):
            channel_id = ch.get("channel_id", "")
            if not channel_id:
                continue

            try:
                kwargs = {"channel": channel_id, "limit": 20}
                latest_ts = ch.get("latest_ts")
                if latest_ts:
                    kwargs["oldest"] = latest_ts

                result = client.conversations_history(**kwargs)
                messages = result.get("messages", [])

                # Process oldest first to keep timestamps in order
                ingested = 0
                new_latest_ts = latest_ts

                for msg in reversed(messages):
                    # Skip bot messages, joins, etc.
                    if msg.get("subtype") or not msg.get("text"):
                        continue
                    if msg.get("bot_id"):
                        continue

                    text = msg["text"]
                    ts = msg["ts"]

                    # Get sender info
                    user_id = msg.get("user", "")
                    sender_name = user_id
                    slack_handle = f"@{user_id}"
                    try:
                        user_info = client.users_info(user=user_id)
                        profile = user_info["user"]
                        sender_name = profile.get("real_name") or profile.get("display_name") or user_id
                        slack_handle = f"@{profile.get('name', user_id)}"
                    except Exception:
                        pass

                    # Convert Slack ts to ISO datetime
                    try:
                        received_at = datetime.datetime.fromtimestamp(
                            float(ts), tz=datetime.timezone.utc
                        ).isoformat()
                    except Exception:
                        received_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

                    message_id = f"slack-{channel_id}-{ts}"

                    ok = await ingest_message(
                        source_channel="slack",
                        source_message_id=message_id,
                        received_at=received_at,
                        sender_name=sender_name,
                        sender_contact=slack_handle,
                        raw_message=text,
                    )

                    if ok:
                        new_latest_ts = ts
                        ingested += 1

                channels[i]["latest_ts"] = new_latest_ts
                channels[i]["last_polled_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                channels[i]["messages_fetched"] = channels[i].get("messages_fetched", 0) + ingested
                channels[i]["is_connected"] = True
                channels[i]["error"] = None

                if ingested:
                    print(f"[Slack] Ingested {ingested} message(s) from {ch.get('channel_name', channel_id)}")

            except SlackApiError as e:
                channels[i]["is_connected"] = False
                channels[i]["error"] = f"Slack API error: {e.response['error']}"
                print(f"[Slack] API error on {channel_id}: {e.response['error']}")
            except Exception as e:
                channels[i]["is_connected"] = False
                channels[i]["error"] = str(e)
                print(f"[Slack] Error on {channel_id}: {e}")

        slack_cfg["channels"] = channels
        config["slack"] = slack_cfg
        sources_config.save_config(config)
        await asyncio.sleep(POLL_INTERVAL)
