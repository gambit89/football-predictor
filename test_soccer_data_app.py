
import streamlit as st
import pandas as pd

from football_predictor.soccer_data_provider import SoccerDataProvider


st.set_page_config(
    page_title="Soccer Data - Historical Analysis",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Soccer Data – Analisi storica")
st.caption("Analisi qualità e profondità dati per competizione e stagione")

if "SOCCER_DATA_KEY" not in st.secrets:
    st.error("SOCCER_DATA_KEY non configurata.")
    st.stop()

provider = SoccerDataProvider(
    st.secrets["SOCCER_DATA_KEY"]
)


# --------------------------------------------------
# RECUPERO COMPETIZIONI
# --------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_coverage_competitions():

    results = []
    page = 1
    total_pages = 1

    while page <= total_pages:

        payload = provider._request(
            "coverage/leagues",
            params={
                "page": page,
                "per_page": 200
            }
        )

        results.extend(payload.get("data", []))

        total_pages = payload.get(
            "meta", {}
        ).get("total_pages", 1)

        page += 1

    return results


# --------------------------------------------------
# RECUPERO COPERTURA SINGOLA COMPETIZIONE
# --------------------------------------------------

def fetch_competition_detail(competition_id):

    payload = provider._request(
        f"coverage/leagues/{competition_id}"
    )

    return payload.get("data", {})


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

try:

    competitions = fetch_coverage_competitions()

    st.success(
        f"Competizioni disponibili: {len(competitions)}"
    )

    # Solo competizioni con xG
    xg_competitions = [
        c for c in competitions
        if c.get("data_types", {})
        .get("xg", {})
        .get("available", False)
    ]

    st.metric(
        "Competizioni con xG",
        len(xg_competitions)
    )

    st.divider()

    st.subheader("🔎 Selezione competizioni")

    competition_options = {
        f"{c.get('name')} | {c.get('country') or 'Internazionale'}":
        c.get("id")
        for c in xg_competitions
    }

    selected_names = st.multiselect(
        "Seleziona le competizioni da analizzare",
        options=list(competition_options.keys()),
        default=list(competition_options.keys())[:10]
    )

    st.caption(
        "Per limitare le richieste API, iniziamo con "
        "un gruppo selezionato di competizioni."
    )

    # --------------------------------------------------
    # ANALISI STAGIONI
    # --------------------------------------------------

    if st.button("🔬 Analizza stagioni selezionate"):

        selected_ids = [
            competition_options[name]
            for name in selected_names
        ]

        results = []

        progress = st.progress(0)

        for index, competition_id in enumerate(selected_ids):

            try:

                data = fetch_competition_detail(
                    competition_id
                )

                competition_name = data.get("name")
                country = data.get("country")

                seasons = data.get("seasons", [])

                for season in seasons:

                    events = season.get(
                        "events", {}
                    )

                    data_types = season.get(
                        "data_types", {}
                    )

                    xg = data_types.get(
                        "xg", {}
                    )

                    team_stats = data_types.get(
                        "team_stats", {}
                    )

                    fixtures = data_types.get(
                        "fixtures", {}
                    )

                    results.append({

                        "Competizione": competition_name,
                        "Paese": country,
                        "Stagione": season.get("year"),
                        "Stato": season.get("status"),

                        "Partite giocate":
                            events.get("finished", 0),

                        "Partite totali":
                            events.get("total", 0),

                        "xG disponibile":
                            xg.get("available", False),

                        "Match con xG":
                            xg.get("covered_events", 0),

                        "Copertura xG %":
                            xg.get("coverage_pct", 0),

                        "Team stats":
                            team_stats.get("available", False),

                        "Match con statistiche":
                            team_stats.get("covered_events", 0),

                        "Copertura statistiche %":
                            team_stats.get("coverage_pct", 0),

                        "Fixtures":
                            fixtures.get("available", False)

                    })

            except Exception as e:

                st.warning(
                    f"Errore su {competition_id}: {e}"
                )

            progress.progress(
                (index + 1) / max(len(selected_ids), 1)
            )

        # --------------------------------------------------
        # RISULTATI
        # --------------------------------------------------

        if results:

            df = pd.DataFrame(results)

            st.success(
                f"Stagioni analizzate: {len(df)}"
            )

            st.subheader("📊 Copertura stagione per stagione")

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            # --------------------------------------------------
            # FILTRI
            # --------------------------------------------------

            st.subheader("🎯 Stagioni con copertura xG")

            df_xg = df[
                df["xG disponibile"] == True
            ]

            st.dataframe(
                df_xg,
                use_container_width=True,
                hide_index=True
            )

            # --------------------------------------------------
            # EXPORT
            # --------------------------------------------------

            csv = df.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                "⬇️ Scarica analisi stagioni CSV",
                data=csv,
                file_name="historical_coverage.csv",
                mime="text/csv"
            )

        else:

            st.warning(
                "Nessun dato restituito per le competizioni selezionate."
            )

except Exception as e:

    st.error(
        f"Errore durante il caricamento: {e}"
    )
