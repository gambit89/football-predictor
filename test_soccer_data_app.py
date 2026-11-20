
import streamlit as st
import pandas as pd

from football_predictor.soccer_data_provider import SoccerDataProvider


st.set_page_config(
    page_title="Soccer Data - Coverage",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Soccer Data – Analisi copertura storica")
st.caption("Verifica qualità, profondità e disponibilità dati per competizione")


if "SOCCER_DATA_KEY" not in st.secrets:
    st.error("SOCCER_DATA_KEY non configurata.")
    st.stop()

provider = SoccerDataProvider(
    st.secrets["SOCCER_DATA_KEY"]
)


def fetch_coverage(data_type=None):

    results = []
    page = 1
    total_pages = 1

    while page <= total_pages:

        params = {
            "page": page,
            "per_page": 200
        }

        if data_type:
            params["data_type"] = data_type

        payload = provider._request(
            "coverage/leagues",
            params=params
        )

        results.extend(
            payload.get("data", [])
        )

        meta = payload.get("meta", {})

        total_pages = meta.get(
            "total_pages",
            1
        )

        page += 1

    return results


st.success("Connessione API configurata.")

if st.button("🔬 Analizza copertura storica"):

    try:

        with st.spinner("Recupero copertura completa..."):

            coverage_all = fetch_coverage()
            coverage_xg = fetch_coverage("xg")

        st.success(
            f"Competizioni analizzate: {len(coverage_all)}"
        )

        st.metric(
            "Competizioni con copertura xG",
            len(coverage_xg)
        )

        # -----------------------------------------------
        # DATI GENERALI
        # -----------------------------------------------

        st.subheader("📋 Copertura generale")

        df_all = pd.json_normalize(coverage_all)

        st.dataframe(
            df_all,
            use_container_width=True,
            hide_index=True
        )

        # -----------------------------------------------
        # COMPETIZIONI CON XG
        # -----------------------------------------------

        st.subheader("🎯 Competizioni con xG")

        df_xg = pd.json_normalize(coverage_xg)

        st.dataframe(
            df_xg,
            use_container_width=True,
            hide_index=True
        )

        # -----------------------------------------------
        # EXPORT CSV
        # -----------------------------------------------

        csv = df_all.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Scarica copertura completa CSV",
            data=csv,
            file_name="soccer_coverage.csv",
            mime="text/csv"
        )

        # -----------------------------------------------
        # DATI API RAW
        # -----------------------------------------------

        with st.expander("🔎 Risposta API completa"):

            st.json(coverage_all)

        with st.expander("🎯 Risposta API filtrata xG"):

            st.json(coverage_xg)

    except Exception as e:

        st.error(
            f"Errore recupero copertura: {e}"
        )
