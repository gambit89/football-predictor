
import streamlit as st
import pandas as pd

from football_predictor.soccer_data_provider import SoccerDataProvider


st.set_page_config(
    page_title="Soccer Data Coverage",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Soccer Data – Coverage Dashboard")
st.caption("Analisi completa delle competizioni e disponibilità dati")


if "SOCCER_DATA_KEY" not in st.secrets:
    st.error("SOCCER_DATA_KEY non configurata.")
    st.stop()

provider = SoccerDataProvider(
    st.secrets["SOCCER_DATA_KEY"]
)

st.success("Connessione API configurata correttamente.")


def fetch_all_competitions():

    competitions = []
    page = 1
    total_pages = 1

    while page <= total_pages:

        payload = provider._request(
            "competitions",
            params={
                "page": page,
                "per_page": 100,
                "sort": "name"
            }
        )

        competitions.extend(
            payload.get("data", [])
        )

        meta = payload.get("meta", {})

        total_pages = meta.get(
            "total_pages",
            1
        )

        page += 1

    return competitions


if st.button("🔍 Analizza copertura completa"):

    try:

        with st.spinner(
            "Recupero competizioni e analisi dati..."
        ):

            competitions = fetch_all_competitions()

        if not competitions:

            st.warning("Nessuna competizione trovata.")
            st.stop()

        df = pd.DataFrame(competitions)

        # Normalizzazione campi booleani
        boolean_columns = [
            "has_team_stats",
            "has_player_stats",
            "odds_available",
            "live_odds_available",
            "xg_available"
        ]

        for column in boolean_columns:

            if column not in df.columns:
                df[column] = False

            df[column] = df[column].fillna(False)

        st.success(
            f"Competizioni recuperate: {len(df)}"
        )

        # ------------------------------------------------
        # KPI
        # ------------------------------------------------

        st.subheader("📊 Riepilogo copertura")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Competizioni",
            len(df)
        )

        col2.metric(
            "Con xG",
            int(df["xg_available"].sum())
        )

        col3.metric(
            "Team Stats",
            int(df["has_team_stats"].sum())
        )

        col4.metric(
            "Player Stats",
            int(df["has_player_stats"].sum())
        )

        col5, col6, col7 = st.columns(3)

        col5.metric(
            "Con quote",
            int(df["odds_available"].sum())
        )

        col6.metric(
            "Quote live",
            int(df["live_odds_available"].sum())
        )

        col7.metric(
            "Paesi",
            df["country"].nunique()
        )

        # ------------------------------------------------
        # COPERTURA PER PAESE
        # ------------------------------------------------

        st.subheader("🌍 Competizioni per paese")

        country_stats = (
            df.groupby("country", dropna=False)
            .agg(
                Competizioni=("id", "count"),
                xG=("xg_available", "sum"),
                TeamStats=("has_team_stats", "sum"),
                PlayerStats=("has_player_stats", "sum"),
                Quote=("odds_available", "sum")
            )
            .reset_index()
            .sort_values(
                "Competizioni",
                ascending=False
            )
        )

        st.dataframe(
            country_stats,
            use_container_width=True,
            hide_index=True
        )

        # ------------------------------------------------
        # FILTRI
        # ------------------------------------------------

        st.subheader("🔎 Filtra competizioni")

        countries = sorted(
            [
                str(c)
                for c in df["country"].dropna().unique()
            ]
        )

        selected_country = st.selectbox(
            "Paese",
            ["Tutti"] + countries
        )

        filtered_df = df.copy()

        if selected_country != "Tutti":

            filtered_df = filtered_df[
                filtered_df["country"] == selected_country
            ]

        xg_filter = st.checkbox(
            "Solo competizioni con xG"
        )

        if xg_filter:

            filtered_df = filtered_df[
                filtered_df["xg_available"] == True
            ]

        stats_filter = st.checkbox(
            "Solo competizioni con statistiche squadre"
        )

        if stats_filter:

            filtered_df = filtered_df[
                filtered_df["has_team_stats"] == True
            ]

        odds_filter = st.checkbox(
            "Solo competizioni con quote"
        )

        if odds_filter:

            filtered_df = filtered_df[
                filtered_df["odds_available"] == True
            ]

        # ------------------------------------------------
        # TABELLA COMPETIZIONI
        # ------------------------------------------------

        st.subheader(
            f"🏆 Competizioni ({len(filtered_df)})"
        )

        preferred_columns = [
            "id",
            "name",
            "country",
            "country_code",
            "confederation",
            "type",
            "has_team_stats",
            "has_player_stats",
            "odds_available",
            "live_odds_available",
            "xg_available"
        ]

        available_columns = [
            c for c in preferred_columns
            if c in filtered_df.columns
        ]

        st.dataframe(
            filtered_df[available_columns],
            use_container_width=True,
            hide_index=True
        )

        # ------------------------------------------------
        # EXPORT
        # ------------------------------------------------

        csv = filtered_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Scarica competizioni CSV",
            data=csv,
            file_name="soccer_data_competitions.csv",
            mime="text/csv"
        )

        # ------------------------------------------------
        # ANALISI QUALITÀ DATI
        # ------------------------------------------------

        st.subheader("📈 Disponibilità dati")

        coverage = pd.DataFrame({
            "Tipo dato": [
                "Team Stats",
                "Player Stats",
                "xG",
                "Quote",
                "Quote Live"
            ],
            "Competizioni": [
                int(df["has_team_stats"].sum()),
                int(df["has_player_stats"].sum()),
                int(df["xg_available"].sum()),
                int(df["odds_available"].sum()),
                int(df["live_odds_available"].sum())
            ]
        })

        st.bar_chart(
            coverage.set_index("Tipo dato")
        )

        # ------------------------------------------------
        # RAW
        # ------------------------------------------------

        with st.expander(
            "Visualizza risposta API originale"
        ):

            st.json(competitions)

    except Exception as e:

        st.error(
            f"Errore durante l'analisi: {e}"
        )
