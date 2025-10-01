import requests, json, os
from datetime import datetime, timezone, date, timedelta

SAVE_DIR, MARKET_DIR = "matches_json", "matches_json/markets"
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(MARKET_DIR, exist_ok=True)

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.wickspin24.live",
    "referer": "https://www.wickspin24.live/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def cleanup_old_files():
    today = date.today()
    for folder in [SAVE_DIR, MARKET_DIR]:
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if f.endswith(".json") and datetime.fromtimestamp(os.path.getmtime(path)).date() < today:
                os.remove(path); print(f"🗑 Deleted old file: {f}")

def fetch_json(url, payload):
    try:
        return requests.post(url, data=payload, headers=HEADERS).json()
    except Exception as e:
        print(f"❌ Request failed: {e}"); return {}

def fetch_all_matches():
    return fetch_json("https://apiplayer.wickspin24.live/exchange/member/playerService/queryEvents",
                      {"type":1,"eventType":-1,"competitionTs":-1,"eventTs":-1,"marketTs":-1,"selectionTs":-1}).get("events", [])

def save_json(data, folder, filename):
    path = os.path.join(folder, filename)
    json.dump(data, open(path, "w", encoding="utf-8"), indent=4, ensure_ascii=False)
    return path

def get_match_by_id(match_id):
    for m in fetch_all_matches():
        if str(m.get("eventId")) == str(match_id):
            print(json.dumps(m, indent=4, ensure_ascii=False)); return m
    print(f"❌ Match ID {match_id} not found."); return None

def is_match_today_or_tomorrow(match):
    ts = match.get("openDateTime")
    if not ts: return False
    match_date = datetime.fromtimestamp(ts/1000, tz=timezone.utc).date()
    return match_date in {date.today(), date.today()+timedelta(days=1)}

def transform_to_matches_json(api_match):
    market = api_match.get("market", {})
    runners = [{
        "id": s.get("selectionId"),
        "name": s.get("runnerName"),
        "back": [{"price": b["price"], "size": b["size"], "line": None} for b in s.get("availableToBack", [])],
        "lay": [{"price": l["price"], "size": l["size"], "line": None} for l in s.get("availableToLay", [])],
        "lastPriceTraded": (s.get("availableToBack") or [{}])[0].get("price", 0),
        "totalMatched": sum(b.get("size",0) for b in s.get("availableToBack", [])),
        "status": "ACTIVE" if s.get("status",1)==1 else "SUSPENDED"
    } for s in market.get("selections", [])]

    return {
        "match_api_id": str(api_match.get("eventId")),
        "match_title": api_match.get("eventName",""),
        "sports_api_id": "2",
        "sports_category_name": "cricket",
        "tournament_api_id": str(api_match.get("competitionId",0)),
        "tournament_name": api_match.get("competitionName",""),
        "start_time": (datetime.strptime(market["marketTime"], "%Y-%m-%d %H:%M").isoformat()+"Z") if market.get("marketTime") else None,
        "in_play": bool(market.get("inPlay",0)),
        "bet_locked": True,
        "market": {
            "op": "Wickspin",
            "market_api_id": market.get("marketId",""),
            "market_title": market.get("marketName",""),
            "totalMatched": market.get("totalMatched",0),
            "is_locked": False,
            "visible": True,
            "runners": runners
        }
    }

def main():
    cleanup_old_files()
    matches, tournaments = fetch_all_matches(), {}

    for m in matches:
        if not (is_match_today_or_tomorrow(m) and m.get("isInPlay") == 1): continue

        match_json = transform_to_matches_json(m)
        save_json(match_json, SAVE_DIR, f"match_{m['eventId']}.json")
        print(f"✅ Saved live match {m['eventId']}")

        if m.get("market"):
            save_json(m["market"], MARKET_DIR, f"market_{m['market']['marketId']}.json")
            print(f"   🔹 Saved market {m['market']['marketId']}")

        tid = str(m.get("competitionId",0))
        tournaments.setdefault(tid,{
            "tournament_api_id": tid,
            "tournament_name": m.get("competitionName",""),
            "sports_categories_id": "6842877d462c78ba096a6fa5",
            "sports_api_id": "4",
            "sports_category_name": "cricket",
            "matchList": []
        })["matchList"].append(match_json)

    for tid, data in tournaments.items():
        save_json(data, SAVE_DIR, f"tournament_{tid}.json")
        print(f"🏆 Saved tournament {tid}")

if __name__ == "__main__":
    main()
    get_match_by_id(input("\n👉 Enter Match ID to see details: "))
