# Football Predictor ⚽

Applicazione web per analisi e previsioni pre-partita di calcio.

## Funzionalità

- Calendario delle partite
- Analisi ultime 10 partite
- Statistiche stagionali
- Modello probabilistico Poisson
- Probabilità 1X2
- Over/Under 2.5
- Goal/No Goal
- Risultati esatti più probabili
- Archivio previsioni SQLite

## Tecnologie

- Python
- Streamlit
- API-Football
- SQLite
- Pandas

## Avvio locale

Installare le dipendenze:

pip install -r requirements.txt

Avviare l'app:

streamlit run app.py

## API

Provider: https://www.api-football.com/

La chiave API deve essere inserita nelle variabili d'ambiente o nei Secrets di Streamlit Cloud.

Non inserire mai credenziali nel repository.

## Nota

Le previsioni sono stime statistiche e non garantiscono risultati.
Il modello necessita di backtesting e calibrazione.
