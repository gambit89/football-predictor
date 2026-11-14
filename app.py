
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from football_predictor.provider import APIFootballProvider
from football_predictor.model import (
    predict_from_profiles,
    build_team_profile,
    score_matrix
)
from football_predictor.storage import save_prediction
from football_predictor.config import API_KEY, API_BASE_URL


st.set_page_config(
    page_title="Football Predictor",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Football Predictor")

st.caption(
    "Previsioni pre-partita · Forma recente + rendimento stagionale · Poisson"
)


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:
    st.header("Calendario")

    days = st.slider(
        "Giorni da visualizzare",
        1, 10, 7
    )

    max_matches = st.slider(
        "Partite da caricare",
        10, 99, 50, 5
    )

    st.caption(
        "I dati storici sono memorizzati in cache per 24 ore."
    )

    if st.button("Aggiorna calendario"):
        st.cache_data.clear()
        st.rerun()


# --------------------------------------------------
# FUNZIONI
# --------------------------------------------------

def parse_date(value):
    dt = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    return (
        dt if dt.tzinfo
        else dt.replace(tzinfo=timezone.utc)
    )


@st.cache_data(ttl=1800, show_spinner=False)
def load_fixtures(key, base, n):
    provider = APIFootballProvider(key, base)
    return provider.get_next_fixtures(n)


@st.cache_data(ttl=86400, show_spinner=False)
def load_team_profile(
    key,
    base,
    team_id,
    league_id,
    season,
    cutoff
):
    provider = APIFootballProvider(key, base)

    stats = provider.get_team_season_stats(
        team_id,
        league_id,
        season,
        cutoff
    )

    recent = provider.get_last_fixtures(
        team_id,
        10,
        cutoff,
        season=season,
        league_id=league_id
    )

    return build_team_profile(
        team_id,
        stats,
        recent
    )


# --------------------------------------------------
# CONTROLLO CONFIGURAZIONE
# --------------------------------------------------

if not API_KEY:
    st.error(
        "Token football-data.org non configurato. "
        "Inserisci FOOTBALL_DATA_TOKEN nelle Secrets "
        "di Streamlit Cloud."
    )
    st.stop()


# --------------------------------------------------
# CARICAMENTO CALENDARIO
# --------------------------------------------------

try:
    with st.spinner("Caricamento calendario..."):
        fixtures = load_fixtures(
            API_KEY,
            API_BASE_URL,
            max_matches
        )

    cutoff_dt = (
        datetime.now(timezone.utc)
        + timedelta(days=days)
    )

    fixtures = [
        f for f in fixtures
        if f.get("date")
        and parse_date(f["date"]) <= cutoff_dt
    ]

except Exception as exc:
    st.error(
        f"Errore durante il caricamento del calendario: {exc}"
    )
    st.stop()


if not fixtures:
    st.info(
        "Nessuna partita disponibile nell'intervallo selezionato."
    )
    st.stop()


# --------------------------------------------------
# PREPARAZIONE DATI
# --------------------------------------------------

rows = []

for fixture in fixtures:

    if not fixture.get("date"):
        continue

    dt = parse_date(
        fixture["date"]
    ).astimezone(
        ZoneInfo("Europe/Rome")
    )

    rows.append({
        "Data": dt.strftime("%d/%m %H:%M"),
        "Data_filtro": dt.strftime("%Y-%m-%d"),
        "Competizione": (
            f"{fixture.get('league', 'N/D')} · "
            f"{fixture.get('country', 'N/D')}"
        ),
        "Casa": fixture.get("home", "N/D"),
        "Trasferta": fixture.get("away", "N/D"),
        "_fixture": fixture
    })


if not rows:
    st.info("Non ci sono partite visualizzabili.")
    st.stop()


# --------------------------------------------------
# FILTRI DATA E CAMPIONATO
# --------------------------------------------------

st.subheader("Partite in programma")

st.caption(
    "Filtra il calendario per giornata e campionato, "
    "poi tocca una partita per visualizzare il pronostico."
)

filter_col1, filter_col2 = st.columns(2)

date_options = sorted(
    set(row["Data_filtro"] for row in rows)
)

league_options = sorted(
    set(row["Competizione"] for row in rows)
)

with filter_col1:
    selected_date = st.selectbox(
        "📅 Data",
        options=["Tutte le date"] + date_options,
        format_func=lambda value: (
            "Tutte le date"
            if value == "Tutte le date"
            else datetime.strptime(
                value, "%Y-%m-%d"
            ).strftime("%d/%m/%Y")
        ),
        key="date_filter"
    )

with filter_col2:
    selected_league = st.selectbox(
        "🏆 Campionato",
        options=["Tutti i campionati"] + league_options,
        key="league_filter"
    )


# --------------------------------------------------
# APPLICAZIONE FILTRI
# --------------------------------------------------

filtered_rows = rows.copy()

if selected_date != "Tutte le date":
    filtered_rows = [
        row for row in filtered_rows
        if row["Data_filtro"] == selected_date
    ]

if selected_league != "Tutti i campionati":
    filtered_rows = [
        row for row in filtered_rows
        if row["Competizione"] == selected_league
    ]


st.caption(
    f"Partite trovate: {len(filtered_rows)}"
)


if not filtered_rows:
    st.warning(
        "Nessuna partita corrisponde ai filtri selezionati. "
        "Prova a modificare data o campionato."
    )
    st.stop()


# --------------------------------------------------
# TABELLA INTERATTIVA
# --------------------------------------------------

fixtures_df = pd.DataFrame([
    {
        "Data": row["Data"],
        "Competizione": row["Competizione"],
        "Casa": row["Casa"],
        "Trasferta": row["Trasferta"]
    }
    for row in filtered_rows
])

# La chiave cambia con i filtri, così una vecchia
# selezione non viene associata a una partita diversa.
table_key = (
    f"fixture_table_{selected_date}_{selected_league}"
)

selection = st.dataframe(
    fixtures_df,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key=table_key
)


# --------------------------------------------------
# RECUPERO PARTITA SELEZIONATA
# --------------------------------------------------

selected_rows = selection.selection.rows

if not selected_rows:
    st.info(
        "Seleziona una partita dalla tabella "
        "per elaborare il pronostico."
    )
    st.stop()


selected_index = selected_rows[0]
match = filtered_rows[selected_index]["_fixture"]


# --------------------------------------------------
# ANALISI PARTITA
# --------------------------------------------------

st.divider()

st.subheader(
    f"{match['home']} – {match['away']}"
)

required_fields = [
    match.get("home_id"),
    match.get("away_id"),
    match.get("league_id"),
    match.get("season"),
    match.get("date")
]

if not all(required_fields):
    st.warning(
        "Dati insufficienti per analizzare questa partita. "
        "Mancano identificativi delle squadre, competizione, "
        "stagione o data."
    )
    st.stop()


try:
    cutoff = parse_date(
        match["date"]
    ).date().isoformat()

    with st.spinner(
        "Analisi rendimento stagionale e ultime 10 partite..."
    ):

        home_profile = load_team_profile(
            API_KEY,
            API_BASE_URL,
            match["home_id"],
            match["league_id"],
            match["season"],
            cutoff
        )

        away_profile = load_team_profile(
            API_KEY,
            API_BASE_URL,
            match["away_id"],
            match["league_id"],
            match["season"],
            cutoff
        )

    if not home_profile or not away_profile:
        st.warning(
            "Statistiche insufficienti per elaborare "
            "un pronostico attendibile."
        )
        st.stop()

    pred = predict_from_profiles(
        home_profile,
        away_profile
    )

    if not pred:
        st.warning(
            "Il modello non ha prodotto una previsione."
        )
        st.stop()

    st.caption(
        f"Partite recenti considerate: "
        f"{home_profile.get('recent_matches', 0)} "
        f"{match['home']} · "
        f"{away_profile.get('recent_matches', 0)} "
        f"{match['away']}."
    )

except Exception as exc:
    st.error(
        f"Impossibile elaborare la previsione: {exc}"
    )

    st.info(
        "Nessun pronostico è stato generato. "
        "Verifica disponibilità dei dati e copertura "
        "della competizione nel tuo piano API."
    )
    st.stop()


# --------------------------------------------------
# RISULTATI MODELLO
# --------------------------------------------------

st.markdown("### Previsione della partita")

c1, c2, c3 = st.columns(3)

c1.metric(
    "xG casa",
    f"{pred['lambda_home']:.2f}"
)

c2.metric(
    "xG trasferta",
    f"{pred['lambda_away']:.2f}"
)

c3.metric(
    "Risultato esatto modale",
    pred["most_likely_score"]
)


# --------------------------------------------------
# PROBABILITÀ 1X2
# --------------------------------------------------

st.markdown("#### Probabilità 1X2")

cols = st.columns(3)

for col, label, value in zip(
    cols,
    ["1 · Casa", "X · Pareggio", "2 · Trasferta"],
    [
        pred["home_win"],
        pred["draw"],
        pred["away_win"]
    ]
):
    col.metric(
        label,
        f"{value:.1%}"
    )


# --------------------------------------------------
# MERCATI GOAL
# --------------------------------------------------

st.markdown("#### Mercati gol")

cols = st.columns(3)

cols[0].metric(
    "Over 2.5",
    f"{pred['over_25']:.1%}"
)

cols[1].metric(
    "Under 2.5",
    f"{pred['under_25']:.1%}"
)

cols[2].metric(
    "Goal",
    f"{pred['btts']:.1%}"
)


# --------------------------------------------------
# RISULTATI ESATTI
# --------------------------------------------------

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
        {
            "Risultato": score,
            "Probabilità": f"{prob:.2%}"
        }
        for score, prob in top
    ]),
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# SALVATAGGIO PREVISIONE
# --------------------------------------------------

if st.button(
    "Salva questa previsione nello storico"
):
    try:
        save_prediction(
            match,
            pred
        )

        st.success(
            "Previsione archiviata nello storico."
        )

    except Exception as exc:
        st.error(
            f"Errore durante il salvataggio: {exc}"
        )


st.caption(
    "Modello Poisson indipendente. "
    "Le stime sono probabilistiche e non costituiscono "
    "garanzie o consigli di scommessa."
)
