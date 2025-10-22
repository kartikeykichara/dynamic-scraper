import requests, json, os, time
from datetime import datetime

# ---------------- CONFIG ----------------
MATCH_ID = "34800290"   # ✅ Sirf ek match ID dal

# Folder setup (sirf match id ke naam se folder)
SAVE_DIR = MATCH_ID
MARKET_DIR = os.path.join(SAVE_DIR, "markets")

os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(MARKET_DIR, exist_ok=True)

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.wickspin24.live",
    "referer": "https://www.wickspin24.live/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ---------------- FUNCTIONS ----------------
def fetch_all_matches():
    """Fetch all matches once"""
    try:
        res = requests.post(
            "https://apiplayer.wickspin24.live/exchange/member/playerService/queryEvents",
            data={
                "type": 1, "eventType": -1,
                "competitionTs": -1, "eventTs": -1,
                "marketTs": -1, "selectionTs": -1
            },
            headers=HEADERS,
            timeout=10
        )
        if res.status_code != 200:
            print(f"❌ API returned {res.status_code}")
            return []
        return res.json().get("events", [])
    except Exception as e:
        print(f"Request failed: {e}")
        return []

def save_json(data, folder, filename):
    """Save JSON file"""
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return path

def fetch_particular_match(match_id):
    """Fetch sirf ek match ka data"""
    all_matches = fetch_all_matches()
    for m in all_matches:
        if str(m.get("eventId")) == str(match_id):
            match_path = save_json(m, SAVE_DIR, f"match_{match_id}.json")
            print(f"✅ Saved {match_path}")

            # Market data handle karna
            if "market" in m and isinstance(m["market"], dict):
                market_path = save_json(m["market"], MARKET_DIR, f"market_{m['market']['marketId']}.json")
                print(f"   🔹 Saved {market_path}")

            elif "markets" in m and isinstance(m["markets"], list):
                for mk in m["markets"]:
                    if "marketId" in mk:
                        market_path = save_json(mk, MARKET_DIR, f"market_{mk['marketId']}.json")
                        print(f"   🔹 Saved {market_path}")
            else:
                print("⚠️ No markets found in this match.")
            return
    print(f"❌ Match ID {match_id} not found in list.")

# ---------------- MAIN LOOP ----------------
if __name__ == "__main__":
    fetch_particular_match(MATCH_ID)
