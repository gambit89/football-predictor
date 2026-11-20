import streamlit as st

from football_predictor.soccer_data_provider import (
    SoccerDataProvider
)

st.set_page_config(
    page_title="Soccer Data API Test",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Test Soccer Data Provider")
st.caption("Ambiente di verifica del nuovo provider API")

if "SOCCER_DATA_KEY" not in st.secrets:
    st.error("SOCCER_DATA_KEY non configurata nelle Secrets.")
    st.stop()

api_key = st.secrets["SOCCER_DATA_KEY"]

st.success("API Key configurata correttamente.")

if st.button("🔄 Recupera partite dei prossimi 14 giorni"):

    try:

        provider = SoccerDataProvider(api_key)

        with st.spinner("Interrogazione Soccer Data in corso..."):

            fixtures = provider.get_fixtures(
                days_ahead=14,
                per_page=100,
                max_matches=50
            )

        st.success(f"Partite recuperate: {len(fixtures)}")

        if fixtures:

            st.subheader("Calendario recuperato")

            for match in fixtures:

                st.markdown(
                    f"**{match.get('home', 'N/D')} "
                    f"vs {match.get('away', 'N/D')}**"
                )

                st.caption(
                    f"Data: {match.get('date')} | "
                    f"Competizione: {match.get('competition_id')} | "
                    f"Stato: {match.get('status')}"
                )

                st.divider()

            st.subheader("Verifica struttura dati")

            st.json(fixtures[0])

        else:

            st.warning(
                "La chiamata è riuscita, ma non sono state "
                "restituite partite."
            )

    except Exception as e:

        st.error(f"Errore durante il test: {e}")
