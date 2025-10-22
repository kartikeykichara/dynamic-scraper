import os, re, json, time, requests
from datetime import datetime, date

# -------------------- Directories --------------------
SAVE_DIR, MARKET_DIR = "matches_json", "matches_json/markets"
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(MARKET_DIR, exist_ok=True)

# -------------------- Constants --------------------
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.wickspin24.live",
    "referer": "https://www.wickspin24.live/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

SPORT_MAPPING = {
    "cricket": {"sports_api_id": "4", "sports_category_name": "cricket"},
    "tennis": {"sports_api_id": "2", "sports_category_name": "tennis"},
    "soccer": {"sports_api_id": "3", "sports_category_name": "soccer"}
}
SPORT_TYPE_PARAM = {"cricket": 1, "tennis": 2, "soccer": 3}


def detect_sport(tournament_name, match_title):
    name = f"{tournament_name} {match_title}".lower()

    # Explicit cricket tournaments
    cricket_tournaments = [
        "one day cup", "ipl", "bbl", "psl", "ranji", "irani",
        "vijay hazare", "syed mushtaq", "t20", "odi", "test"
    ]
    
    # Cricket keywords
    cricket_kw = [
        "cricket","men","women","team","bulls","tigers","titans",
        "blues","southern","northern","western","eastern",
        "victoria","tasmania","queensland","new south wales",
        "india","pakistan","australia","england","south africa",
        "sri lanka","bangladesh","west indies","super 60"
    ]

    # Soccer keywords + tournaments
    soccer_kw = ["soccer","football","liga","premier","uefa","bundesliga",
                 "serie a","la liga","mls","j league","afc asian cup"]

    # Tennis keywords
    tennis_kw = ["challenger","atp","wta","open","slam","wimbledon",
                 "us open","roland garros","australian open","tennis"]

    # 1️⃣ Tournament-based cricket detection
    if any(t in name for t in cricket_tournaments):
        return "cricket"

    # 2️⃣ Soccer detection (before generic cricket keywords)
    if any(k in name for k in soccer_kw):
        return "soccer"

    # 3️⃣ Generic cricket keyword detection
    if any(k in name for k in cricket_kw):
        return "cricket"

    # 4️⃣ Tennis detection
    if any(k in name for k in tennis_kw):
        return "tennis"

    # 5️⃣ Short-name tennis pattern
    if " v " in match_title.lower() or "/" in match_title:
        parts = [p.strip() for p in re.split(r" v ", match_title, flags=re.I)]
        if len(parts) == 2 and all(len(p.split()) <= 3 for p in parts):
            if not re.search(r"women|men|team|cricket|t20|odi|ipl|psl|bbl|ranji", match_title, re.I):
                return "tennis"

    return "unknown"


# -------------------- Helpers --------------------
def fetch_json(url, payload):
    try:
        r = requests.post(url, data=payload, headers=HEADERS, timeout=10)
        return r.json() if r.ok else {}
    except Exception as e:
        print(f"Fetch error: {e}")
        return {}

def save_json(data, folder, filename):
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return path

def cleanup_old_files():
    today = date.today()
    for folder in [SAVE_DIR, MARKET_DIR]:
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            if f.endswith(".json") and datetime.fromtimestamp(os.path.getmtime(p)).date() < today:
                os.remove(p)

def print_live_odds(match_json):
    print(f"\n {match_json['match_title']} ({match_json['sports_category_name']})")
    for r in match_json.get("market", {}).get("runners", []):
        price = r['lastPriceTraded'] or (r['back'][0]['price'] if r['back'] else r['lay'][0]['price'] if r['lay'] else 0)
        print(f"     • {r['name']}: {price}")

# -------------------- Fetch Matches --------------------
def fetch_matches_for_sport(sport):
    res = fetch_json("https://apiplayer.wickspin24.live/exchange/member/playerService/queryEvents", {
        "type": SPORT_TYPE_PARAM[sport],
        "eventType": -1, "competitionTs": -1, "eventTs": -1, "marketTs": -1, "selectionTs": -1
    })
    events = res.get("events", [])
    print(f"\n {sport.upper()}: {len(events)} matches fetched.")
    return events

# -------------------- Transformations --------------------
def build_runner(s):
    back = [{"price": b.get("price",0), "size": b.get("size",100), "line": None} for b in s.get("availableToBack",[])]
    lay  = [{"price": l.get("price",0), "size": l.get("size",100), "line": None} for l in s.get("availableToLay",[])]
    return {
        "id": s.get("selectionId"), "name": s.get("runnerName"),
        "back": back, "lay": lay,
        "lastPriceTraded": s.get("lastPriceTraded",0),
        "totalMatched": s.get("totalMatched",0),
        "status": "ACTIVE" if s.get("status",1)==1 else "SUSPENDED"
    }

def transform_to_matches_json(m):
    sport = detect_sport(m.get("competitionName",""), m.get("eventName",""))
    if sport not in SPORT_MAPPING:
        print(f" Unknown sport detected for {m.get('eventName','')} — skipping")
        return None
    sm = SPORT_MAPPING[sport]
    markets = m.get("market", [])
    if isinstance(markets, dict): markets = [markets]
    elif isinstance(markets, str): markets = []
    market = markets[0] if markets else {}

    return {
        "match_api_id": str(m.get("eventId")),
        "match_title": m.get("eventName",""),
        "sports_api_id": sm["sports_api_id"],
        "sports_category_name": sm["sports_category_name"],
        "tournament_api_id": str(m.get("competitionId","")),
        "tournament_name": m.get("competitionName",""),
        "start_time": m.get("openDate",""),
        "in_play": m.get("isInPlay")==1,
        "bet_locked": False,
        "market": {
            "op": "Betfair",
            "market_api_id": str(market.get("marketId","")),
            "market_title": market.get("marketName",""),
            "totalMatched": market.get("totalMatched",0),
            "is_locked": False, "visible": True,
            "runners": [build_runner(s) for s in market.get("selections",[])]
        }
    }

def transform_to_market_json(m):
    sport = detect_sport(m.get("competitionName",""), m.get("eventName",""))
    sm = SPORT_MAPPING.get(sport, {"sports_api_id":"","sports_category_name":""})
    markets = m.get("market", [])
    if isinstance(markets, dict): markets = [markets]
    elif isinstance(markets, str): markets = []
    return {
        "sports_categories_id": "6842877d462c78ba096a6fa5",
        "sports_api_id": sm["sports_api_id"],
        "sports_category_name": sm["sports_category_name"],
        "tournament_id": f"{m.get('competitionId')}_UUID",
        "tournament_api_id": str(m.get("competitionId","")),
        "tournament_name": m.get("competitionName",""),
        "match_id": f"{m.get('eventId')}_UUID",
        "match_api_id": str(m.get("eventId")),
        "match_name": m.get("eventName",""),
        "start_time": m.get("openDate",""),
        "end_time": None, "status": True,
        "markets": [{
            "op": "", "market_api_id": str(x.get("marketId","")),
            "market_title": x.get("marketName",""),
            "totalMatched": x.get("totalMatched",0),
            "runners": [build_runner(s) for s in x.get("selections",[])],
            "is_locked": False, "visible": True
        } for x in markets]
    }

# -------------------- Main --------------------
def main():
    cleanup_old_files()
    tournaments, all_matches = {}, []

    for s in SPORT_MAPPING:
        all_matches += fetch_matches_for_sport(s)

    for m in all_matches:
        if m.get("isInPlay") != 1: continue
        match_json, market_json = transform_to_matches_json(m), transform_to_market_json(m)
        if not (match_json and market_json): continue

        save_json(match_json, SAVE_DIR, f"match_{m['eventId']}.json")
        print_live_odds(match_json)
        save_json(market_json, MARKET_DIR, f"market_{m['eventId']}.json")

        tid = str(m.get("competitionId",0))
        sport = detect_sport(m.get("competitionName",""), m.get("eventName",""))
        sm = SPORT_MAPPING.get(sport,{})
        tournaments.setdefault(tid,{
            "tournament_api_id": tid,
            "tournament_name": m.get("competitionName",""),
            "sports_categories_id": "6842877d462c78ba096a6fa5",
            "sports_api_id": sm.get("sports_api_id",""),
            "sports_category_name": sm.get("sports_category_name",""),
            "sport_name": sport,
            "matchList": []
        })["matchList"].append(match_json)

    for tid, data in tournaments.items():
        save_json(data, SAVE_DIR, f"tournament_{tid}.json")
        print(f"🏆 Saved tournament {tid}")

# -------------------- Run --------------------
if __name__ == "__main__":
    while True:
        print(f"\n==============================\n⏰ Fetching LIVE data @ {datetime.now():%H:%M:%S}\n==============================")
        main()
        print("\n⏳ Waiting 60 seconds before next fetch...\n")
        time.sleep(60)
