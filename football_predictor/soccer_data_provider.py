
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests


class SoccerDataProvider:
    """
    Provider Soccer Data.

    Versione iniziale:
    - Recupero calendario
    - Normalizzazione delle partite
    - Compatibilità strutturale con Football Predictor
    - Nessuna modifica al modello Poisson
    """

    BASE_URL = "https://api.soccer-data.co/v1"
    ITALY_TZ = ZoneInfo("Europe/Rome")

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

    # --------------------------------------------------
    # API REQUEST
    # --------------------------------------------------

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

        if response.status_code == 403:
            raise RuntimeError(
                "Accesso negato. Verifica la copertura "
                "del tuo piano API."
            )

        if response.status_code == 429:
            retry_after = response.headers.get(
                "Retry-After"
            )

            message = (
                "Limite richieste Soccer Data raggiunto."
            )

            if retry_after:
                message += (
                    f" Attendere {retry_after} secondi."
                )

            raise RuntimeError(message)

        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            raise RuntimeError(
                "Risposta API non valida."
            )

        if "data" not in payload:
            raise RuntimeError(
                "Risposta API priva del campo data."
            )

        return payload

    # --------------------------------------------------
    # NORMALIZZAZIONE
    # --------------------------------------------------

    @staticmethod
    def _normalize_match(match):

        home_team = match.get("home_team") or {}
        away_team = match.get("away_team") or {}
        score = match.get("score") or {}

        match_id = match.get("id")
        match_date = match.get("utc_date")

        competition_id = match.get("competition_id")
        season_id = match.get("season_id")

        status = match.get("status")

        status_map = {
            "finished": "FT",
            "live": "LIVE",
            "scheduled": "NS",
            "postponed": "PST",
            "cancelled": "CANC"
        }

        normalized_status = status_map.get(
            status,
            status
        )

        return {

            # ------------------------------------------
            # IDENTIFICATIVI
            # ------------------------------------------

            "fixture_id": match_id,
            "id": match_id,

            "competition_id": competition_id,
            "season_id": season_id,

            "home_id": home_team.get("id"),
            "away_id": away_team.get("id"),

            "home_team_id": home_team.get("id"),
            "away_team_id": away_team.get("id"),

            # ------------------------------------------
            # DATA
            # ------------------------------------------

            "date": match_date,
            "utc_date": match_date,

            # ------------------------------------------
            # COMPETIZIONE
            # ------------------------------------------

            "league": competition_id,
            "league_id": competition_id,

            "country": None,
            "season": None,

            "matchday": match.get("matchday"),

            # ------------------------------------------
            # SQUADRE
            # ------------------------------------------

            "home": home_team.get("name"),
            "away": away_team.get("name"),

            "home_team": home_team.get("name"),
            "away_team": away_team.get("name"),

            # ------------------------------------------
            # STATO
            # ------------------------------------------

            "status": normalized_status,

            "fixture": {
                "id": match_id,
                "date": match_date,
                "status": {
                    "short": normalized_status
                }
            },

            # ------------------------------------------
            # SQUADRE - FORMATO COMPATIBILE
            # ------------------------------------------

            "teams": {
                "home": {
                    "id": home_team.get("id"),
                    "name": home_team.get("name")
                },
                "away": {
                    "id": away_team.get("id"),
                    "name": away_team.get("name")
                }
            },

            # ------------------------------------------
            # RISULTATO
            # ------------------------------------------

            "goals": {
                "home": score.get("home"),
                "away": score.get("away")
            },

            "home_goals": score.get("home"),
            "away_goals": score.get("away"),

            "score": score,

            # ------------------------------------------
            # DISPONIBILITÀ DATI
            # ------------------------------------------

            "xg_available": match.get(
                "xg_available",
                False
            ),

            "shotmap_available": match.get(
                "shotmap_available",
                False
            ),

            "odds_available": match.get(
                "odds_available",
                False
            ),

            # ------------------------------------------
            # DATI ORIGINALI
            # ------------------------------------------

            "raw": match
        }

    # --------------------------------------------------
    # CALENDARIO
    # --------------------------------------------------

    def get_fixtures(
        self,
        days_ahead=14,
        per_page=100,
        max_matches=None
    ):

        if days_ahead < 0:
            raise ValueError(
                "days_ahead non può essere negativo."
            )

        if not 1 <= per_page <= 100:
            raise ValueError(
                "per_page deve essere compreso tra 1 e 100."
            )

        # Data e offset orario italiano dinamico
        now_italy = datetime.now(
            self.ITALY_TZ
        )

        today = now_italy.date()

        date_to = today + timedelta(
            days=days_ahead
        )

        utc_offset = now_italy.strftime("%z")

        utc_offset = (
            utc_offset[:3]
            + ":"
            + utc_offset[3:]
        )

        params = {
            "status": "scheduled",
            "date_from": today.isoformat(),
            "date_to": date_to.isoformat(),
            "utc_offset": utc_offset,
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

            data = payload.get(
                "data",
                []
            )

            meta = payload.get(
                "meta",
                {}
            )

            fixtures.extend(
                self._normalize_match(match)
                for match in data
            )

            total_pages = meta.get(
                "total_pages",
                1
            )

            current_page = meta.get(
                "page",
                params["page"]
            )

            # Limite opzionale
            if max_matches is not None:

                if len(fixtures) >= max_matches:

                    fixtures = fixtures[:max_matches]

                    break

            # Fine paginazione
            if current_page >= total_pages:
                break

            params["page"] += 1

        # Ordinamento cronologico
        fixtures.sort(
            key=lambda match: (
                match.get("date") or ""
            )
        )

        return fixtures

    # --------------------------------------------------
    # ALIAS COMPATIBILITÀ
    # --------------------------------------------------

    def get_next_fixtures(
        self,
        count=50,
        days_ahead=14
    ):

        return self.get_fixtures(
            days_ahead=days_ahead,
            per_page=100,
            max_matches=count
        )
