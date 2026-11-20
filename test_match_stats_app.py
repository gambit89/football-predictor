
import streamlit as st
import pandas as pd

from datetime import date, timedelta

from football_predictor.soccer_data_provider import SoccerDataProvider


st.set_page_config(
    page_title="Soccer Data - Match Stats",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Match Stats Analyzer")
st.caption("Test di recupero statistiche e xG delle partite concluse")

if "SOCCER_DATA_KEY" not in st.secrets:
    st.error("SOCCER_DATA_KEY non configurata.")
    st.stop()

provider = SoccerDataProvider(
    st.secrets["SOCCER_DATA_KEY"]
)


# --------------------------------------------------
# RECUPERO PARTITE CONCLUSE RECENTI
# --------------------------------------------------

@st.cache_data(ttl=1800)
def fetch_finished_matches():

    date_to = date.today()
    date_from = date_to - timedelta(days=30)

    payload = provider._request(
        "matches",
        params={
            "status": "finished",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "per_page": 100,
            "page": 1
        }
    )

    return payload.get("data", [])


# --------------------------------------------------
# RECUPERO STATISTICHE PARTITA
# --------------------------------------------------

def fetch_match_stats(match_id):

    return provider._request(
        f"matches/{match_id}/stats"
    )


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

try:

    matches = fetch_finished_matches()

    st.success(
        f"Partite concluse recuperate: {len(matches)}"
    )

    if not matches:

        st.warning("Nessuna partita conclusa disponibile.")

        st.stop()

    # --------------------------------------------------
    # DATAFRAME PARTITE
    # --------------------------------------------------

    df_matches = pd.json_normalize(matches)

    st.subheader("📋 Partite disponibili")

    display_columns = [
        "id",
        "utc_date",
        "home_team.name",
        "away_team.name",
        "competition_id",
        "xg_available"
    ]

    display_columns = [
        c for c in display_columns
        if c in df_matches.columns
    ]

    st.dataframe(
        df_matches[display_columns],
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------
    # SELEZIONE PARTITA
    # --------------------------------------------------

    match_options = {}

    for match in matches:

        home = (
            match.get("home_team", {})
            .get("name", "Home")
        )

        away = (
            match.get("away_team", {})
            .get("name", "Away")
        )

        date = match.get(
            "utc_date",
            ""
        )

        competition = match.get(
            "competition_id",
            ""
        )

        match_id = match.get("id")

        label = (
            f"{date[:10]} | "
            f"{home} - {away} | "
            f"{competition}"
        )

        match_options[label] = match_id

    selected_match = st.selectbox(
        "Seleziona una partita conclusa",
        options=list(match_options.keys())
    )

    selected_match_id = match_options[
        selected_match
    ]

    # --------------------------------------------------
    # ANALISI STATISTICHE
    # --------------------------------------------------

    if st.button("🔬 Recupera statistiche partita"):

        try:

            with st.spinner(
                "Recupero statistiche in corso..."
            ):

                payload = fetch_match_stats(
                    selected_match_id
                )

            data = payload.get(
                "data",
                {}
            )

            st.success(
                "Statistiche recuperate correttamente."
            )

            # ------------------------------------------
            # DATI GENERALI
            # ------------------------------------------

            st.subheader("📊 Statistiche principali")

            overview = data.get(
                "overview",
                {}
            )

            overview_rows = []

            for stat_name, stat_data in overview.items():

                if not isinstance(stat_data, dict):
                    continue

                all_data = stat_data.get(
                    "all"
                )

                if isinstance(all_data, dict):

                    overview_rows.append({

                        "Statistica": stat_name,

                        "Home": all_data.get(
                            "home"
                        ),

                        "Away": all_data.get(
                            "away"
                        )

                    })

            if overview_rows:

                df_overview = pd.DataFrame(
                    overview_rows
                )

                st.dataframe(
                    df_overview,
                    use_container_width=True,
                    hide_index=True
                )

            # ------------------------------------------
            # xG
            # ------------------------------------------

            st.subheader("🎯 Expected Goals")

            xg = overview.get(
                "expected_goals",
                {}
            )

            if xg:

                st.json(xg)

            else:

                st.warning(
                    "xG non disponibile per questa partita."
                )

            # ------------------------------------------
            # NON-PENALTY xG
            # ------------------------------------------

            st.subheader("⚽ Non-Penalty xG")

            st.json(
                data.get(
                    "np_expected_goals"
                )
            )

            # ------------------------------------------
            # STATISTICHE COMPLETE
            # ------------------------------------------

            st.subheader("📚 Tutte le statistiche")

            for section, values in data.items():

                if section in [
                    "match_id",
                    "overview",
                    "np_expected_goals"
                ]:
                    continue

                with st.expander(
                    section.replace("_", " ").title()
                ):

                    st.json(values)

            # ------------------------------------------
            # RISPOSTA RAW
            # ------------------------------------------

            with st.expander(
                "🔎 Risposta API completa"
            ):

                st.json(payload)

        except Exception as e:

            st.error(
                f"Errore recupero statistiche: {e}"
            )

except Exception as e:

    st.error(
        f"Errore durante il recupero partite: {e}"
    )
