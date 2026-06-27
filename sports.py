import urllib.request
import json

API_BASE = "https://www.thesportsdb.com/api/v1/json/123"

SPORT_LEAGUES = {
    "football": {
        "name": "⚽ football",
        "icon": "⚽",
        "leagues": {
            "4328": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
            "4335": "🇪🇸 La Liga",
            "4331": "🇩🇪 Bundesliga",
            "4332": "🇮🇹 Serie A",
            "4334": "🇫🇷 Ligue 1",
            "4480": "⭐ Champions League",
            "4399": "🇺🇸 MLS",
        }
    },
    "basketball": {
        "name": "🏀 basketball",
        "icon": "🏀",
        "leagues": {
            "4387": "🇺🇸 NBA",
            "4966": "🌍 EuroLeague",
        }
    },
    "boxing": {
        "name": "🥊 box",
        "icon": "🥊",
        "leagues": {
            "4445": "🥊 Boxing",
        }
    },
    "mma": {
        "name": "🥋 MMA / UFC",
        "icon": "🥋",
        "leagues": {
            "4443": "🥋 UFC",
        }
    },
    "tennis": {
        "name": "🎾 tennis",
        "icon": "🎾",
        "leagues": {
            "4464": "🎾 ATP Tour",
            "4481": "🎾 WTA Tour",
        }
    },
    "rugby": {
        "name": "🏉 rugby",
        "icon": "🏉",
        "leagues": {
            "4574": "Six Nations",
            "4698": "Rugby World Cup",
        }
    },
    "hockey": {
        "name": "🏒 hockey",
        "icon": "🏒",
        "leagues": {
            "4380": "🇺🇸 NHL",
        }
    },
    "baseball": {
        "name": "⚾ baseball",
        "icon": "⚾",
        "leagues": {
            "4424": "🇺🇸 MLB",
        }
    },
}


def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"Sports API error: {e}")
        return None


def get_events_for_league(league_id, mode="next"):
    endpoint = "eventsnextleague.php" if mode == "next" else "eventspastleague.php"
    url = f"{API_BASE}/{endpoint}?id={league_id}"
    data = fetch_json(url)
    if not data or not data.get("events"):
        return []
    return data["events"]


def get_sport_events(sport_key, mode="next"):
    if sport_key not in SPORT_LEAGUES:
        return []

    all_events = []
    for league_id, league_name in SPORT_LEAGUES[sport_key]["leagues"].items():
        events = get_events_for_league(league_id, mode)
        for e in events[:8]:
            all_events.append({
                "id": e.get("idEvent"),
                "league": league_name,
                "league_id": league_id,
                "home": e.get("strHomeTeam", ""),
                "away": e.get("strAwayTeam", ""),
                "date": e.get("dateEvent", ""),
                "time": e.get("strTime", ""),
                "venue": e.get("strVenue", ""),
                "home_score": e.get("intHomeScore"),
                "away_score": e.get("intAwayScore"),
                "home_logo": e.get("strHomeTeamBadge", ""),
                "away_logo": e.get("strAwayTeamBadge", ""),
                "status": e.get("strStatus", ""),
                "thumb": e.get("strThumb", ""),
            })

    all_events.sort(key=lambda x: x["date"] or "9999")
    return all_events
