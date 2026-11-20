import streamlit as st
import pandas as pd

from football_predictor.soccer_data_provider import (
    SoccerDataProvider
)

st.set_page_config(
    page_title="Soccer Data Coverage",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Soccer Data – Analisi copertura")
st.caption("Verifica competizioni e stagioni disponibili")


if "SOCCER_DATA_KEY" not in st.secrets:
    st.error("SOCCER_DATA_KEY non configurata.")
    st.stop()

api_key = st.secrets["SOCCER_DATA_KEY"]

provider = SoccerDataProvider(api_key)

st.success("Connessione API configurata.")


if st.button("🔍 Recupera tutte le competizioni"):

    try:

        with st.spinner("Recupero competizioni..."):

            payload = provider._request("competitions")

        data = payload.get("data", [])

        st.success(
            f"Competizioni recuperate: {len(data)}"
        )

        if data:

            st.subheader("Elenco competizioni")

            df = pd.json_normalize(data)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            st.subheader("Analisi campi disponibili")

            st.write(
                "Campi restituiti dall'API:"
            )

            st.write(
                list(data[0].keys())
            )

            st.subheader("Risposta API originale")

            st.json(payload)

        else:

            st.warning(
                "Nessuna competizione restituita."
            )

    except Exception as e:

        st.error(
            f"Errore durante il recupero competizioni: {e}"
        )
