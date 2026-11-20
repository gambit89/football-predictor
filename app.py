import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from football_predictor.provider import APIFootballProvider
from football_predictor.model import predict_from_profiles, build_team_profile
from football_predictor.storage import save_prediction
from football_predictor.config import API_KEY, API_BASE_URL

st.set_page_config(page_title="Football Predictor", page_icon="⚽", layout="wide")
st.title("⚽ Football Predictor")
st.caption("Previsioni pre-partita · gol fatti/subiti · sede · stagione 70% + ultime 5 gare 30% · Poisson")


def parse_date(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@st.cache_data(ttl=1800, show_spinner=False)
def load_fixtures(key, base, count, days):
    return APIFootballProvider(key, base).get_next_fixtures(count, days)


@st.cache_data(ttl=86400, show_spinner=False)
def load_team_profile(key, base, team_id, league_id, season, cutoff):
    provider = APIFootballProvider(key, base)
    stats = provider.get_team_season_stats(team_id, league_id, season, cutoff)
    recent = provider.get_last_fixtures(team_id, 5, cutoff, season=season, league_id=league_id)
    return build_team_profile(team_id, stats, recent)


with st.sidebar:
    st.header("Calendario")
    days = st.slider("Giorni da visualizzare", 1, 30, 14)
    max_matches = st.slider("Partite da caricare", 10, 500, 200, 10)
    if st.button("Aggiorna calendario"):
        st.cache_data.clear()
        st.rerun()

if not API_KEY:
    st.error("Token football-data.org non configurato. Inserisci FOOTBALL_DATA_TOKEN nelle Secrets di Streamlit Cloud.")
    st.stop()

try:
    with st.spinner("Caricamento calendario..."):
        fixtures = load_fixtures(API_KEY, API_BASE_URL, max_matches, days)
    cutoff_dt = datetime.now(timezone.utc) + timedelta(days=days)
    fixtures = [f for f in fixtures if f.get("date") and parse_date(f["date"]) <= cutoff_dt]
except Exception as exc:
    st.error(f"Errore durante il caricamento del calendario: {exc}")
    st.stop()

rows = []
for fixture in fixtures:
    if not fixture.get("date"):
        continue
    dt = parse_date(fixture["date"]).astimezone(ZoneInfo("Europe/Rome"))
    rows.append({
        "Data": dt.strftime("%d/%m %H:%M"),
        "Data filtro": dt.strftime("%Y-%m-%d"),
        "Competizione": f"{fixture.get('league', 'N/D')} · {fixture.get('country', 'N/D')}",
        "Casa": fixture.get("home", "N/D"),
        "Trasferta": fixture.get("away", "N/D"),
        "_fixture": fixture,
    })

if not rows:
    st.info("Nessuna partita disponibile nell'intervallo selezionato.")
    st.stop()

st.subheader("Partite in programma")
date_values = sorted({row["Data filtro"] for row in rows})
league_values = sorted({row["Competizione"] for row in rows})
col1, col2 = st.columns(2)
with col1:
    selected_date = st.selectbox("📅 Data", ["Tutte le date"] + date_values, format_func=lambda value: value if value == "Tutte le date" else datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y"))
with col2:
    selected_league = st.selectbox("🏆 Campionato", ["Tutti i campionati"] + league_values)
filtered = [row for row in rows if (selected_date == "Tutte le date" or row["Data filtro"] == selected_date) and (selected_league == "Tutti i campionati" or row["Competizione"] == selected_league)]
st.caption(f"Partite trovate: {len(filtered)}")
if not filtered:
    st.info("Nessuna partita corrisponde ai filtri selezionati.")
    st.stop()

selection = st.dataframe(
    pd.DataFrame([{k: row[k] for k in ("Data", "Competizione", "Casa", "Trasferta")} for row in filtered]),
    use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row",
    key=f"fixture_table_{selected_date}_{selected_league}",
)
if not selection.selection.rows:
    st.info("Seleziona una partita dalla tabella per elaborare il pronostico.")
    st.stop()

match = filtered[selection.selection.rows[0]]["_fixture"]
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

st.markdown("#### Probabilità 1X2")
st.dataframe(pd.DataFrame({
    "Esito": ["1 · Vittoria casa", "X · Pareggio", "2 · Vittoria trasferta"],
    "Probabilità": [pred["home_win"], pred["draw"], pred["away_win"]],
}).style.format({"Probabilità": "{:.1%}"}), use_container_width=True, hide_index=True)

def style_market_pair(frame):
    highest_probability = frame["Probabilità"].max()

    def highlight_highest(row):
        style = (
            "background-color: #176B3A; color: white; font-weight: bold"
            if row["Probabilità"] == highest_probability
            else "font-weight: bold"
        )
        return [style] * len(row)

    return frame.style.apply(highlight_highest, axis=1).format(
        {"Probabilità": "{:.1%}"}
    )


for threshold in ("15", "25", "35"):
    label = f"{threshold[0]}.{threshold[1]}"
    pair = pd.DataFrame([
        {"Mercato": f"Over {label} gol", "Probabilità": pred[f"over_{threshold}"]},
        {"Mercato": f"Under {label} gol", "Probabilità": pred[f"under_{threshold}"]},
    ])
    st.markdown(f"##### Over / Under {label} gol")
    st.dataframe(style_market_pair(pair), use_container_width=True, hide_index=True)

st.markdown("#### BTTS")
st.dataframe(pd.DataFrame({
    "Mercato": ["Goal (entrambe segnano)", "No Goal"],
    "Probabilità": [pred["btts"], pred["no_btts"]],
}).style.format({"Probabilità": "{:.1%}"}), use_container_width=True, hide_index=True)

st.markdown("#### Top 10 risultati esatti")
st.dataframe(pd.DataFrame([
    {"Risultato": score, "Probabilità": probability}
    for score, probability in pred["top_scores"]
]).style.format({"Probabilità": "{:.2%}"}), use_container_width=True, hide_index=True)

if st.button("Salva questa previsione nello storico"):
    try:
        save_prediction(match, pred)
        st.success("Previsione archiviata nello storico.")
    except Exception as exc:
        st.error(f"Errore durante il salvataggio: {exc}")

st.caption("Modello Poisson indipendente basato esclusivamente sui gol fatti/subiti e sulla sede. Le probabilità sono stime e non garantiscono risultati.")



