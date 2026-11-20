
import os
from datetime import datetime

from football_predictor.soccer_data_provider import (
    SoccerDataProvider
)


def main():

    print("=" * 60)
    print("TEST SOCCER DATA PROVIDER")
    print("=" * 60)

    api_key = os.getenv("SOCCER_DATA_KEY")

    if not api_key:
        print("ERRORE: SOCCER_DATA_KEY non configurata.")
        return

    provider = SoccerDataProvider(api_key)

    print("\nRecupero partite prossimi 14 giorni...")

    fixtures = provider.get_fixtures(
        days_ahead=14,
        per_page=100,
        max_matches=20
    )

    print(f"\nPartite recuperate: {len(fixtures)}")

    if not fixtures:
        print("Nessuna partita trovata.")
        return

    print("\n" + "=" * 60)
    print("ELENCO PARTITE")
    print("=" * 60)

    competitions = set()

    for match in fixtures:

        date = match.get("date")
        competition_id = match.get("competition_id")
        season_id = match.get("season_id")

        competitions.add(competition_id)

        print("\n----------------------------------------")

        print(f"Data UTC: {date}")
        print(f"Competizione ID: {competition_id}")
        print(f"Stagione ID: {season_id}")

        print(
            f"{match.get('home')} "
            f"vs "
            f"{match.get('away')}"
        )

        print(f"Status: {match.get('status')}")

    print("\n" + "=" * 60)
    print("RIEPILOGO")
    print("=" * 60)

    print(f"Partite totali: {len(fixtures)}")
    print(f"Competizioni individuate: {len(competitions)}")

    for competition in sorted(
        str(c) for c in competitions if c is not None
    ):
        print(f"- {competition}")

    print("\nTEST COMPLETATO")


if __name__ == "__main__":
    main()
