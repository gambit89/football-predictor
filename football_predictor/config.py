import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def get_secret(name, default=""):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


API_KEY = get_secret("API_FOOTBALL_KEY")
API_BASE_URL = get_secret(
    "API_FOOTBALL_BASE_URL",
    "https://v3.football.api-sports.io",
)
