
import requests
from datetime import datetime, timezone


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

        errors = data.get("errors")
        if errors:
            raise RuntimeError(f"API-Football: {errors}")

        return data.get("response", [])

    def get_next_fixtures(self, count=50):
        data = self._get(
            "fixtures",
            {"next": count}
        )

        fixtures = []

        for item in data:
            fixture = item.get("fixture", {})
            league = item.get("league", {})
            teams = item.get("teams", {})

            home = teams.get("home", {})
            away = teams.get("away", {})

            fixtures.append({
                "fixture_id": fixture.get("id"),
                "date": fixture.get("date"),
                "league": league.get("name"),
                "league_id": league.get("id"),
                "season": league.get("season"),
                "country": league.get("country"),
                "home": home.get("name"),
                "away": away.get("name"),
                "home_id": home.get("id"),
                "away_id": away.get("id"),
                "status": fixture.get("status", {}).get("short")
            })

        return fixtures

    def get_team_season_stats(
        self, team_id, league_id, season, cutoff=None
    ):
        params = {
            "team": team_id,
            "league": league_id,
            "season": season
        }

        if cutoff:
            params["date"] = cutoff

        data = self._get("teams/statistics", params)

        return data[0] if data else {}

    def get_last_fixtures(self, team_id, count=10, cutoff=None):
        params = {
            "team": team_id,
            "last": count
        }

        if cutoff:
            params["to"] = cutoff

        return self._get("fixtures", params)
