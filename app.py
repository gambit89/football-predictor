import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import unicodedata

from football_predictor.provider import APIFootballProvider
from football_predictor.model import predict_from_profiles, build_team_profile
from football_predictor.storage import save_prediction
from football_predictor.config import API_KEY, API_BASE_URL

ROME = ZoneInfo("Europe/Rome")
ACTIVE_STATUSES = {"NS", "TBD", "LIVE", "1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT"}
PRIMARY_COMPETITIONS = {
    "italy": {"serie a", "serie b"},
    "england": {"premier league", "championship"},
    "spain": {"la liga", "segunda division"},
    "france": {"ligue 1", "ligue 2"},
    "germany": {"bundesliga", "2 bundesliga"},
    "netherlands": {"eredivisie", "eerste divisie"},
    "belgium": {"jupiler pro league", "challenger pro league"},
    "portugal": {"primeira liga", "liga portugal", "liga portugal 2", "segunda liga"},
    "ireland": {"premier division", "first division"},
    "scotland": {"premiership", "championship"},
    "poland": {"ekstraklasa", "i liga"},
    "romania": {"liga i", "liga ii", "liga 1", "liga 2", "superliga"},
    "bulgaria": {"first league", "second league", "first professional league", "second professional league", "parva liga", "vtora liga"},
    "argentina": {"liga profesional argentina", "liga profesional", "primera nacional"},
    "brazil": {"serie a", "serie b"},
    "usa": {"major league soccer", "usl championship"},
    "turkey": {"super lig", "1 lig"},
    "greece": {"super league 1", "super league 2", "super league"},
    "austria": {"bundesliga", "2 liga"},
    "switzerland": {"super league", "challenge league"},
    "denmark": {"superliga", "1 division"},
    "norway": {"eliteserien", "1 division"},
    "sweden": {"allsvenskan", "superettan"},
    "czech republic": {"czech liga", "fnl"},
    "japan": {"j1 league", "j2 league"},
    "mexico": {"liga mx", "liga de expansion mx"},
    "colombia": {"primera a", "primera b"},
    "chile": {"primera division", "primera b"},
    "uruguay": {"primera division", "segunda division"},
    "ecuador": {"liga pro", "liga pro serie b"},
    "paraguay": {"primera division", "division intermedia"},
    "peru": {"primera division", "liga 2"},
    "south korea": {"k league 1", "k league 2"},
    "saudi arabia": {"pro league", "division 1"},
    "south africa": {"premier soccer league", "national first division"},
    "morocco": {"botola pro", "botola 2"},
}
COUNTRY_ALIASES = {
    "republic of ireland": "ireland",
    "united states": "usa",
    "united states of america": "usa",
    "czechia": "czech republic",
    "korea republic": "south korea",
    "korea republic (south korea)": "south korea",
    "usa": "usa",
}

st.set_page_config(page_title="Football Predictor", page_icon="⚽", layout="wide")
st.title("⚽ Football Predictor")
st.caption("Previsioni pre-partita · gol fatti/subiti · sede · stagione 70% + ultime 5 gare 30% · Poisson")


def parse_date(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def normalize_label(value):
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(ch for ch in decomposed if not unicodedata.combining(ch)).split())


def is_primary_competition(fixture):
    country = normalize_label(fixture.get("country"))
    country = COUNTRY_ALIASES.get(country, country)
    league = normalize_label(fixture.get("league"))
    if any(tag in league for tag in ("women", "woman", "femminile", "feminine", "u19", "u21", "youth", "reserve", "primavera")):
        return False
    competition_names = PRIMARY_COMPETITIONS.get(country, set())
    return any(
        league == name or league.startswith(name + " ")
        for name in competition_names
    )


@st.cache_data(ttl=1800, show_spinner=False)
def load_fixtures(key, base, count):
    # Read a one-day buffer to handle the UTC/Italy date boundary; filter below to Italy's today.
    return APIFootballProvider(key, base).get_next_fixtures(count, 1)


@st.cache_data(ttl=86400, show_spinner=False)
def load_team_profile(key, base, team_id, league_id, season, cutoff):
    provider = APIFootballProvider(key, base)
    stats = provider.get_team_season_stats(team_id, league_id, season, cutoff)
    recent = provider.get_last_fixtures(team_id, 5, cutoff, season=season, league_id=league_id)
    return build_team_profile(team_id, stats, recent)


with st.sidebar:
    st.header("Calendario")
    st.caption("Solo le partite di oggi non ancora concluse")
    max_matches = st.slider("Partite da caricare", 10, 500, 200, 10)
    if st.button("Aggiorna calendario"):
        st.cache_data.clear()
        st.rerun()

if not API_KEY:
    st.error("Chiave API-Football non configurata. Inserisci API_FOOTBALL_KEY nelle Secrets di Streamlit Cloud.")
    st.stop()

try:
    with st.spinner("Caricamento delle partite di oggi..."):
        fixtures = load_fixtures(API_KEY, API_BASE_URL, max_matches)
    today = datetime.now(ROME).date()
    fixtures = [
        match for match in fixtures
        if match.get("date")
        and parse_date(match["date"]).astimezone(ROME).date() == today
        and (match.get("status") or {}).upper() in ACTIVE_STATUSES
    ]
except Exception as exc:
    st.error(f"Errore durante il caricamento del calendario: {exc}")
    st.stop()

rows = []
for fixture in fixtures:
    dt = parse_date(fixture["date"]).astimezone(ROME)
    rows.append({
        "Data": dt.strftime("%H:%M"),
        "Competizione": f"{fixture.get('league', 'N/D')} · {fixture.get('country', 'N/D')}",
        "Casa": fixture.get("home", "N/D"),
        "Trasferta": fixture.get("away", "N/D"),
        "_fixture": fixture,
    })

if not rows:
    st.info("Oggi non ci sono partite ancora da disputare o attualmente in corso.")
    st.stop()

st.subheader(f"Partite di oggi · {datetime.now(ROME).strftime('%d/%m/%Y')}")
primary_rows = [row for row in rows if is_primary_competition(row["_fixture"])]
secondary_rows = [row for row in rows if not is_primary_competition(row["_fixture"])]
st.caption(f"Totale gare: {len(rows)} · principali: {len(primary_rows)} · secondarie: {len(secondary_rows)}")


def render_fixture_module(module_key, title, module_rows):
    st.markdown(f"### {title}")
    if not module_rows:
        st.info("Nessuna partita disponibile oggi in questo gruppo.")
        return
    selection_key = f"fixture_table_{datetime.now(ROME).date()}_{module_key}"
    selection = st.dataframe(
        pd.DataFrame([
            {key: row[key] for key in ("Data", "Competizione", "Casa", "Trasferta")}
            for row in module_rows
        ]),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=selection_key,
    )
    selected_rows = list(selection.selection.rows)
    previous_key = f"previous_selection_{module_key}"
    previous_rows = st.session_state.get(previous_key, [])
    if selected_rows != previous_rows:
        st.session_state[previous_key] = selected_rows
        st.session_state["selected_fixture"] = (
            module_rows[selected_rows[0]]["_fixture"] if selected_rows else None
        )


render_fixture_module("primary", "🏆 Campionati principali", primary_rows)
render_fixture_module("secondary", "🌍 Campionati secondari", secondary_rows)

match = st.session_state.get("selected_fixture")
if not match:
    st.info("Seleziona una partita dalla tabella per elaborare il pronostico.")
    st.stop()

if not all(match.get(key) for key in ("home_id", "away_id", "league_id", "season", "date")):
    st.warning("Dati insufficienti: mancano identificativi delle squadre, competizione, stagione o data.")
    st.stop()

st.divider()
st.subheader(f"{match['home']} – {match['away']}")
cutoff = parse_date(match["date"]).date().isoformat()
try:
    with st.spinner("Analisi rendimento stagionale e ultime 5 partite..."):
        home = load_team_profile(API_KEY, API_BASE_URL, match["home_id"], match["league_id"], match["season"], cutoff)
        away = load_team_profile(API_KEY, API_BASE_URL, match["away_id"], match["league_id"], match["season"], cutoff)
    if not home or not away:
        st.warning("Statistiche insufficienti per elaborare il pronostico.")
        st.stop()
    pred = predict_from_profiles(home, away)
except Exception as exc:
    st.error(f"Impossibile elaborare la previsione: {exc}")
    st.info("Verifica disponibilità dei dati e copertura della competizione nel piano API.")
    st.stop()

st.caption(f"Campione recente: {home['recent_matches']} gare per {match['home']} · {away['recent_matches']} per {match['away']}. Mercati calcolati sulla matrice Poisson.")
col1, col2, col3 = st.columns(3)
col1.metric("λ gol casa", f"{pred['lambda_home']:.2f}")
col2.metric("λ gol trasferta", f"{pred['lambda_away']:.2f}")
col3.metric("Risultato modale", pred["most_likely_score"])


def style_probability_rows(frame, threshold=None):
    best_probability = frame["Probabilità"].max()

    def highlight_value(row):
        probability = row["Probabilità"]
        should_highlight = probability > threshold if threshold is not None else probability == best_probability
        styles = [""] * len(row)
        if should_highlight:
            styles[row.index.get_loc("Probabilità")] = "background-color: #176B3A; color: white; font-weight: bold"
        return styles

    return frame.style.apply(highlight_value, axis=1)


st.markdown("#### Probabilità 1X2")
one_x_two = pd.DataFrame({
    "Esito": ["1 · Vittoria casa", "X · Pareggio", "2 · Vittoria trasferta"],
    "Probabilità": [pred["home_win"], pred["draw"], pred["away_win"]],
})
st.dataframe(style_probability_rows(one_x_two).format({"Probabilità": "{:.1%}"}), use_container_width=True, hide_index=True)


def style_market_pair(frame):
    highest_probability = frame["Probabilità"].max()

    def highlight_highest(row):
        style = "background-color: #176B3A; color: white; font-weight: bold" if row["Probabilità"] == highest_probability else "font-weight: bold"
        return [style] * len(row)

    return frame.style.apply(highlight_highest, axis=1).format({"Probabilità": "{:.1%}"})


for threshold in ("15", "25", "35"):
    label = f"{threshold[0]}.{threshold[1]}"
    pair = pd.DataFrame([
        {"Mercato": f"Over {label} gol", "Probabilità": pred[f"over_{threshold}"]},
        {"Mercato": f"Under {label} gol", "Probabilità": pred[f"under_{threshold}"]},
    ])
    st.markdown(f"##### Over / Under {label} gol")
    st.dataframe(style_market_pair(pair), use_container_width=True, hide_index=True)

st.markdown("#### BTTS")
btts_markets = pd.DataFrame({
    "Mercato": ["Goal (entrambe segnano)", "No Goal"],
    "Probabilità": [pred["btts"], pred["no_btts"]],
})
st.dataframe(style_probability_rows(btts_markets).format({"Probabilità": "{:.1%}"}), use_container_width=True, hide_index=True)

st.markdown("#### Top 10 risultati esatti")
exact_scores = pd.DataFrame([
    {"Risultato": score, "Probabilità": probability}
    for score, probability in pred["top_scores"]
])
st.dataframe(style_probability_rows(exact_scores, threshold=0.10).format({"Probabilità": "{:.2%}"}), use_container_width=True, hide_index=True)
st.caption("In verde i risultati esatti con probabilità superiore al 10%.")

if st.button("Salva questa previsione nello storico"):
    try:
        save_prediction(match, pred)
        st.success("Previsione archiviata nello storico.")
    except Exception as exc:
        st.error(f"Errore durante il salvataggio: {exc}")

st.caption("Modello Poisson indipendente basato esclusivamente sui gol fatti/subiti e sulla sede. Le probabilità sono stime e non garantiscono risultati.")
