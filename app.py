
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
# SOGLIA RISULTATI ESATTI
# --------------------------------------------------

st.markdown("### Evidenza delle probabilità")

score_threshold = st.slider(
    "Soglia di evidenziazione risultati esatti",
    min_value=1,
    max_value=30,
    value=10,
    step=1,
    format="%d%%"
)

st.caption(
    "I risultati esatti che raggiungono o superano "
    "questa percentuale saranno evidenziati in verde."
)


# --------------------------------------------------
# PROBABILITÀ 1X2
# --------------------------------------------------

st.markdown("#### Probabilità 1X2")

one_x_two = pd.DataFrame({
    "Esito": [
        "1 · Vittoria casa",
        "X · Pareggio",
        "2 · Vittoria trasferta"
    ],
    "Probabilità": [
        pred["home_win"],
        pred["draw"],
        pred["away_win"]
    ]
})


def highlight_best(row):
    styles = [""] * len(row)

    probability_index = row.index.get_loc("Probabilità")

    if row["Probabilità"] == one_x_two["Probabilità"].max():
        styles[probability_index] = (
            "background-color: #176B3A; color: white; font-weight: bold"
        )

    return styles


def color_probability(value):
    if value >= 0.60:
        return "background-color: #176B3A; color: white; font-weight: bold"
    elif value >= 0.45:
        return "background-color: #80651B; color: white"
    else:
        return "background-color: #792D35; color: white"


st.dataframe(
    one_x_two.style
    .apply(highlight_best, axis=1)
    .format({"Probabilità": "{:.1%}"}),
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# MERCATI GOAL
# --------------------------------------------------

st.markdown("#### Mercati gol")

markets = pd.DataFrame({
    "Mercato": [
        "Over 2.5",
        "Under 2.5",
        "Goal (BTTS)"
    ],
    "Probabilità": [
        pred["over_25"],
        pred["under_25"],
        pred["btts"]
    ]
})


def highlight_goal_markets(row):
    styles = [""] * len(row)
    probability_index = row.index.get_loc("Probabilità")

    # Confronto diretto Over / Under
    if row["Mercato"] in ("Over 2.5", "Under 2.5"):
        if row["Probabilità"] == max(
            pred["over_25"],
            pred["under_25"]
        ):
            styles[probability_index] = (
                "background-color: #176B3A; color: white; font-weight: bold"
            )

    # Evidenzia Goal se raggiunge almeno il 55%
    elif row["Mercato"] == "Goal (BTTS)":
        if row["Probabilità"] >= 0.55:
            styles[probability_index] = (
                "background-color: #176B3A; color: white; font-weight: bold"
            )
        elif row["Probabilità"] >= 0.45:
            styles[probability_index] = (
                "background-color: #80651B; color: white"
            )
        else:
            styles[probability_index] = (
                "background-color: #792D35; color: white"
            )

    return styles


st.dataframe(
    markets.style
    .apply(highlight_goal_markets, axis=1)
    .format({"Probabilità": "{:.1%}"}),
    use_container_width=True,
    hide_index=True
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

exact_scores = pd.DataFrame([
    {
        "Risultato": score,
        "Probabilità": prob
    }
    for score, prob in top
])


def highlight_exact_scores(row):
    probability = row["Probabilità"]

    if probability >= score_threshold / 100:
        return [
            "background-color: #176B3A; color: white; font-weight: bold"
        ] * len(row)

    return [""] * len(row)


st.dataframe(
    exact_scores.style
    .apply(highlight_exact_scores, axis=1)
    .format({"Probabilità": "{:.2%}"}),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Verde: risultato esatto sopra la soglia selezionata. "
    "La probabilità si riferisce al modello Poisson."
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
    "Le probabilità non garantiscono risultati "
    "e non rappresentano da sole un'indicazione "
    "di convenienza economica."
)
