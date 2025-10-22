

import os, json, time, requests
from datetime import datetime,date

# -------------------- Directory --------------------
SAVE_DIR = "odds"  # 🔹 Everything goes into this folder
os.makedirs(SAVE_DIR, exist_ok=True)

# -------------------- API Setup --------------------
EVENTS_URL = "https://gakvx.wickspin24.live/exchange/member/playerService/queryEvents"
API_URL = "https://gakvx.wickspin24.live/exchange/member/playerService/queryFullMarkets"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.wickspin24.live",
    "Referer": "https://www.wickspin24.live/",
    "Cookie": "JSESSIONID=YOUR_SESSION_ID"  # 🔹 Replace with your latest session
}

SELECTION_TS = int(time.time() * 1000)  # timestamp for market request
REFRESH_INTERVAL = 1

# -------------------- Helpers --------------------
def fetch_json(url, payload):
    try:
        r = requests.post(url, headers=HEADERS, data=payload, timeout=10)
        if r.status_code != 200 or not r.text.strip():
            print(f"Error fetching: {r.status_code}")
            return {}
        return r.json()
    except Exception as e:
        print(f"Request error: {e}")
        return {}

def save_json(data, filename):
    path = os.path.join(SAVE_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path

def print_market(market):
    print(f"\n🏏 {market.get('eventName', 'Match')} | {market.get('marketName')}")
    print(f" Total Matched: {market.get('totalMatched',0)}")

    for s in market.get("selections", []):
        back_data = s.get("availableToBack")
        lay_data = s.get("availableToLay")

        # Safely extract back and lay price
        if isinstance(back_data, list) and len(back_data) > 0:
            back = back_data[0].get("price", "-")
        elif isinstance(back_data, dict):
            back = back_data.get("price", "-")
        else:
            back = "-"

        if isinstance(lay_data, list) and len(lay_data) > 0:
            lay = lay_data[0].get("price", "-")
        elif isinstance(lay_data, dict):
            lay = lay_data.get("price", "-")
        else:
            lay = "-"

        print(f"{s.get('runnerName','-'):20} | Back: {back:<6} | Lay: {lay:<6}")

        
def cleanup_old_files():
    today = date.today()
    for f in os.listdir(SAVE_DIR):
        p = os.path.join(SAVE_DIR, f)
        if not f.endswith(".json"):
            continue
        if datetime.fromtimestamp(os.path.getmtime(p)).date() < today:
            os.remove(p)
            print(f"🗑️ Removed old file: {f}")


# -------------------- Fetch Live Matches --------------------
def get_live_matches():
    payload = {
        "type": "1",
        "eventType": "4",
        "competitionTs": "-1",
        "eventTs": "-1",
        "marketTs": "-1",
        "selectionTs": "-1",
        "collectEventIds": ""
    }
    data = fetch_json(EVENTS_URL, payload)
    events = [
        {
            "event_id": e["eventId"],
            "market_id": e.get("market", {}).get("marketId"),
            "name": e.get("eventName")
        }
        for e in data.get("events", [])
        if e.get("isInPlay") == 1 and e.get("market")
    ]
    print(f"✅ {len(events)} live matches fetched.")
    return events

# -------------------- Fetch Market Data --------------------
def get_market(event_id, market_id):
    payload = {
        "eventId": event_id,
        "marketId": market_id,
        "selectionTs": SELECTION_TS,
        "isGetRunnerMetadata": "false"
    }
    return fetch_json(API_URL, payload).get("market", {})

# -------------------- Main Loop --------------------
def main():
    matches = get_live_matches()
    if not matches:
        print("No live matches found.")
        return

    for match in matches:
        market = get_market(match["event_id"], match["market_id"])
        if market:
            print_market(market)
            # Save market JSON
            save_json(market, f"market_{match['event_id']}.json")
            # Optional: also save match summary if needed
            save_json({"event_id": match["event_id"], "name": match["name"]}, f"match_{match['event_id']}.json")
        else:
            print(f"No market data for {match['name']}")

# -------------------- Run --------------------
if __name__ == "__main__":
    while True:
        cleanup_old_files()  # 🧹 remove yesterday’s data first
        print(f"\n==============================\n⏰ Fetching LIVE data @ {datetime.now():%H:%M:%S}\n==============================")
        main()
        print(f"\n⏳ Waiting {REFRESH_INTERVAL} seconds before next fetch...\n")
        time.sleep(REFRESH_INTERVAL)
