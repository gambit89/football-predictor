import pandas as pd
import streamlit as st
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import unicodedata
from football_predictor.provider import APIFootballProvider
from football_predictor.model import predict_from_profiles, build_team_profile
from football_predictor.storage import save_prediction
from football_predictor.config import API_KEY, API_BASE_URL

ROME = ZoneInfo("Europe/Rome")
ACTIVE_STATUSES = {"NS", "TBD", "LIVE", "1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT"}
PRIMARY_LEAGUES = {
    "Italia": {"Serie A": 135, "Serie B": 136},
    "Inghilterra": {"Premier League": 39, "Championship": 40},
    "Spagna": {"La Liga": 140, "Segunda División": 141},
    "Francia": {"Ligue 1": 61, "Ligue 2": 62},
    "Germania": {"Bundesliga": 78, "2. Bundesliga": 79},
    "Olanda": {"Eredivisie": 88, "Eerste Divisie": 89},
    "Belgio": {"Jupiler Pro League": 144, "Challenger Pro League": 145},
    "Portogallo": {"Primeira Liga": 94, "Liga Portugal 2": 95},
    "Irlanda": {"Premier Division": 357, "First Division": 358},
    "Scozia": {"Premiership": 179, "Championship": 180},
    "Polonia": {"Ekstraklasa": 106, "I Liga": 107},
    "Romania": {"Liga I": 283, "Liga II": 284},
    "Bulgaria": {"First League": 172, "Second League": 173},
    "Argentina": {"Liga Profesional": 128, "Primera Nacional": 129},
    "Brasile": {"Serie A": 71, "Serie B": 72},
    "USA": {"Major League Soccer": 253, "USL Championship": 255},
    "Turchia": {"Süper Lig": 203, "1. Lig": 204},
    "Grecia": {"Super League 1": 197, "Super League 2": 494},
    "Austria": {"Bundesliga": 218, "2. Liga": 219},
    "Svizzera": {"Super League": 207, "Challenge League": 208},
    "Danimarca": {"Superliga": 119, "1st Division": 120},
    "Norvegia": {"Eliteserien": 103, "1. Division": 104},
    "Svezia": {"Allsvenskan": 113, "Superettan": 114},
    "Repubblica Ceca": {"Czech Liga": 345, "FNL": 346},
    "Giappone": {"J1 League": 98, "J2 League": 99},
    "Messico": {"Liga MX": 262, "Liga de Expansión MX": 263},
    "Colombia": {"Primera A": 239, "Primera B": 240},
    "Cile": {"Primera División": 265, "Primera B": 266},
    "Uruguay": {"Primera División": 268, "Segunda División": 269},
    "Ecuador": {"Liga Pro": 242, "Liga Pro Serie B": 243},
    "Paraguay": {"Primera División": 250, "División Intermedia": 252},
    "Perù": {"Primera División": 281, "Liga 2": 282},
    "Corea del Sud": {"K League 1": 292, "K League 2": 293},
    "Arabia Saudita": {"Pro League": 307, "Division 1": 308},
    "Sudafrica": {"Premier Soccer League": 288, "National First Division": 289},
    "Marocco": {"Botola Pro": 200, "Botola 2": 201},
}
LEAGUE_NAME_BY_ID = {
    league_id: f"{country} · {name}"
    for country, leagues in PRIMARY_LEAGUES.items()
    for name, league_id in leagues.items()
}
DYNAMIC_COMPETITIONS = {
    "Armenia": {"Premier League", "First League"},
    "Australia": {"A-League", "Australian Championship"},
    "Algeria": {"Ligue 1", "Ligue 2"},
    "Tunisia": {"Ligue 1", "Ligue 2"},
    "India": {"Indian Super League", "I-League"},
    "Indonesia": {"Liga 1", "Liga 2"},
    "England": {"League One", "League Two"},
    "Italy": {"Serie C - Girone A", "Serie C - Girone B", "Serie C - Girone C"},
}

st.set_page_config(page_title="Football Predictor", page_icon="⚽", layout="wide")
st.title("⚽ Football Predictor")
st.caption("Previsioni pre-partita · gol fatti/subiti · sede · stagione 70% + ultime 5 gare 30% · Poisson")

# Soglie operative esplorative concordate per la selezione dei pronostici.
MARKET_THRESHOLDS = {
    "1X2": 0.55,
    "over_under_25": 0.60,
    "over_under_15": 0.65,
    "over_under_35": 0.65,
    "btts": 0.60,
    "double_chance": 0.70,
}


def parse_date(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def normalize_label(value):
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(ch for ch in decomposed if not unicodedata.combining(ch)).split())


@st.cache_data(ttl=1800, show_spinner=False)
def load_fixtures(key, base, match_date, league_ids, count):
    return APIFootballProvider(key, base).get_fixtures_for_date(match_date, league_ids, count)


@st.cache_data(ttl=86400, show_spinner=False)
def load_dynamic_leagues(key, base, season):
    catalog = APIFootballProvider(key, base).get_leagues_for_season(season)
    matches = []
    for item in catalog:
        league = item.get("league") or {}
        country = (item.get("country") or {}).get("name")
        name = league.get("name")
        if not country or not name or country not in DYNAMIC_COMPETITIONS:
            continue
        allowed_names = {normalize_label(value) for value in DYNAMIC_COMPETITIONS[country]}
        if normalize_label(name) in allowed_names:
            matches.append((int(league["id"]), f"{country} · {name}"))
    return tuple(sorted(set(matches), key=lambda entry: entry[1]))


@st.cache_data(ttl=86400, show_spinner=False)
def load_team_profile(key, base, team_id, league_id, season, cutoff):
    provider = APIFootballProvider(key, base)
    stats = provider.get_team_season_stats(team_id, league_id, season, cutoff)
    recent = provider.get_last_fixtures(team_id, 5, cutoff, season=season, league_id=league_id)
    return build_team_profile(team_id, stats, recent)


with st.sidebar:
    st.header("Calendario")
    today = datetime.now(ROME).date()
    calendar_days = [today + timedelta(days=offset) for offset in range(8)]
    selected_day = st.selectbox("Giornata", calendar_days, format_func=lambda day: day.strftime("%A %d/%m/%Y"))
    st.caption("Da oggi ai prossimi 7 giorni.")
    max_matches = st.slider("Partite da caricare", 10, 500, 200, 10)
    if st.button("Aggiorna calendario"):
        st.cache_data.clear()
        st.rerun()

if not API_KEY:
    st.error("Chiave API-Football non configurata. Inserisci API_FOOTBALL_KEY nelle Secrets di Streamlit Cloud.")
    st.stop()

dynamic_leagues = ()
try:
    with st.spinner("Aggiornamento campionati richiesti..."):
        dynamic_leagues = load_dynamic_leagues(API_KEY, API_BASE_URL, selected_day.year)
except Exception as exc:
    st.warning(f"Elenco aggiornato dei campionati aggiuntivi non disponibile: {exc}")

for league_id, label in dynamic_leagues:
    LEAGUE_NAME_BY_ID[league_id] = label
all_league_ids = [league_id for leagues in PRIMARY_LEAGUES.values() for league_id in leagues.values()]
all_league_ids.extend(league_id for league_id, _ in dynamic_leagues)
all_league_ids = sorted(set(all_league_ids))
with st.sidebar:
    selected_leagues = st.multiselect(
        "Campionati da analizzare", options=all_league_ids, default=all_league_ids,
        format_func=lambda league_id: LEAGUE_NAME_BY_ID[league_id], key="selected_competitions_v2",
    )
    st.caption("Riduci la selezione per diminuire il numero di chiamate al provider.")

selection_context = (selected_day.isoformat(), tuple(sorted(selected_leagues)))
if st.session_state.get("fixture_context") != selection_context:
    st.session_state["fixture_context"] = selection_context
    st.session_state["selected_fixture"] = None

if not selected_leagues:
    st.info("Seleziona almeno un campionato per caricare il calendario.")
    st.stop()

try:
    date_string = selected_day.isoformat()
    with st.spinner(f"Caricamento delle partite del {selected_day:%d/%m/%Y}..."):
        fixtures = load_fixtures(API_KEY, API_BASE_URL, date_string, tuple(sorted(selected_leagues)), max_matches)
    today = datetime.now(ROME).date()
    allowed_statuses = ACTIVE_STATUSES if selected_day == today else {"NS", "TBD"}
    fixtures = [
        match for match in fixtures
        if match.get("date")
        and parse_date(match["date"]).astimezone(ROME).date() == selected_day
        and (match.get("status") or "").upper() in allowed_statuses
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
    st.info("Nessuna partita da disputare o in corso nella data selezionata e nei campionati scelti.")
    st.stop()

st.subheader(f"Partite del giorno: {len(rows)}")
st.caption(f"Data selezionata: {selected_day.strftime('%d/%m/%Y')} · campionati selezionati: {len(selected_leagues)}")


def render_fixture_module(module_key, title, module_rows):
    st.markdown(f"### {title}")
    if not module_rows:
        st.info("Nessuna partita disponibile nella data selezionata.")
        return
    selection_key = f"fixture_table_{selected_day}_{tuple(sorted(selected_leagues))}_{module_key}"
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
    previous_key = f"previous_selection_{selected_day}_{tuple(sorted(selected_leagues))}_{module_key}"
    previous_rows = st.session_state.get(previous_key, [])
    if selected_rows != previous_rows:
        st.session_state[previous_key] = selected_rows
        st.session_state["selected_fixture"] = (
            module_rows[selected_rows[0]]["_fixture"] if selected_rows else None
        )


render_fixture_module("primary", "Partite dei campionati selezionati", rows)

match = st.session_state.get("selected_fixture")
if not match:
    st.info("Seleziona una partita dalla tabella per elaborare il pronostico.")
    st.stop()

if not all(match.get(key) for key in ("home_id", "away_id", "league_id", "season", "date")):
    st.warning("Dati insufficienti: mancano identificativi delle squadre, competizione, stagione o data.")
    st.stop()

st.divider()
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


def qualified_signals(prediction):
    candidates = [
        ("1X2", "1", prediction["home_win"], MARKET_THRESHOLDS["1X2"]),
        ("1X2", "X", prediction["draw"], MARKET_THRESHOLDS["1X2"]),
        ("1X2", "2", prediction["away_win"], MARKET_THRESHOLDS["1X2"]),
        ("U/O 1,5", "Over", prediction["over_15"], MARKET_THRESHOLDS["over_under_15"]),
        ("U/O 1,5", "Under", prediction["under_15"], MARKET_THRESHOLDS["over_under_15"]),
        ("U/O 2,5", "Over", prediction["over_25"], MARKET_THRESHOLDS["over_under_25"]),
        ("U/O 2,5", "Under", prediction["under_25"], MARKET_THRESHOLDS["over_under_25"]),
        ("U/O 3,5", "Over", prediction["over_35"], MARKET_THRESHOLDS["over_under_35"]),
        ("U/O 3,5", "Under", prediction["under_35"], MARKET_THRESHOLDS["over_under_35"]),
        ("Gol/No Gol", "Gol", prediction["btts"], MARKET_THRESHOLDS["btts"]),
        ("Gol/No Gol", "No Gol", prediction["no_btts"], MARKET_THRESHOLDS["btts"]),
        (
            "Doppia chance",
            "1X",
            prediction["home_win"] + prediction["draw"],
            MARKET_THRESHOLDS["double_chance"],
        ),
        (
            "Doppia chance",
            "X2",
            prediction["draw"] + prediction["away_win"],
            MARKET_THRESHOLDS["double_chance"],
        ),
    ]
    return [item for item in candidates if item[2] >= item[3]]


signals = qualified_signals(pred)
st.subheader(f"{match['home']} – {match['away']}")
if signals:
    signal_rows = []
    for market in dict.fromkeys(item[0] for item in signals):
        market_signals = [item for item in signals if item[0] == market]
        outcomes = "  ·  ".join(
            f"{outcome} ({probability:.1%})"
            for _, outcome, probability, _ in market_signals
        )
        signal_rows.append({
            "Mercato": market,
            "Esiti sopra soglia": outcomes,
            "Soglia minima": market_signals[0][3],
        })

    signal_table = pd.DataFrame(signal_rows)
    signal_style = (
        signal_table.style
        .format({"Soglia minima": "{:.0%}"})
        .set_properties(**{
            "font-weight": "bold",
            "padding": "0.7rem 0.9rem",
            "vertical-align": "middle",
        })
        .set_table_styles([{
            "selector": "th",
            "props": [
                ("font-weight", "bold"),
                ("padding", "0.7rem 0.9rem"),
                ("text-align", "left"),
            ],
        }])
    )
    st.markdown("**Esiti sopra soglia**")
    st.dataframe(
        signal_style,
        use_container_width=True,
        hide_index=True,
        height=min(120 + 52 * len(signal_rows), 432),
    )
else:
    st.info("Nessun esito raggiunge le soglie minime impostate per questa partita.")

st.caption(f"Campione recente: {home['recent_matches']} gare per {match['home']} · {away['recent_matches']} per {match['away']}. Mercati calcolati sulla matrice Poisson.")
col1, col2, col3 = st.columns(3)
col1.metric("λ gol casa", f"{pred['lambda_home']:.2f}")
col2.metric("λ gol trasferta", f"{pred['lambda_away']:.2f}")
col3.metric("Risultato modale", pred["most_likely_score"])


def style_threshold_rows(frame, threshold):
    def highlight_value(row):
        if row["Probabilità"] >= threshold:
            style = "background-color: #176B3A; color: white; font-weight: bold"
        else:
            style = "color: #888888"
        return [style] * len(row)

    return frame.style.apply(highlight_value, axis=1)


st.markdown("#### Probabilità 1X2")
one_x_two = pd.DataFrame({
    "Esito": ["1 · Vittoria casa", "X · Pareggio", "2 · Vittoria trasferta"],
    "Probabilità": [pred["home_win"], pred["draw"], pred["away_win"]],
})
st.dataframe(
    style_threshold_rows(one_x_two, MARKET_THRESHOLDS["1X2"]).format(
        {"Probabilità": "{:.1%}"}
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown("#### Doppia Chance")
double_chance = pd.DataFrame({
    "Esito": ["1X · Casa o pareggio", "X2 · Pareggio o trasferta"],
    "Probabilità": [
        pred["home_win"] + pred["draw"],
        pred["draw"] + pred["away_win"],
    ],
})
st.dataframe(
    style_threshold_rows(double_chance, MARKET_THRESHOLDS["double_chance"]).format(
        {"Probabilità": "{:.1%}"}
    ),
    use_container_width=True,
    hide_index=True,
)


for threshold in ("15", "25", "35"):
    label = f"{threshold[0]}.{threshold[1]}"
    threshold_key = f"over_under_{threshold}"
    pair = pd.DataFrame([
        {"Mercato": f"Over {label} gol", "Probabilità": pred[f"over_{threshold}"]},
        {"Mercato": f"Under {label} gol", "Probabilità": pred[f"under_{threshold}"]},
    ])
    st.markdown(f"##### Over / Under {label} gol")
    st.dataframe(
        style_threshold_rows(pair, MARKET_THRESHOLDS[threshold_key]).format(
            {"Probabilità": "{:.1%}"}
        ),
        use_container_width=True,
        hide_index=True,
    )

st.markdown("#### BTTS")
btts_markets = pd.DataFrame({
    "Mercato": ["Goal (entrambe segnano)", "No Goal"],
    "Probabilità": [pred["btts"], pred["no_btts"]],
})
st.dataframe(
    style_threshold_rows(btts_markets, MARKET_THRESHOLDS["btts"]).format(
        {"Probabilità": "{:.1%}"}
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown("#### Top 10 risultati esatti")
exact_scores = pd.DataFrame([
    {"Risultato": score, "Probabilità": probability}
    for score, probability in pred["top_scores"]
])
st.dataframe(exact_scores.style.format({"Probabilità": "{:.2%}"}), use_container_width=True, hide_index=True)
st.caption("I risultati esatti sono mostrati come dettaglio e non rientrano nei filtri soglia dei mercati.")
st.caption("Verde = esito e probabilità che raggiungono o superano la soglia impostata; grigio = sotto soglia.")

if st.button("Salva questa previsione nello storico"):
    try:
        save_prediction(match, pred)
        st.success("Previsione archiviata nello storico.")
    except Exception as exc:
        st.error(f"Errore durante il salvataggio: {exc}")

st.caption("Modello Poisson indipendente basato esclusivamente sui gol fatti/subiti e sulla sede. Le probabilità sono stime e non garantiscono risultati.")
