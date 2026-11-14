
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
        """
        Esegue una richiesta all'API-Football
        e restituisce il contenuto del campo response.
        """

        response = requests.get(
            f"{self.base_url}/{endpoint}",
            headers=self.headers,
            params=params or {},
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise RuntimeError(
                "Risposta API non valida."
            )

        errors = data.get("errors")

        if errors:
            raise RuntimeError(
                f"API-Football: {errors}"
            )

        return data.get("response", [])

    def get_next_fixtures(self, count=50):
        """
        Recupera le partite dei prossimi 14 giorni.

        Non utilizza il parametro 'next', non disponibile
        nel piano gratuito API-Football.

        Utilizza invece i parametri 'from' e 'to'.
        """

        today = datetime.now(
            ZoneInfo("Europe/Rome")
        ).date()

        end_date = today + timedelta(days=14)

        params = {
            "from": today.isoformat(),
            "to": end_date.isoformat(),
            "timezone": "Europe/Rome"
        }

        data = self._get(
            "fixtures",
            params
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
                "status": fixture.get(
                    "status", {}
                ).get("short")
            })

        # Ordina le partite in base alla data
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
        """
        Recupera le statistiche stagionali della squadra.

        cutoff limita le statistiche alle partite
        disputate fino alla data indicata.
        """

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

        # L'endpoint restituisce normalmente un dizionario.
        # Manteniamo anche la compatibilità con eventuali liste.
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
        """
        Recupera le ultime partite della squadra.

        Se cutoff è presente, limita la ricerca
        alle partite precedenti o coincidenti
        con la data indicata.
        """

        params = {
            "team": team_id,
            "last": count
        }

        if cutoff:
            params["to"] = cutoff

        data = self._get(
            "fixtures",
            params
        )

        return data
