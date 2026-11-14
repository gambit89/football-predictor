
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from football_predictor.provider import APIFootballProvider
from football_predictor.model import (
    predict_match, predict_from_profiles,
    build_team_profile, score_matrix
)
from football_predictor.storage import save_prediction
from football_predictor.config import API_KEY, API_BASE_URL

st.set_page_config(
    page_title="Football Predictor",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Football Predictor")
st.caption("Previsioni pre-partita · Forma recente + rendimento stagionale · Poisson")

with st.sidebar:
    st.header("Calendario")
    days = st.slider("Giorni da visualizzare", 1, 14, 7)
    max_matches = st.slider("Partite da caricare", 10, 99, 50, 5)

    st.caption("I dati storici sono memorizzati in cache per 24 ore.")

    if st.button("Aggiorna calendario"):
        st.cache_data.clear()
        st.rerun()


def parse_date(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@st.cache_data(ttl=1800, show_spinner=False)
def load_fixtures(key, base, n):
    return APIFootballProvider(key, base).get_next_fixtures(n)


@st.cache_data(ttl=86400, show_spinner=False)
def load_team_profile(key, base, team_id, league_id, season, cutoff):
    provider = APIFootballProvider(key, base)
    stats = provider.get_team_season_stats(
        team_id, league_id, season, cutoff
    )
    recent = provider.get_last_fixtures(team_id, 10, cutoff)
    return build_team_profile(team_id, stats, recent)


if not API_KEY:
    st.warning(
        "Modalità demo: inserisci la chiave API-Football "
        "per utilizzare calendario e statistiche reali."
    )

    fixtures = [
        {
            "fixture_id": 90001,
            "date": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            "league": "Demo League",
            "league_id": 999,
            "season": 2026,
            "country": "Demo",
            "home": "North City",
            "away": "South United",
            "home_id": 1,
            "away_id": 2,
            "status": "NS"
        },
        {
            "fixture_id": 90002,
            "date": (datetime.now(timezone.utc) + timedelta(hours=9)).isoformat(),
            "league": "Demo League",
            "league_id": 999,
            "season": 2026,
            "country": "Demo",
            "home": "Riverside FC",
            "away": "Athletic Town",
            "home_id": 3,
            "away_id": 4,
            "status": "NS"
        }
    ]

else:
    try:
        with st.spinner("Caricamento calendario..."):
            fixtures = load_fixtures(
                API_KEY, API_BASE_URL, max_matches
            )

        cutoff_dt = datetime.now(timezone.utc) + timedelta(days=days)
        fixtures = [
            f for f in fixtures
            if parse_date(f["date"]) <= cutoff_dt
        ]

    except Exception as exc:
        st.error(f"Errore API: {exc}")
        fixtures = []


if not fixtures:
    st.info("Nessuna partita disponibile nell'intervallo selezionato.")
    st.stop()


rows = []

for f in fixtures:
    dt = parse_date(f["date"]).astimezone(ZoneInfo("Europe/Rome"))

    rows.append({
        "Data": dt.strftime("%d/%m %H:%M"),
        "Competizione": f"{f['league']} · {f['country']}",
        "Casa": f["home"],
        "Trasferta": f["away"],
        "_fixture": f
    })


st.subheader("Partite in programma")

st.dataframe(
    pd.DataFrame(rows).drop(columns=["_fixture"]),
    use_container_width=True,
    hide_index=True
)

options = [
    f"{r['Data']} | {r['Casa']} - {r['Trasferta']} ({r['Competizione']})"
    for r in rows
]

selected = st.selectbox("Scegli una partita", options)
match = rows[options.index(selected)]["_fixture"]

st.divider()
st.subheader(f"{match['home']} – {match['away']}")

pred = None
profiles_available = False

if (
    API_KEY
    and match.get("home_id")
    and match.get("away_id")
    and match.get("league_id")
    and match.get("season")
):
    try:
        cutoff = parse_date(match["date"]).date().isoformat()

        with st.spinner("Analisi ultime 10 partite e stagione..."):
            hp = load_team_profile(
                API_KEY, API_BASE_URL,
                match["home_id"], match["league_id"],
                match["season"], cutoff
            )

            ap = load_team_profile(
                API_KEY, API_BASE_URL,
                match["away_id"], match["league_id"],
                match["season"], cutoff
            )

        pred = predict_from_profiles(hp, ap)
        profiles_available = True

        st.caption(
            f"Campione recente: {hp['recent_matches']} partite "
            f"{match['home']} · {ap['recent_matches']} partite "
            f"{match['away']}."
        )

    except Exception as exc:
        st.warning(
            f"Impossibile recuperare tutti i dati squadra ({exc}). "
            "Uso un modello neutro dimostrativo."
        )


if pred is None:
    pred = predict_match()


c1, c2, c3 = st.columns(3)

c1.metric("xG casa", f"{pred['lambda_home']:.2f}")
c2.metric("xG trasferta", f"{pred['lambda_away']:.2f}")
c3.metric("Risultato esatto modale", pred["most_likely_score"])


st.markdown("#### Probabilità 1X2")

cols = st.columns(3)

for col, label, value in zip(
    cols,
    ["1 · Casa", "X · Pareggio", "2 · Trasferta"],
    [pred["home_win"], pred["draw"], pred["away_win"]]
):
    col.metric(label, f"{value:.1%}")


st.markdown("#### Mercati gol")

cols = st.columns(3)

cols[0].metric("Over 2.5", f"{pred['over_25']:.1%}")
cols[1].metric("Under 2.5", f"{pred['under_25']:.1%}")
cols[2].metric("Goal", f"{pred['btts']:.1%}")


st.markdown("#### Top 10 risultati esatti")

matrix = score_matrix(
    pred["lambda_home"],
    pred["lambda_away"],
    8
)

top = sorted(
    matrix.items(),
    key=lambda x: x[1],
    reverse=True
)[:10]

st.dataframe(
    pd.DataFrame([
        {"Risultato": score, "Probabilità": f"{prob:.2%}"}
        for score, prob in top
    ]),
    use_container_width=True,
    hide_index=True
)


if profiles_available:
    if st.button("Salva questa previsione nello storico"):
        save_prediction(match, pred)
        st.success("Previsione archiviata nel database locale.")
else:
    st.info(
        "Modalità demo/fallback: per ottenere stime specifiche "
        "servono dati API disponibili per competizione e squadre."
    )


st.caption(
    "Modello Poisson indipendente, prima iterazione. "
    "Le stime sono probabilistiche e non costituiscono "
    "garanzie o consigli di scommessa."
)
