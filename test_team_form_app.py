
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from football_predictor.soccer_data_provider import SoccerDataProvider


st.set_page_config(
    page_title="Football Predictor - Team Form",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Team Form Analyzer")
st.caption("Analisi gol stagionali, casa/trasferta e ultime 5 partite")

if "SOCCER_DATA_KEY" not in st.secrets:
    st.error("SOCCER_DATA_KEY non configurata.")
    st.stop()

provider = SoccerDataProvider(
    st.secrets["SOCCER_DATA_KEY"]
)


# ==================================================
# COMPETIZIONI
# ==================================================

@st.cache_data(ttl=3600)
def fetch_competitions():

    results = []
    page = 1
    total_pages = 1

    while page <= total_pages:

        payload = provider._request(
            "competitions",
            params={
                "per_page": 100,
                "page": page
            }
        )

        results.extend(payload.get("data", []))

        total_pages = payload.get(
            "meta", {}
        ).get("total_pages", 1)

        page += 1

    return results


# ==================================================
# PARTITE CONCLUSE
# ==================================================

@st.cache_data(ttl=1800)
def fetch_matches(competition_id, date_from, date_to):

    results = []
    page = 1
    total_pages = 1

    while page <= total_pages:

        payload = provider._request(
            "matches",
            params={
                "competition_id": competition_id,
                "status": "finished",
                "date_from": date_from,
                "date_to": date_to,
                "per_page": 100,
                "page": page
            }
        )

        results.extend(
            payload.get("data", [])
        )

        total_pages = payload.get(
            "meta", {}
        ).get("total_pages", 1)

        page += 1

    return results


# ==================================================
# ELABORAZIONE DATI SQUADRE
# ==================================================

def analyze_teams(matches):

    team_data = {}

    for match in matches:

        home = match.get("home_team") or {}
        away = match.get("away_team") or {}
        score = match.get("score") or {}

        home_name = home.get("name")
        away_name = away.get("name")

        home_goals = score.get("home")
        away_goals = score.get("away")

        if (
            not home_name
            or not away_name
            or home_goals is None
            or away_goals is None
        ):
            continue

        match_date = match.get("utc_date", "")

        # ------------------------------------------
        # INIZIALIZZAZIONE SQUADRE
        # ------------------------------------------

        for team_name in [home_name, away_name]:

            if team_name not in team_data:

                team_data[team_name] = {
                    "matches": [],
                    "home_matches": [],
                    "away_matches": []
                }

        # ------------------------------------------
        # REGISTRAZIONE PARTITA HOME
        # ------------------------------------------

        home_record = {
            "date": match_date,
            "team": home_name,
            "opponent": away_name,
            "venue": "Home",
            "goals_for": home_goals,
            "goals_against": away_goals
        }

        team_data[home_name]["matches"].append(
            home_record
        )

        team_data[home_name]["home_matches"].append(
            home_record
        )

        # ------------------------------------------
        # REGISTRAZIONE PARTITA AWAY
        # ------------------------------------------

        away_record = {
            "date": match_date,
            "team": away_name,
            "opponent": home_name,
            "venue": "Away",
            "goals_for": away_goals,
            "goals_against": home_goals
        }

        team_data[away_name]["matches"].append(
            away_record
        )

        team_data[away_name]["away_matches"].append(
            away_record
        )

    # ------------------------------------------
    # ORDINAMENTO CRONOLOGICO
    # ------------------------------------------

    for team in team_data.values():

        team["matches"].sort(
            key=lambda x: x["date"]
        )

        team["home_matches"].sort(
            key=lambda x: x["date"]
        )

        team["away_matches"].sort(
            key=lambda x: x["date"]
        )

    return team_data


# ==================================================
# MEDIE
# ==================================================

def calculate_averages(matches):

    if not matches:
        return {
            "Partite": 0,
            "GF": 0,
            "GS": 0,
            "Media GF": 0,
            "Media GS": 0
        }

    played = len(matches)

    goals_for = sum(
        m["goals_for"] for m in matches
    )

    goals_against = sum(
        m["goals_against"] for m in matches
    )

    return {
        "Partite": played,
        "GF": goals_for,
        "GS": goals_against,
        "Media GF": round(goals_for / played, 3),
        "Media GS": round(goals_against / played, 3)
    }


# ==================================================
# DASHBOARD
# ==================================================

try:

    competitions = fetch_competitions()

    competition_options = {
        f"{c.get('name')} | {c.get('country') or 'Internazionale'}":
        c.get("id")
        for c in competitions
        if c.get("id") is not None
    }

    selected_competition = st.selectbox(
        "Seleziona competizione",
        options=list(competition_options.keys())
    )

    competition_id = competition_options[
        selected_competition
    ]

    col1, col2 = st.columns(2)

    with col1:

        date_from = st.date_input(
            "Inizio stagione",
            value=date(date.today().year, 7, 1)
        )

    with col2:

        date_to = st.date_input(
            "Fine analisi",
            value=date.today()
        )

    if date_from > date_to:

        st.error("La data iniziale non può essere successiva a quella finale.")
        st.stop()

    if st.button("📥 Recupera dati squadre"):

        with st.spinner("Recupero partite..."):

            matches = fetch_matches(
                competition_id,
                date_from.isoformat(),
                date_to.isoformat()
            )

            team_data = analyze_teams(
                matches
            )

            st.session_state["team_data"] = team_data
            st.session_state["team_matches"] = matches
            st.session_state["selected_competition"] = selected_competition

    # ==================================================
    # RISULTATI
    # ==================================================

    if "team_data" in st.session_state:

        team_data = st.session_state["team_data"]

        st.success(
            f"Partite recuperate: "
            f"{len(st.session_state['team_matches'])} | "
            f"Squadre: {len(team_data)}"
        )

        team_name = st.selectbox(
            "Seleziona squadra",
            options=sorted(team_data.keys())
        )

        selected_team = team_data[team_name]

        all_matches = selected_team["matches"]
        home_matches = selected_team["home_matches"]
        away_matches = selected_team["away_matches"]

        last5 = all_matches[-5:]

        # ------------------------------------------
        # MEDIE STAGIONALI
        # ------------------------------------------

        season_all = calculate_averages(
            all_matches
        )

        season_home = calculate_averages(
            home_matches
        )

        season_away = calculate_averages(
            away_matches
        )

        recent5 = calculate_averages(
            last5
        )

        # ------------------------------------------
        # KPI
        # ------------------------------------------

        st.subheader(
            f"📊 Rendimento – {team_name}"
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Partite stagione",
            season_all["Partite"]
        )

        c2.metric(
            "Gol fatti",
            season_all["GF"]
        )

        c3.metric(
            "Gol subiti",
            season_all["GS"]
        )

        c4.metric(
            "Forma ultime 5",
            f"{recent5['Media GF']} GF / "
            f"{recent5['Media GS']} GS"
        )

        # ------------------------------------------
        # RENDIMENTO STAGIONALE
        # ------------------------------------------

        st.subheader("🏟️ Rendimento stagionale")

        df_season = pd.DataFrame(
            [
                {
                    "Periodo": "Totale stagione",
                    **season_all
                },
                {
                    "Periodo": "In casa",
                    **season_home
                },
                {
                    "Periodo": "In trasferta",
                    **season_away
                }
            ]
        )

        st.dataframe(
            df_season,
            use_container_width=True,
            hide_index=True
        )

        # ------------------------------------------
        # FORMA RECENTE
        # ------------------------------------------

        st.subheader("🔥 Ultime 5 partite")

        df_recent = pd.DataFrame(
            last5
        )

        if not df_recent.empty:

            df_recent = df_recent[
                [
                    "date",
                    "opponent",
                    "venue",
                    "goals_for",
                    "goals_against"
                ]
            ].rename(
                columns={
                    "date": "Data",
                    "opponent": "Avversario",
                    "venue": "Casa/Trasferta",
                    "goals_for": "Gol fatti",
                    "goals_against": "Gol subiti"
                }
            )

            st.dataframe(
                df_recent,
                use_container_width=True,
                hide_index=True
            )

        # ------------------------------------------
        # ULTIME 5 CASA / TRASFERTA
        # ------------------------------------------

        st.subheader("🏠 Rendimento recente per sede")

        recent_home = calculate_averages(
            home_matches[-5:]
        )

        recent_away = calculate_averages(
            away_matches[-5:]
        )

        df_recent_venue = pd.DataFrame(
            [
                {
                    "Periodo": "Ultime 5 in casa",
                    **recent_home
                },
                {
                    "Periodo": "Ultime 5 in trasferta",
                    **recent_away
                }
            ]
        )

        st.dataframe(
            df_recent_venue,
            use_container_width=True,
            hide_index=True
        )

        # ------------------------------------------
        # EXPORT
        # ------------------------------------------

        st.download_button(
            "⬇️ Esporta dati squadra CSV",
            data=pd.DataFrame(all_matches).to_csv(
                index=False
            ).encode("utf-8"),
            file_name=f"{team_name}_team_data.csv",
            mime="text/csv"
        )

except Exception as e:

    st.error(
        f"Errore durante il recupero dati: {e}"
    )
