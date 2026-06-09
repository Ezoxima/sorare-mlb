"""
explore_missions.py — probe API Sorare missions avec JWT
Usage : python explore_missions.py
"""
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".." / ".env")

SORARE_API = "https://api.sorare.com/graphql"
JWT        = os.getenv("SORARE_JWT", "")

HEADERS = {
    "Content-Type":  "application/json",
    "Authorization": f"Bearer {JWT}",
    "JWT-AUD":       "Ezox_api",
}


def _post(query: str) -> dict:
    resp = requests.post(SORARE_API, json={"query": query}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _section(title: str, query: str):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")
    try:
        data = _post(query)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"  ERREUR : {e}")


PROBES = {
    "currentUser.missions":               "{ currentUser { missions { nodes { id __typename } } } }",
    "currentUser.so5Missions":            "{ currentUser { so5Missions { nodes { id __typename } } } }",
    "currentUser.ongoingMissions":        "{ currentUser { ongoingMissions { id __typename } } }",
    "currentUser.missionContributions":   "{ currentUser { missionContributions { id __typename } } }",
    "currentUser.quests":                 "{ currentUser { quests { id __typename } } }",
    "currentUser.challenges":             "{ currentUser { challenges { id __typename } } }",
    "so5.missions":                       "{ so5 { missions { nodes { id __typename } } } }",
    "so5.currentUserMissions":            "{ so5 { currentUserMissions { id __typename } } }",
    "so5.missionSeason":                  "{ so5 { missionSeason { id missions { id __typename } } } }",
    "so5.featuredLeaderboardContests":    "{ so5 { featuredLeaderboardContests { id __typename } } }",
    "so5.leaderboardContests":            "{ so5 { leaderboardContests { nodes { id __typename } } } }",
}

for label, query in PROBES.items():
    print(f"\n── {label}")
    try:
        data = _post(query)
        if "errors" in data:
            print(f"   ERR: {data['errors'][0]['message']}")
        else:
            print(f"   OK : {json.dumps(data['data'], ensure_ascii=False)[:300]}")
    except Exception as e:
        print(f"   EXC: {e}")
