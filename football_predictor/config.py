
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def get_secret(name, default=""):
    try:
        return st.secrets.get(
            name,
            os.getenv(name, default)
        )
    except Exception:
        return os.getenv(name, default)


# Nuovo provider: football-data.org
API_KEY = get_secret("FOOTBALL_DATA_TOKEN")

API_BASE_URL = get_secret(
    "FOOTBALL_DATA_BASE_URL",
    "https://api.football-data.org/v4"
)
