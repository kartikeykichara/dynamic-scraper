

import os, json, time, requests
from datetime import datetime, date

# ------------------- Directories -------------------
SAVE_DIR = "fancy"  
os.makedirs(SAVE_DIR, exist_ok=True)

# ------------------- API Setup -------------------
EVENTS_URL = "https://gakvx.wickspin24.live/exchange/member/playerService/queryEvents"
FANCY_URL = "https://gakvx.wickspin24.live/exchange/member/playerService/queryDMFancyBetMarkets"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.wickspin24.live",
    "Referer": "https://www.wickspin24.live/",
    "x-requested-with": "XMLHttpRequest"
}

COOKIES = {
    "JSESSIONID": "YOUR_SESSION_ID_HERE",  
    "intercom-session-qmraeqj3": "",
    "load_balancer": "034e2db2-4d23-4e9e-b103-6e3b535b5ffc"
}

REFRESH_INTERVAL = 1 

# ------------------- Helpers -------------------
def fetch_json(url, payload):
    """Send POST and return JSON."""
    try:
        r = requests.post(url, headers=HEADERS, cookies=COOKIES, data=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f" Request error: {e}")
        return {}

def save_json(event_id, data):
    """Save market JSON for an event."""
    save_file = os.path.join(SAVE_DIR, f"MarketData_{event_id}.json")
    with open(save_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return save_file

def merge_markets(old_data, new_data):
    """Merge previous + new markets together."""
    old_markets = {m["apiSiteMarketId"]: m for m in old_data.get("dmFancyBetMarkets", [])}
    new_markets = new_data.get("dmFancyBetMarkets", [])

    for m in new_markets:
        market_id = m.get("apiSiteMarketId")
        if not market_id:
            continue
        if m.get("removed"):
            old_markets.pop(market_id, None)
            continue
        old_markets[market_id] = m

    merged_data = {
        "dmFancyBetMarkets": list(old_markets.values()),
        "dmFancyBetEvent": new_data.get("dmFancyBetEvent", {}),
        "version": new_data.get("version", int(time.time() * 1000))
    }
    return merged_data

def load_old_data(event_id):
    """Load previously saved JSON data if exists."""
    save_file = os.path.join(SAVE_DIR, f"MarketData_{event_id}.json")
    if os.path.exists(save_file):
        with open(save_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"dmFancyBetMarkets": [], "dmFancyBetEvent": {}, "version": 0}

def print_fancy(data):
    """Print market details in console."""
    dm_markets = data.get("dmFancyBetMarkets", [])
    if not dm_markets:
        print(" No fancy markets found.")
        return
    print(f"\n Event: {dm_markets[0].get('eventName','Unknown')} | Total Markets: {len(dm_markets)}")
    for m in dm_markets:
        print(f" {m.get('marketName','Unknown Market')} | Status: {m.get('status')} | Suspended: {m.get('suspended')}")

# ------------------- File Cleanup -------------------
def cleanup_old_files():
    """Remove old JSONs older than today."""
    today = date.today()
    for f in os.listdir(SAVE_DIR):
        p = os.path.join(SAVE_DIR, f)
        if not f.endswith(".json"):
            continue
        if datetime.fromtimestamp(os.path.getmtime(p)).date() < today:
            os.remove(p)
            

# ------------------- Fetch Live Matches -------------------
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
            "event_id": str(e["eventId"]),
            "market_ids": [e.get("market", {}).get("marketId")] if e.get("market") else [],
            "name": e.get("eventName")
        }
        for e in data.get("events", [])
        if e.get("isInPlay") == 1
    ]
    print(f"{len(events)} live events fetched.")
    return events

# ------------------- Fetch Fancy Markets -------------------
def fetch_fancy(event_id, market_ids):
    if not market_ids:
        return {"dmFancyBetMarkets": [], "dmFancyBetEvent": {}, "version": int(time.time() * 1000)}
    payload = {
        "eventId": event_id,
        "version": str(int(time.time() * 1000)),
        "oddsType": "1",
        "marketIds": ",".join(market_ids),
        "isDynamicUpdate": "0"
    }
    return fetch_json(FANCY_URL, payload)

# ------------------- Main Loop -------------------
if __name__ == "__main__":
    print("🔁 Fetching dynamic Fancy data for all live events ...")
    while True:
        try:
            cleanup_old_files()  #  remove yesterday’s data first
            events = get_live_matches()

            for event in events:
                event_id = event["event_id"]
                market_ids = event["market_ids"]
                data = fetch_fancy(event_id, market_ids)
                old_data = load_old_data(event_id)
                merged_data = merge_markets(old_data, data)
                save_json(event_id, merged_data)
                print_fancy(merged_data)
                print(f"\n✅ MarketData_{event_id}.json updated ({len(merged_data['dmFancyBetMarkets'])} markets)\n")

        except Exception as e:
            print(f" Error: {e}")
        time.sleep(REFRESH_INTERVAL)
