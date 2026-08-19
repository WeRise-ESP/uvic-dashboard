"""
Conector de Meta Ads (Marketing API).

Orden: API real -> caché -> datos de ejemplo.

Credenciales esperadas en .streamlit/secrets.toml:
    [meta_ads]
    access_token = "..."
    ad_account_id = "act_33542477"
    api_version = "v21.0"
"""
from __future__ import annotations

import pandas as pd

from src import config
from src.connectors.base import (
    ResultadoConector,
    _leer_secreto,
    guardar_cache,
    leer_cache,
)
from src.data import sample_data

# Códigos de error TRANSITORIOS de Meta (reintentar, no fallar): 1 desconocido,
# 2 "Service temporarily unavailable", 4/17/613 rate limit, 341 límite de app.
_META_TRANSITORIOS = {1, 2, 4, 17, 341, 613}


def _get_meta(url, params, timeout=60, intentos=3):
    """GET a la Graph API con reintentos ante errores transitorios de Meta
    (código 2, rate limits, 5xx). Un error real (p.ej. 190 token) corta enseguida."""
    import time

    import requests

    resp = None
    for i in range(intentos):
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code == 200:
            return resp
        try:
            cod = resp.json().get("error", {}).get("code")
        except Exception:  # noqa: BLE001
            cod = None
        if (resp.status_code >= 500 or cod in _META_TRANSITORIOS) and i < intentos - 1:
            time.sleep(2 * (i + 1))  # backoff 2s, 4s
            continue
        break
    resp.raise_for_status()
    return resp


def obtener(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("meta_ads")
    if creds:
        try:
            df = _consultar_api(creds, desde, hasta)
            if df is not None:
                if not df.empty:
                    guardar_cache(df, "meta_ads")
                return ResultadoConector(df, "api", "Meta Marketing API")
        except Exception as e:  # noqa: BLE001
            cache = leer_cache("meta_ads")
            if cache is not None:
                return ResultadoConector(cache, "cache", f"API falló ({e}); uso caché")

    cache = leer_cache("meta_ads")
    if cache is not None and not cache.empty:
        return ResultadoConector(cache, "cache", "Caché local")

    dias = (hasta - desde).days + 1
    return ResultadoConector(
        sample_data.meta_ads_diario(dias), "sample", "Datos de ejemplo"
    )


def _consultar_api(creds: dict, desde, hasta) -> pd.DataFrame:
    """Insights diarios por campaña vía Graph API (con requests, sin SDK)."""
    import json
    from datetime import timedelta

    version = creds.get("api_version", "v21.0")
    account = creds.get("ad_account_id", config.META_AD_ACCOUNT_ID)
    token = creds["access_token"]

    # Estado (effective_status) de todas las campañas → mapa nombre→estado legible.
    estados = {}
    try:
        rc = _get_meta(
            f"https://graph.facebook.com/{version}/{account}/campaigns",
            {"fields": "name,effective_status", "limit": 500, "access_token": token})
        for cp in rc.json().get("data", []):
            estados[cp.get("name", "")] = config.estado_legible(cp.get("effective_status"))
    except Exception:  # noqa: BLE001
        pass

    url_base = f"https://graph.facebook.com/{version}/{account}/insights"
    filas = []
    con_datos = set()
    # Trocear el rango en ventanas de 7 días: Meta rechaza la consulta diaria de
    # rangos largos (error 1/2 'Service temporarily unavailable') pero acepta bien
    # las cortas. Se piden por tramos y se unen los resultados.
    ini = desde
    while ini <= hasta:
        fin = min(ini + timedelta(days=6), hasta)
        url = url_base
        params = {
            "level": "campaign",
            "fields": "campaign_name,impressions,clicks,spend,actions",
            "time_increment": 1,
            "time_range": json.dumps({"since": str(ini), "until": str(fin)}),
            "access_token": token,
            "limit": 500,
        }
        while url:
            resp = _get_meta(url, params)
            data = resp.json()
            for row in data.get("data", []):
                nombre = row.get("campaign_name", "")
                if not config.es_campana_werise(nombre):
                    continue  # acotamos al scope WeRise (cualquier campaña 'WeRise…')
                con_datos.add(nombre)
                # OJO: Meta reporta el MISMO lead bajo dos action_type ("lead" y
                # "offsite_conversion.fb_pixel_lead"). Sumarlos duplica → tomamos el máximo.
                vals = [
                    int(float(a.get("value", 0)))
                    for a in row.get("actions", [])
                    if a.get("action_type") in ("lead", "offsite_conversion.fb_pixel_lead")
                ]
                leads = max(vals) if vals else 0
                filas.append(dict(
                    fecha=pd.to_datetime(row["date_start"]).date(),
                    plataforma="Meta Ads",
                    campana=nombre,
                    estado=estados.get(nombre, "Otra"),
                    impresiones=int(row.get("impressions", 0)),
                    clics=int(row.get("clicks", 0)),
                    coste=round(float(row.get("spend", 0)), 2),
                    conversiones=leads,
                ))
            url = data.get("paging", {}).get("next")
            params = None  # la URL 'next' ya trae los parámetros
        ini = fin + timedelta(days=1)

    # Incluir TODAS las campañas WeRise (aunque estén pausadas o sin gasto en el
    # periodo) con una fila a cero, para que siempre se muestren en el dashboard.
    for nombre, est in estados.items():
        if config.es_campana_werise(nombre) and nombre not in con_datos:
            con_datos.add(nombre)
            filas.append(dict(
                fecha=pd.to_datetime(hasta).date(),
                plataforma="Meta Ads",
                campana=nombre,
                estado=est,
                impresiones=0, clics=0, coste=0.0, conversiones=0,
            ))

    return pd.DataFrame(filas)


