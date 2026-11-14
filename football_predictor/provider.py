
import requests
from datetime import datetime, timedelta, timezone


class APIFootballProvider:

    def __init__(self, api_key, base_url):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-Auth-Token": api_key
        }

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        response = requests.get(
            url,
            headers=self.headers,
            params=params or {},
            timeout=30
        )

        if response.status_code == 400:
            raise RuntimeError(
                f"Errore 400 football-data.org: {response.text}"
            )

        if response.status_code == 401:
            raise RuntimeError(
                "Autenticazione API non riuscita. "
                "Controlla FOOTBALL_DATA_TOKEN."
            )

        if response.status_code == 403:
            raise RuntimeError(
                "Competizione o dati non inclusi nel piano API."
            )

        if response.status_code == 429:
            raise RuntimeError(
                "Limite richieste API raggiunto. Attendi prima di riprovare."
            )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise RuntimeError("Risposta API non valida.")

        return data

    def _normalize_match(self, item):
        home = item.get("homeTeam") or {}
        away = item.get("awayTeam") or {}
        competition = item.get("competition") or {}
        season = item.get("season") or {}
        score = item.get("score") or {}
        full_time = score.get("fullTime") or {}
        status = item.get("status")

        status_map = {
            "FINISHED": "FT",
            "IN_PLAY": "LIVE",
            "PAUSED": "HT",
            "SCHEDULED": "NS",
            "TIMED": "NS",
            "POSTPONED": "PST",
            "CANCELLED": "CANC",
            "SUSPENDED": "SUSP",
            "AWARDED": "FT"
        }

        season_start = season.get("startDate")

        return {
            "fixture_id": item.get("id"),
            "date": item.get("utcDate"),
            "league": competition.get("name"),
            "league_id": competition.get("code"),
            "season": (
                int(season_start[:4])
                if season_start else None
            ),
            "country": (item.get("area") or {}).get("name"),
            "home": home.get("name"),
            "away": away.get("name"),
            "home_id": home.get("id"),
            "away_id": away.get("id"),
            "status": status_map.get(status, status),

            "fixture": {
                "id": item.get("id"),
                "date": item.get("utcDate"),
                "status": {
                    "short": status_map.get(status, status)
                }
            },

            "teams": {
                "home": {
                    "id": home.get("id"),
                    "name": home.get("name")
                },
                "away": {
                    "id": away.get("id"),
                    "name": away.get("name")
                }
            },

            "goals": {
                "home": full_time.get("home"),
                "away": full_time.get("away")
            }
        }

    def get_next_fixtures(self, count=50):
        today = datetime.now(timezone.utc).date()
        end_date = today + timedelta(days=9)

        data = self._get(
            "matches",
            {
                "dateFrom": today.isoformat(),
                "dateTo": end_date.isoformat()
            }
        )

        fixtures = [
            self._normalize_match(item)
            for item in data.get("matches", [])
        ]

        fixtures.sort(
            key=lambda item: item["date"] or ""
        )

        return fixtures[:count]

    def _get_team_matches(
        self,
        team_id,
        season,
        league_id=None,
        cutoff=None
    ):
        params = {
            "season": season,
            "limit": 100
        }

        if league_id:
            params["competitions"] = league_id

        if cutoff:
            cutoff_date = datetime.fromisoformat(
                cutoff
            ).date()

            start_date = cutoff_date - timedelta(days=364)

            params["dateFrom"] = start_date.isoformat()
            params["dateTo"] = cutoff_date.isoformat()

        data = self._get(
            f"teams/{team_id}/matches",
            params
        )

        matches = [
            self._normalize_match(item)
            for item in data.get("matches", [])
        ]

        matches.sort(
            key=lambda item: item["date"] or ""
        )

        return matches

    def get_team_season_stats(
        self,
        team_id,
        league_id,
        season,
        cutoff=None
    ):
        matches = self._get_team_matches(
            team_id,
            season,
            league_id,
            cutoff
        )

        stats = {
            "goals": {
                "for": {"average": {}},
                "against": {"average": {}}
            }
        }

        venues = {
            "home": [],
            "away": [],
            "total": []
        }

        for match in matches:
            if match["status"] not in ("FT", "AET", "PEN"):
                continue

            goals = match["goals"]
            gh = goals["home"]
            ga = goals["away"]

            if gh is None or ga is None:
                continue

            if match["home_id"] == team_id:
                venues["home"].append((gh, ga))
                venues["total"].append((gh, ga))
            else:
                venues["away"].append((ga, gh))
                venues["total"].append((ga, gh))

        for venue, results in venues.items():
            if not results:
                stats["goals"]["for"]["average"][venue] = None
                stats["goals"]["against"]["average"][venue] = None
                continue

            stats["goals"]["for"]["average"][venue] = round(
                sum(result[0] for result in results) / len(results),
                3
            )

            stats["goals"]["against"]["average"][venue] = round(
                sum(result[1] for result in results) / len(results),
                3
            )

        return stats

    def get_last_fixtures(
        self,
        team_id,
        count=10,
        cutoff=None,
        season=None,
        league_id=None
    ):
        if season is None:
            raise ValueError(
                "La stagione è necessaria per recuperare la forma recente."
            )

        matches = self._get_team_matches(
            team_id,
            season,
            league_id,
            cutoff
        )

        completed = [
            match
            for match in matches
            if match["status"] in ("FT", "AET", "PEN")
        ]

        return completed[-count:]
