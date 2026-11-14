
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

        if response.status_code == 403:
            raise RuntimeError(
                "Competizione o dati non inclusi "
                "nel piano football-data.org."
            )

        if response.status_code == 429:
            raise RuntimeError(
                "Limite richieste API raggiunto. "
                "Attendi prima di riprovare."
            )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise RuntimeError("Risposta API non valida.")

        if "error" in data:
            raise RuntimeError(str(data["error"]))

        return data

    def _normalize_match(self, item):
        """
        Converte il formato football-data.org
        nel formato utilizzato dal modello Poisson.
        """

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
            "CANCELLED": "CANC"
        }

        return {
            "fixture_id": item.get("id"),
            "date": item.get("utcDate"),
            "league": competition.get("name"),
            "league_id": competition.get("code"),
            "season": (
                int(season["startDate"][:4])
                if season.get("startDate")
                else None
            ),
            "country": (
                (item.get("area") or {}).get("name")
            ),
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
        """
        Recupera le partite dei prossimi 14 giorni.
        """

        today = datetime.now(timezone.utc).date()
        end_date = today + timedelta(days=14)

        data = self._get(
            "matches",
            {
                "dateFrom": today.isoformat(),
                "dateTo": end_date.isoformat()
            }
        )

        matches = data.get("matches", [])

        fixtures = [
            self._normalize_match(item)
            for item in matches
        ]

        fixtures.sort(
            key=lambda x: x["date"] or ""
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
            params["dateTo"] = cutoff

        data = self._get(
            f"teams/{team_id}/matches",
            params
        )

        matches = data.get("matches", [])

        normalized = [
            self._normalize_match(item)
            for item in matches
        ]

        normalized.sort(
            key=lambda x: x["date"] or ""
        )

        return normalized

    def get_team_season_stats(
        self,
        team_id,
        league_id,
        season,
        cutoff=None
    ):
        """
        Ricostruisce le statistiche stagionali
        dai risultati effettivi delle partite.
        """

        matches = self._get_team_matches(
            team_id,
            season,
            league_id,
            cutoff
        )

        stats = {
            "goals": {
                "for": {
                    "average": {}
                },
                "against": {
                    "average": {}
                }
            }
        }

        venues = {
            "home": [],
            "away": [],
            "total": []
        }

        for match in matches:

            if match["status"] != "FT":
                continue

            goals = match["goals"]
            home_id = match["home_id"]

            gh = goals["home"]
            ga = goals["away"]

            if gh is None or ga is None:
                continue

            if home_id == team_id:
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

            goals_for = sum(x[0] for x in results)
            goals_against = sum(x[1] for x in results)

            stats["goals"]["for"]["average"][venue] = round(
                goals_for / len(results), 3
            )

            stats["goals"]["against"]["average"][venue] = round(
                goals_against / len(results), 3
            )

        return stats

    def get_last_fixtures(
        self,
        team_id,
        count=10,
        cutoff=None
    ):
        """
        Recupera le ultime partite della squadra
        nella stagione e competizione corrente.
        """

        # La stagione e la competizione vengono
        # impostate dal profilo caricato in app.py.
        # Vengono aggiunte tramite i parametri
        # ricevuti dal metodo di caricamento.

        matches = self._get_team_matches(
            team_id,
            datetime.now(timezone.utc).year,
            None,
            cutoff
        )

        completed = [
            match for match in matches
            if match["status"] == "FT"
        ]

        return completed[-count:]
