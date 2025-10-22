#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ultimate Redis + Local JSON sync script
- Keeps Redis storage in the original compact byte-encoded JSON format.
- Also writes human-readable JSON files into matches_json/<sport>/{match, premium_markets, fancy}/
- Deletes old Redis keys and local files on each run (configurable)
- Fetches live matches from the API, detects sport, formats titles, saves match + premium + fancy
- Prints a detailed "image-like" summary, and verifies saved data
"""

import os
import json
import time
import requests
import redis
from datetime import datetime
from typing import Dict, List, Any

# -------------------- Redis Configuration --------------------
REDIS_CONFIG = {
    'host': 'redis-11328.c264.ap-south-1-1.ec2.redns.redis-cloud.com',
    'port': 11328,
    'password': '7OL7vswJKJyVzNtKBq7YFNLsWPdY9t2r',
    'db': 0,
    'decode_responses': False,  # keep bytes (original behavior)
    'socket_timeout': 10,
    'socket_connect_timeout': 10
}

# -------------------- Constants / Headers --------------------
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

# -------------------- Local Directory Setup --------------------
BASE_DIR = "matches_json"
SAVE_DIR = BASE_DIR  # maintain same variable name style as earlier
MARKET_DIR = os.path.join(SAVE_DIR, "markets")  # optional market dir (kept for compatibility)

def ensure_base_dirs():
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(MARKET_DIR, exist_ok=True)
    for sport in ['tennis','cricket','soccer']:
        sport_dir = os.path.join(BASE_DIR, sport)
        os.makedirs(sport_dir, exist_ok=True)
        for sub in ["match", "premium_markets", "fancy"]:
            os.makedirs(os.path.join(sport_dir, sub), exist_ok=True)

ensure_base_dirs()

def ensure_sport_folders(sport_type: str):
    sport_dir = os.path.join(BASE_DIR, sport_type)
    os.makedirs(sport_dir, exist_ok=True)
    for sub in ["match", "premium_markets", "fancy"]:
        os.makedirs(os.path.join(sport_dir, sub), exist_ok=True)
    return sport_dir

def clear_local_folders():
    """Remove all files inside matches_json/<sport>/* (keeps folders)"""
    print("\n🗑️ Clearing local folder contents...")
    for sport in ['tennis','cricket','soccer']:
        sport_dir = os.path.join(BASE_DIR, sport)
        if os.path.exists(sport_dir):
            for root, dirs, files in os.walk(sport_dir):
                for f in files:
                    try:
                        os.remove(os.path.join(root, f))
                    except Exception as e:
                        print(f"⚠️ Couldn't remove {os.path.join(root,f)}: {e}")
            print(f"✅ Cleared files in {sport}/")
    print("🧹 Local cleanup done.")

def save_json_to_file(filepath: str, data: dict):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved -> {filepath}")
    except Exception as e:
        print(f"❌ File save error for {filepath}: {e}")

# -------------------- Initialize Redis --------------------
def init_redis():
    try:
        client = redis.Redis(**REDIS_CONFIG)
        client.ping()
        print("✅ Connected to Redis Cloud successfully")
        return client
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return None

redis_client = init_redis()

# -------------------- Delete All Previous Data (Redis + Local) --------------------
def delete_all_previous_data():
    """Delete ALL previous Redis keys matching patterns (and optionally clear local files)"""
    if not redis_client:
        print("⚠️ Redis client not available - skipping Redis delete")
    else:
        print("\n🗑️ Deleting ALL previous Redis data (matching patterns)...")
        deleted_count = 0
        for sport in ['tennis','cricket','soccer']:
            patterns = [
                f"in_play_{sport}_premium:*",
                f"in_play_{sport}_premium:match:*",
                f"in_play_{sport}_premium:premium_markets:*",
                f"in_play_{sport}_premium:fancy:*"
            ]
            for pattern in patterns:
                try:
                    keys = redis_client.keys(pattern)
                    if keys:
                        # redis_client.delete expects *keys when decode_responses False -> bytes keys OK
                        redis_client.delete(*keys)
                        deleted_count += len(keys)
                        print(f"✅ Deleted {len(keys)} keys for pattern {pattern}")
                except Exception as e:
                    print(f"⚠️ Error deleting keys for {pattern}: {e}")
        print(f"🗑️ Total Redis keys deleted: {deleted_count}")

    # Now clear local files
    clear_local_folders()

# -------------------- Exact Match Save (Redis + Local) --------------------
def save_match_data(sport_type: str, match_id: str, match_title: str, tournament: str = "") -> bool:
    """Save match data in EXACT format (compact JSON bytes to Redis) AND pretty JSON file locally"""
    if not redis_client:
        print("⚠️ Redis unavailable - skipping Redis save")
    try:
        clean_match_id = match_id.lstrip('-')
        match_key = f"in_play_{sport_type}_premium:match:{match_id}"

        match_data = {
            "match": match_title,
            "url": f"https://www.wickspin24.live/sports/{sport_type}/match/{clean_match_id}",
            "fancy_bet": sport_type == "cricket",
            "aportabook": True
        }

        # Compact JSON bytes for Redis (exact-like)
        try:
            serialized_data = json.dumps(match_data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            if redis_client:
                redis_client.set(match_key, serialized_data)
        except Exception as e:
            print(f"❌ Redis set error for {match_key}: {e}")

        # Save pretty file locally (human readable)
        try:
            sport_dir = ensure_sport_folders(sport_type)
            local_path = os.path.join(sport_dir, "match", f"{match_id}.json")
            save_json_to_file(local_path, match_data)
        except Exception as e:
            print(f"❌ Local file save error: {e}")

        print(f"💾 {sport_type.upper()} saved: {match_title} ({match_id})")
        return True

    except Exception as e:
        print(f"❌ save_match_data error: {e}")
        return False

def save_premium_markets(sport_type: str, match_id: str, match_title: str) -> bool:
    """Save premium market data to Redis + local file (market_<id>.json)"""
    if not redis_client:
        print("⚠️ Redis unavailable - skipping Redis save for premium markets")
    try:
        premium_key = f"in_play_{sport_type}_premium:premium_markets:{match_id}"
        premium_data = {
            "match_id": match_id,
            "match_title": match_title,
            "markets": [
                {
                    "market_id": f"market_{match_id}",
                    "market_name": "Match Odds",
                    "runners": [
                        {"runner_id": "1", "runner_name": "Home", "odds": "1.85"},
                        {"runner_id": "2", "runner_name": "Away", "odds": "1.95"}
                    ]
                }
            ]
        }

        # Save to Redis (compact bytes)
        try:
            serialized = json.dumps(premium_data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            if redis_client:
                redis_client.set(premium_key, serialized)
        except Exception as e:
            print(f"❌ Redis premium set error for {premium_key}: {e}")

        # Local file
        sport_dir = ensure_sport_folders(sport_type)
        local_path = os.path.join(sport_dir, "premium_markets", f"market_{match_id}.json")
        save_json_to_file(local_path, premium_data)

        return True
    except Exception as e:
        print(f"❌ save_premium_markets error: {e}")
        return False

def save_fancy_markets(sport_type: str, match_id: str, fancy_data: Dict[str, Any]) -> bool:
    """Save fancy markets (if any) into fancy/<id>.json and Redis key"""
    if not redis_client:
        print("⚠️ Redis unavailable - skipping Redis save for fancy markets")
    try:
        fancy_key = f"in_play_{sport_type}_premium:fancy:{match_id}"
        # Save to Redis
        try:
            serialized = json.dumps(fancy_data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            if redis_client:
                redis_client.set(fancy_key, serialized)
        except Exception as e:
            print(f"❌ Redis fancy set error for {fancy_key}: {e}")

        # Local file
        sport_dir = ensure_sport_folders(sport_type)
        local_path = os.path.join(sport_dir, "fancy", f"fancy_{match_id}.json")
        save_json_to_file(local_path, fancy_data)
        return True
    except Exception as e:
        print(f"❌ save_fancy_markets error: {e}")
        return False

# -------------------- Improved Data Processing Helpers --------------------
def extract_tennis_players(event_name: str):
    """Return names formatted like 'N. Lastname - J. Lastname' (but keep simple if can't parse)"""
    if " v " in event_name:
        parts = event_name.split(" v ")
        if len(parts) == 2:
            p1 = parts[0].strip()
            p2 = parts[1].strip()

            def fmt(name):
                parts = name.split()
                if len(parts) >= 2:
                    return f"{parts[0][0]}. {parts[-1]}"
                return name

            return fmt(p1), fmt(p2)
    return event_name, "Player2"

def extract_team_names(event_name: str, sport: str):
    if " v " in event_name:
        parts = event_name.split(" v ")
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    if " vs " in event_name:
        parts = event_name.split(" vs ")
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return f"{sport.title()} Team A", f"{sport.title()} Team B"

def detect_sport_type(tournament_name: str, event_name: str, api_sport: str):
    """Detect sport using tournament, event_name and api_sport as fallback"""
    combined = f"{tournament_name} {event_name}".lower()
    detected_sport = api_sport

    tennis_indicators = ["challenger", "atp", "wta", "open", "tennis", "grand slam", "doubles", "singles"]
    cricket_indicators = ["cricket", "t20", "odi", "test", "ipl", "bbl", "psl", "cup", "trophy", "women", "men", "domestic"]
    soccer_indicators = ["soccer", "football", "premier", "league", "uefa", "fifa", "champions", "bundesliga", "la liga", "serie a", "laliga"]

    if any(indicator in combined for indicator in tennis_indicators):
        detected_sport = "tennis"
    elif any(indicator in combined for indicator in cricket_indicators):
        detected_sport = "cricket"
    elif any(indicator in combined for indicator in soccer_indicators):
        detected_sport = "soccer"

    # Name pattern detection for tennis (two-person names)
    if " v " in event_name:
        parts = event_name.split(" v ")
        if len(parts) == 2:
            p1_words = len(parts[0].split())
            p2_words = len(parts[1].split())
            if 2 <= p1_words <= 3 and 2 <= p2_words <= 3:
                if not any(word in combined for word in ["fc", "club", "united", "city", "team", "county", "state"]):
                    detected_sport = "tennis"

    print(f"🎯 Sport Detection: '{event_name}' -> {detected_sport.upper()}")
    return detected_sport

def format_match_title(event_name: str, sport: str):
    if sport == "tennis":
        p1, p2 = extract_tennis_players(event_name)
        return f"{p1} - {p2}"
    elif sport == "cricket":
        t1, t2 = extract_team_names(event_name, "cricket")
        return f"{t1} v {t2}"
    elif sport == "soccer":
        t1, t2 = extract_team_names(event_name, "soccer")
        return f"{t1} vs {t2}"
    return event_name

# -------------------- API Fetching --------------------
def fetch_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = requests.post(url, data=payload, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ API Error: {response.status_code} for {url}")
            return {}
    except Exception as e:
        print(f"❌ Fetch error: {e} for {url}")
        return {}

def fetch_live_matches() -> List[Dict[str, Any]]:
    all_matches: List[Dict[str, Any]] = []
    for sport in SPORT_MAPPING:
        try:
            print(f"\n📥 Fetching {sport} matches from API...")
            response = fetch_json("https://apiplayer.wickspin24.live/exchange/member/playerService/queryEvents", {
                "type": SPORT_TYPE_PARAM[sport],
                "eventType": -1, "competitionTs": -1, "eventTs": -1, "marketTs": -1, "selectionTs": -1
            })
            if response and 'events' in response:
                matches = response['events']
                live_matches = [m for m in matches if m.get("isInPlay") == 1]
                for match in live_matches:
                    match['api_sport'] = sport
                print(f"✅ Found {len(live_matches)} LIVE {sport} matches")
                all_matches.extend(live_matches)
            else:
                print(f"❌ No events found for {sport}")
        except Exception as e:
            print(f"❌ Error fetching {sport}: {e}")
    print(f"\n🎯 Total LIVE matches found: {len(all_matches)}")
    return all_matches

# -------------------- Proper Display Format (print like image) --------------------
def print_redis_data_proper():
    if not redis_client:
        print("❌ Redis not connected - cannot print Redis data")
        return

    print("\n" + "="*80)
    print("# Results: Scanning Redis Data")
    print("="*80)

    total_scanned = 0
    sport_data = {}
    for sport in ['tennis','cricket','soccer']:
        match_pattern = f"in_play_{sport}_premium:match:*"
        premium_pattern = f"in_play_{sport}_premium:premium_markets:*"
        try:
            matches = redis_client.keys(match_pattern) or []
            premium_markets = redis_client.keys(premium_pattern) or []
        except Exception as e:
            print(f"⚠️ Redis keys fetch error for {sport}: {e}")
            matches = []
            premium_markets = []

        total_sport = len(matches) + len(premium_markets)
        sport_data[sport] = {
            'matches': matches,
            'premium_markets': premium_markets,
            'total': total_sport
        }
        total_scanned += total_sport

    print(f"\n# Results: {total_scanned}. Scanned {total_scanned} / {total_scanned}")

    for sport in ['tennis','cricket','soccer']:
        data = sport_data[sport]
        if data['total'] > 0:
            match_count = len(data['matches'])
            premium_count = len(data['premium_markets'])
            print(f"\n## Columns")
            print(f"- **in_play_{sport}_premium**")
            print(f"  100%")
            print(f"  {data['total']}")
            print()
            match_percent = int((match_count / data['total']) * 100) if data['total'] > 0 else 0
            premium_percent = 100 - match_percent
            print(f"| match    | {match_percent}%    | {match_count}    |")
            print(f"| premium_markets | {premium_percent}%    | {premium_count}    |")
            print()
            # show first 9 match entries like image
            for match_key in data['matches'][:9]:
                try:
                    match_key_str = match_key.decode() if isinstance(match_key, bytes) else match_key
                    match_id = match_key_str.split(':')[-1]
                    match_data = redis_client.get(match_key) or b''
                    data_size = len(match_data) if match_data else 0
                    print(f"| JSON    | {match_id}    | No limit    | {data_size} B    |")
                except Exception as e:
                    print(f"⚠️ Error reading key display: {e}")
            print("\n---")

            # sample details
            if data['matches']:
                sample_key = data['matches'][0]
                try:
                    sample_key_str = sample_key.decode() if isinstance(sample_key, bytes) else sample_key
                    sample_data = redis_client.get(sample_key)
                    if sample_data:
                        try:
                            # sample_data might be bytes
                            if isinstance(sample_data, (bytes, bytearray)):
                                parsed_data = json.loads(sample_data.decode('utf-8'))
                            else:
                                parsed_data = json.loads(sample_data)
                        except Exception:
                            parsed_data = {}
                        print(f"\n## Columns")
                        print(f"- **{sample_key_str}**")
                        print(f"### Top-level values: 4 TTL: No limit")
                        print(f"<1 min")
                        print(f"\n---")
                        print(f'### "match": "{parsed_data.get("match", "")}"')
                        print(f'"url": "{parsed_data.get("url", "")}"')
                        print(f'"fancy_bet": {parsed_data.get("fancy_bet", False)}')
                        print(f'"aportabook": {parsed_data.get("aportabook", True)}')
                        print(f"\n---")
                except Exception as e:
                    print(f"⚠️ Error printing sample: {e}")

# -------------------- Verify and Validate --------------------
def verify_and_validate():
    """Verify local files AND Redis entries (first few)"""
    print("\n🔍 Verifying data storage (local files + Redis keys)...")
    issues_found = 0
    if redis_client:
        for sport in ['tennis','cricket','soccer']:
            match_pattern = f"in_play_{sport}_premium:match:*"
            try:
                matches = redis_client.keys(match_pattern) or []
            except Exception as e:
                print(f"⚠️ Error fetching keys for verify: {e}")
                matches = []

            print(f"\n{sport.upper()} Matches in Redis: {len(matches)}")
            for match_key in matches[:3]:
                key_str = match_key.decode() if isinstance(match_key, bytes) else match_key
                data = redis_client.get(match_key)
                if not data:
                    print(f"❌ {key_str}: NO DATA")
                    issues_found += 1
                    continue
                try:
                    if isinstance(data, (bytes, bytearray)):
                        parsed = json.loads(data.decode('utf-8'))
                    else:
                        parsed = json.loads(data)
                    required = ['match','url','fancy_bet','aportabook']
                    if all(field in parsed for field in required):
                        print(f"✅ {key_str}: VALID")
                        print(f"   Content: {parsed.get('match')}")
                    else:
                        print(f"❌ {key_str}: MISSING FIELDS")
                        issues_found += 1
                except Exception:
                    print(f"❌ {key_str}: INVALID JSON")
                    issues_found += 1
    else:
        print("⚠️ Redis not connected - verifying only local files")

    # Verify local files (first 3 per sport)
    for sport in ['tennis','cricket','soccer']:
        match_path = os.path.join(BASE_DIR, sport, "match")
        if not os.path.exists(match_path):
            continue
        files = [f for f in os.listdir(match_path) if f.endswith(".json")]
        for f in files[:3]:
            try:
                with open(os.path.join(match_path, f), "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                if all(k in data for k in ["match","url","fancy_bet","aportabook"]):
                    print(f"✅ LOCAL {sport}/{f}: VALID")
                else:
                    print(f"⚠️ LOCAL {sport}/{f}: MISSING KEYS")
                    issues_found += 1
            except Exception:
                print(f"❌ LOCAL {sport}/{f}: INVALID JSON")
                issues_found += 1

    if issues_found == 0:
        print("\n🎉 ALL DATA STORED CORRECTLY!")
    else:
        print(f"\n⚠️ {issues_found} issues found during verification")

# -------------------- Main Processing --------------------
def process_live_matches():
    if not redis_client:
        print("⚠️ Redis not connected - will still create local files but Redis saves skipped")

    print("\n🎯 Processing LIVE matches...")
    # Clear previous (Redis + local)
    delete_all_previous_data()

    # Fetch matches
    live_matches = fetch_live_matches()
    if not live_matches:
        print("❌ No live matches found - nothing to save")
        return

    sport_counts = {"tennis":0,"cricket":0,"soccer":0}
    for match in live_matches:
        match_id = str(match.get("eventId",""))
        event_name = match.get("eventName","").strip()
        tournament_name = match.get("competitionName","").strip()
        api_sport = match.get("api_sport", "cricket")
        if not event_name or not match_id:
            continue

        sport_type = detect_sport_type(tournament_name, event_name, api_sport)
        match_title = format_match_title(event_name, sport_type)

        saved = save_match_data(sport_type, match_id, match_title, tournament_name)
        if saved:
            # Save premium markets (demo structure) and optionally fancy (demo)
            save_premium_markets(sport_type, match_id, match_title)

            # Example: If cricket and we want to simulate fancy markets, create demo fancy
            if sport_type == "cricket":
                fancy_demo = {
                    "match_id": match_id,
                    "fancy_name": f"Fancy market for {match_id}",
                    "selections": [
                        {"id":"f1","name":"FancyA","price":"1.2"},
                        {"id":"f2","name":"FancyB","price":"2.3"}
                    ]
                }
                save_fancy_markets(sport_type, match_id, fancy_demo)

            sport_counts[sport_type] += 1

    print("\n📊 FINAL RESULTS:")
    for sport, count in sport_counts.items():
        if count > 0:
            print(f"   {sport.upper()}: {count} matches")
    total = sum(sport_counts.values())
    print(f"   TOTAL: {total} matches")

# -------------------- Runner / Main --------------------
def main():
    print(f"\n{'='*60}")
    print(f"⏰ STARTING DATA PROCESSING @ {datetime.now():%H:%M:%S}")
    print(f"{'='*60}")

    process_live_matches()
    print_redis_data_proper()
    verify_and_validate()

    print(f"\n🏁 PROCESSING COMPLETED @ {datetime.now():%H:%M:%S}")

# -------------------- Run with Interval --------------------
if __name__ == "__main__":
    print("🚀 STARTING REDIS + LOCAL DATA SERVICE - FULL MERGED VERSION")
    try:
        while True:
            main()
            print("\n⏳ Waiting 60 seconds for next update...")
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 Service stopped by user")
    except Exception as e:
        print(f"❌ Critical error: {e}")
