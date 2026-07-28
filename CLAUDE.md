# Dashboard de Marketing — UVic / WeRise

Contexto para trabajar en este proyecto. Léelo antes de tocar código.

## Qué es
Dashboard **Streamlit multipágina** de marketing para los programas de UVic
gestionados por WeRise (Executive MBA y afines). Ads + GA4 + HubSpot.

- **Repo:** `WeRise-ESP/uvic-dashboard` (rama `main`)
- **App:** https://uvic-dashboard.streamlit.app
- **Entry point:** `app.py`
- **Actualizar = `git push` a `main`** → Streamlit Cloud redespliega solo.

## Arrancar en local
```bash
source .venv/bin/activate        # o crear: python -m venv .venv && pip install -r requirements.txt
streamlit run app.py
```
Necesitas `.streamlit/secrets.toml` (NO está en git — pídelo por el gestor de
contraseñas del equipo). La service account de GA4 va **en línea** como
`[ga4.service_account]`, no como fichero.

## Fuentes de datos
- **Google Ads** (CID 2970533333) + **Meta Ads** + **HubSpot** (token de Rise
  Education — usar siempre ese, no proponer rotarlo) + **GA4**.
- Segmentación por programa vía propiedad `uvic_curso`; matrículas = pipeline UVIC.
- Tema de marca UVic: rojo `#CF0A2C`.

## Nota
Reversal es un **clon** de este dashboard (misma arquitectura `src/connectors`,
`src/data`, `src/ui`). Si arreglas algo estructural aquí, probablemente aplique allá.

## ⚠️ Trampas comunes (heredadas de la arquitectura)
- **Batches de HubSpot: máximo 100 inputs** por llamada (la API devuelve 400 con más).
- **Matrículas = deals ganados**, no contactos por lifecyclestage.
- Cada conector: **API real → caché parquet → sample_data** (para que sea navegable
  sin credenciales).
