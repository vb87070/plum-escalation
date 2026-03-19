"""
Quick data loader — reads all 3 mock CSVs and POSTs each row to the webhook.
Run from the escalation-system folder:
    python load_mock_data.py
"""
import csv
import json
import urllib.request
import urllib.error
import time
import os

API_URL = "http://localhost:8000/webhook/ingest"
MOCK_DIR = os.path.join(os.path.dirname(__file__), "mock_data")

CSV_FILES = [
    "mock_gmail.csv",
    "mock_slack.csv",
    "mock_whatsapp.csv",
]

def post_row(row: dict) -> dict:
    payload = json.dumps(row).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def load_csv(filename: str):
    filepath = os.path.join(MOCK_DIR, filename)
    channel = filename.replace("mock_", "").replace(".csv", "")
    print(f"\n📂  Loading {filename} ...")

    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for i, row in enumerate(rows, 1):
        try:
            result = post_row(row)
            urgency     = result.get("urgency", "?")
            score       = result.get("priority_score", "?")
            is_esc      = result.get("is_escalation", 1)
            account     = result.get("account_name", "Unknown")
            flag        = "✅" if is_esc else "🔕 (non-escalation)"
            print(f"  {flag}  Row {i}/{len(rows)} | [{urgency}] Score={score} | {account}")
            time.sleep(0.6)   # small delay between Claude calls
        except urllib.error.HTTPError as e:
            print(f"  ❌  Row {i} failed: HTTP {e.code} — {e.read().decode()}")
        except Exception as e:
            print(f"  ❌  Row {i} failed: {e}")

if __name__ == "__main__":
    print("=" * 55)
    print("  Plum Escalation — Mock Data Loader")
    print("=" * 55)

    # Quick health check
    try:
        with urllib.request.urlopen("http://localhost:8000/", timeout=5) as r:
            print("✅  Server is reachable at localhost:8000")
    except Exception:
        print("❌  Server not reachable. Start it first:")
        print("    python -m uvicorn main:app --reload")
        exit(1)

    for csv_file in CSV_FILES:
        load_csv(csv_file)

    print("\n" + "=" * 55)
    print("  ✅  All mock data loaded!")
    print("  👉  Open dashboard/index.html in your browser")
    print("=" * 55)
