from datetime import datetime, timedelta, timezone

import requests


class APIFootballProvider:
    """API-Football v3 adapter; returns the structures expected by the model."""

    def __init__(self, api_key, base_url="https://v3.football.api-sports.io"):
        self.base_url = base_url.rstrip("/")
        self.headers = {"x-apisports-key": api_key}

    def _get(self, endpoint, params=None):
        response = requests.get(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            headers=self.headers,
            params=params or {},
            timeout=30,
        )
        if response.status_code == 401:
            raise RuntimeError(
                "Autenticazione API-Football non riuscita. Controlla API_FOOTBALL_KEY."
            )
        if response.status_code == 403:
            raise RuntimeError(
                "Accesso API-Football negato: verifica piano, endpoint e copertura."
            )
        if response.status_code == 429:
            raise RuntimeError(
                "Limite richieste API-Football raggiunto. Attendi prima di riprovare."
            )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("response"), list):
            raise RuntimeError("Risposta API-Football non valida.")
        errors = data.get("errors")
        if errors:
            raise RuntimeError(f"Errore API-Football: {errors}")
        return data

    @staticmethod
    def _normalize_match(item):
        fixture = item.get("fixture") or {}
        league = item.get("league") or {}
        teams = item.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        goals = item.get("goals") or {}
        status = (fixture.get("status") or {}).get("short")
        return {
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
            "status": status,
            "fixture": {
                "id": fixture.get("id"),
                "date": fixture.get("date"),
                "status": {"short": status},
            },
            "teams": {
                "home": {"id": home.get("id"), "name": home.get("name")},
                "away": {"id": away.get("id"), "name": away.get("name")},
            },
            "goals": {"home": goals.get("home"), "away": goals.get("away")},
        }

    def get_next_fixtures(self, count=500, days=30):
        today = datetime.now(timezone.utc).date()
        params = {
            "from": today.isoformat(),
            "to": (today + timedelta(days=days)).isoformat(),
            "timezone": "Europe/Rome",
            "page": 1,
        }
        matches = []
        while True:
            data = self._get("fixtures", params)
            matches.extend(self._normalize_match(item) for item in data["response"])
            paging = data.get("paging") or {}
            current = int(paging.get("current") or params["page"])
            total = int(paging.get("total") or current)
            if current >= total or len(matches) >= count:
                break
            params["page"] = current + 1
        matches.sort(key=lambda match: match["date"] or "")
        return matches[:count]

    def _get_team_matches(self, team_id, season, league_id=None, cutoff=None):
        params = {
            "team": team_id,
            "season": season,
            "last": 20,
            "status": "FT-AET-PEN",
            "timezone": "Europe/Rome",
        }
        if league_id is not None:
            params["league"] = league_id
        if cutoff:
            params["to"] = cutoff
        data = self._get("fixtures", params)
        matches = [self._normalize_match(item) for item in data["response"]]
        matches.sort(key=lambda match: match["date"] or "")
        return matches

    def get_team_season_stats(self, team_id, league_id, season, cutoff=None):
        params = {"team": team_id, "league": league_id, "season": season}
        if cutoff:
            params["date"] = cutoff
        data = self._get("teams/statistics", params)
        result = data["response"] or {}
        goals = result.get("goals") or {}
        scored = goals.get("for") or {}
        conceded = goals.get("against") or {}
        scored_avg = scored.get("average") or {}
        conceded_avg = conceded.get("average") or {}

        def number(value):
            try:
                return round(float(value), 3) if value is not None and value != "-" else None
            except (TypeError, ValueError):
                return None

        return {
            "goals": {
                "for": {"average": {
                    "home": number(scored_avg.get("home")),
                    "away": number(scored_avg.get("away")),
                    "total": number(scored_avg.get("total")),
                }},
                "against": {"average": {
                    "home": number(conceded_avg.get("home")),
                    "away": number(conceded_avg.get("away")),
                    "total": number(conceded_avg.get("total")),
                }},
            }
        }

    def get_last_fixtures(
        self, team_id, count=10, cutoff=None, season=None, league_id=None
    ):
        if season is None:
            raise ValueError("La stagione è necessaria per recuperare la forma recente.")
        matches = self._get_team_matches(team_id, season, league_id, cutoff)
        completed = [
            match for match in matches if match["status"] in {"FT", "AET", "PEN"}
        ]
        return completed[-count:]
