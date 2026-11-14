
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


class APIFootballProvider:

    def __init__(self, api_key, base_url):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "x-apisports-key": api_key
        }

    def _get(self, endpoint, params=None):
        response = requests.get(
            f"{self.base_url}/{endpoint}",
            headers=self.headers,
            params=params or {},
            timeout=30
        )

        response.raise_for_status()
        data = response.json()

        if not isinstance(data, dict):
            raise RuntimeError("Risposta API non valida.")

        errors = data.get("errors")

        if errors:
            raise RuntimeError(
                f"API-Football: {errors}"
            )

        return data.get("response", [])

    def get_next_fixtures(self, count=50):
        """
        Recupera le partite di ieri, oggi e domani.
        Evita il parametro next non disponibile
        nel piano gratuito.
        """

        today = datetime.now(
            ZoneInfo("Europe/Rome")
        ).date()

        fixtures = []
        seen_ids = set()

        for day in range(-1, 2):

            current_date = (
                today + timedelta(days=day)
            ).isoformat()

            data = self._get(
                "fixtures",
                {
                    "date": current_date
                }
            )

            for item in data:

                fixture = item.get("fixture", {})
                league = item.get("league", {})
                teams = item.get("teams", {})

                fixture_id = fixture.get("id")

                if not fixture_id or fixture_id in seen_ids:
                    continue

                home = teams.get("home", {})
                away = teams.get("away", {})

                fixtures.append({
                    "fixture_id": fixture_id,
                    "date": fixture.get("date"),
                    "league": league.get("name"),
                    "league_id": league.get("id"),
                    "season": league.get("season"),
                    "country": league.get("country"),
                    "home": home.get("name"),
                    "away": away.get("name"),
                    "home_id": home.get("id"),
                    "away_id": away.get("id"),
                    "status": fixture.get(
                        "status", {}
                    ).get("short")
                })

                seen_ids.add(fixture_id)

        fixtures.sort(
            key=lambda x: x["date"] or ""
        )

        return fixtures[:count]

    def get_team_season_stats(
        self,
        team_id,
        league_id,
        season,
        cutoff=None
    ):

        params = {
            "team": team_id,
            "league": league_id,
            "season": season
        }

        if cutoff:
            params["date"] = cutoff

        data = self._get(
            "teams/statistics",
            params
        )

        if isinstance(data, dict):
            return data

        if isinstance(data, list) and data:
            return data[0]

        return {}

    def get_last_fixtures(
        self,
        team_id,
        count=10,
        cutoff=None
    ):

        params = {
            "team": team_id,
            "last": count
        }

        if cutoff:
            params["to"] = cutoff

        return self._get(
            "fixtures",
            params
        )
