

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests


class SoccerDataProvider:
    """
    Provider Soccer Data.
    Versione iniziale dedicata al recupero del calendario.
    Non contiene ancora statistiche per il modello predittivo.
    """

    BASE_URL = "https://api.soccer-data.co/v1"

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("SOCCER_DATA_KEY")

        if not self.api_key:
            raise ValueError(
                "Chiave API Soccer Data mancante. "
                "Configura SOCCER_DATA_KEY."
            )

        self.session = requests.Session()
        self.session.headers.update({
            "X-Api-Key": self.api_key
        })

    def _request(self, endpoint, params=None):
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        response = self.session.get(
            url,
            params=params or {},
            timeout=30
        )

        if response.status_code == 401:
            raise RuntimeError(
                "Autenticazione Soccer Data fallita. "
                "Verifica la chiave API."
            )

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            message = "Limite richieste Soccer Data raggiunto."

            if retry_after:
                message += f" Attendere {retry_after} secondi."

            raise RuntimeError(message)

        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            raise RuntimeError("Risposta API non valida.")

        if "data" not in payload:
            raise RuntimeError(
                "La risposta API non contiene il campo 'data'."
            )

        return payload

    @staticmethod
    def _normalize_match(match):
        home_team = match.get("home_team") or {}
        away_team = match.get("away_team") or {}
        score = match.get("score") or {}

        return {
            "id": match.get("id"),
            "fixture_id": match.get("id"),

            "date": match.get("utc_date"),
            "utc_date": match.get("utc_date"),

            "competition_id": match.get("competition_id"),
            "season_id": match.get("season_id"),
            "matchday": match.get("matchday"),

            "home": home_team.get("name"),
            "away": away_team.get("name"),

            "home_id": home_team.get("id"),
            "away_id": away_team.get("id"),

            "home_team": home_team.get("name"),
            "away_team": away_team.get("name"),

            "home_team_id": home_team.get("id"),
            "away_team_id": away_team.get("id"),

            "status": match.get("status"),

            "home_goals": score.get("home"),
            "away_goals": score.get("away"),

            "score": score,

            "xg_available": match.get("xg_available"),
            "shotmap_available": match.get("shotmap_available"),

            "raw": match
        }

    def get_fixtures(
        self,
        days_ahead=14,
        per_page=100,
        max_matches=None
    ):
        """
        Recupera le partite programmate nei prossimi giorni.

        days_ahead:
            Numero di giorni da oggi.

        per_page:
            Numero di partite per pagina (massimo 100).

        max_matches:
            Limite opzionale di partite da restituire.
        """

        if not 1 <= per_page <= 100:
            raise ValueError(
                "per_page deve essere compreso tra 1 e 100."
            )

        today = datetime.now(
            ZoneInfo("Europe/Rome")
        ).date()

        date_to = today + timedelta(days=days_ahead)

        params = {
            "status": "scheduled",
            "date_from": today.isoformat(),
            "date_to": date_to.isoformat(),
            "utc_offset": "+01:00",
            "sort": "utc_date",
            "per_page": per_page,
            "page": 1
        }

        fixtures = []

        while True:
            payload = self._request(
                "matches",
                params=params
            )

            data = payload.get("data", [])
            meta = payload.get("meta", {})

            fixtures.extend(
                self._normalize_match(match)
                for match in data
            )

            total_pages = meta.get("total_pages", 1)
            current_page = meta.get("page", params["page"])

            if max_matches and len(fixtures) >= max_matches:
                fixtures = fixtures[:max_matches]
                break

            if current_page >= total_pages:
                break

            params["page"] += 1

        return fixtures
