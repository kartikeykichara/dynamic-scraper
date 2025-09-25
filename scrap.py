
import requests
import json
import os
from datetime import datetime, timezone, date, timedelta

SAVE_DIR = "matches_json"
MARKET_DIR = os.path.join(SAVE_DIR, "markets")
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(MARKET_DIR, exist_ok=True)

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.wickspin24.live",
    "referer": "https://www.wickspin24.live/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
}

def cleanup_old_files():
    today = date.today()
    for folder in [SAVE_DIR, MARKET_DIR]:
        for filename in os.listdir(folder):
            if filename.endswith(".json"):
                path = os.path.join(folder, filename)
                try:
                    if datetime.fromtimestamp(os.path.getmtime(path)).date() < today:
                        os.remove(path)
                        print(f"🗑 Deleted old file: {filename}")
                except Exception as e:
                    print(f"⚠️ Error deleting {filename}: {e}")

def fetch_all_matches():
    url = "https://apiplayer.wickspin24.live/exchange/member/playerService/queryEvents"
    payload = {"type":1,"eventType":4,"competitionTs":-1,"eventTs":-1,"marketTs":-1,"selectionTs":-1}
    try:
        resp = requests.post(url, data=payload, headers=HEADERS)
        resp.raise_for_status()
        return resp.json().get("events", [])
    except Exception as e:
        print(f"❌ Failed to fetch events: {e}")
        return []

def save_json(data, folder, filename):
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return path

def get_match_by_id(match_id):
    matches = fetch_all_matches()
    for m in matches:
        if str(m.get("eventId")) == str(match_id):
            print(json.dumps(m, indent=4, ensure_ascii=False))
            return m
    print(f"❌ Match ID {match_id} not found.")
    return None

def is_match_today_or_tomorrow(match):
    try:
        ts = match.get("openDateTime")
        if not ts: return False
        match_date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
        today, tomorrow = date.today(), date.today() + timedelta(days=1)
        return match_date in (today, tomorrow)
    except Exception as e:
        print(f"⚠️ Date parsing error: {e}")
        return False

def main():
    cleanup_old_files()
    matches = fetch_all_matches()
    if not matches:
        print("No matches found.")
        return

    for m in matches:
        if not is_match_today_or_tomorrow(m) or m.get("isInPlay") != 1:
            continue

        event_id = m.get("eventId")
        match_file = f"match_{event_id}.json"
        save_json(m, SAVE_DIR, match_file)
        print(f"✅ Saved live match {event_id} -> {SAVE_DIR}/{match_file}")

        market = m.get("market")
        if market:
            market_id = market.get("marketId", f"unknown_{event_id}")
            market_file = f"market_{market_id}.json"
            save_json(market, MARKET_DIR, market_file)
            print(f"   🔹 Saved market {market_id} -> {MARKET_DIR}/{market_file}")

if __name__ == "__main__":
    main()
    match_id = input("\n👉 Enter Match ID to see details: ")
    get_match_by_id(match_id)
