"""
Orquestador de datos: llama a cada conector con caché de Streamlit y expone
un objeto único `DatosDashboard` que consumen todas las páginas.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from src import config
from src.connectors import ga4, google_ads, hubspot, meta_ads, plan


@dataclass
class DatosDashboard:
    google: pd.DataFrame
    meta: pd.DataFrame
    ga4: pd.DataFrame
    leads: pd.DataFrame
    deals: pd.DataFrame
    origenes: dict  # {"Google Ads": "sample", ...}
    detalles: dict = field(default_factory=dict)  # motivo/origen por fuente
    leads_import: pd.DataFrame = field(default_factory=pd.DataFrame)
    negocios_import: pd.DataFrame = field(default_factory=pd.DataFrame)
    origen_import: str = "sample"
    ga4_fuente: pd.DataFrame = field(default_factory=pd.DataFrame)
    ga4_campana: pd.DataFrame = field(default_factory=pd.DataFrame)
    ga4_resumen: pd.DataFrame = field(default_factory=pd.DataFrame)
    ga4_eventos: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def ads(self) -> pd.DataFrame:
        """Google + Meta unificados (mismo esquema de columnas)."""
        frames = [d for d in (self.google, self.meta) if not d.empty]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def hay_datos_reales(self) -> bool:
        return any(o in ("api", "cache") for o in self.origenes.values())


# Caché por fuente con TTL distinto: HubSpot corto (cambia a diario), ads/GA4 largo.
@st.cache_data(ttl=config.CACHE_TTL_ADS, show_spinner="Cargando Google Ads…")
def _cargar_google(desde, hasta):
    r = google_ads.obtener(desde, hasta)
    return r.df, r.origen, r.detalle


@st.cache_data(ttl=config.CACHE_TTL_ADS, show_spinner="Cargando Meta Ads…")
def _cargar_meta(desde, hasta):
    r = meta_ads.obtener(desde, hasta)
    return r.df, r.origen, r.detalle


@st.cache_data(ttl=config.CACHE_TTL_GA4, show_spinner="Cargando GA4…")
def _cargar_ga4(desde, hasta):
    r = ga4.obtener(desde, hasta)
    rf = ga4.obtener_fuente(desde, hasta)
    rc = ga4.obtener_campana(desde, hasta)
    rr = ga4.obtener_resumen(desde, hasta)
    re = ga4.obtener_eventos_campana(desde, hasta)
    return r.df, r.origen, r.detalle, rf.df, rc.df, rr.df, re.df


@st.cache_data(ttl=config.CACHE_TTL_HUBSPOT, show_spinner="Cargando HubSpot…")
def _cargar_hubspot(desde, hasta):
    leads = hubspot.obtener(desde, hasta)
    deals = hubspot.obtener_deals(desde, hasta)
    return leads.df, leads.origen, leads.detalle, deals.df


@st.cache_data(ttl=config.CACHE_TTL_HUBSPOT, show_spinner="Cargando leads importados…")
def _cargar_importados():
    leads_i, negocios_i, origen_i = hubspot.importados()
    return leads_i, negocios_i, origen_i


@st.cache_data(ttl=config.CACHE_TTL_HUBSPOT, show_spinner="Cargando actividad comercial…")
def cargar_actividad():
    """Informe de actividad de leads UVIC (llamadas, emails, intentos de contacto).
    Devuelve (estructura, origen)."""
    return hubspot.actividad_uvic()


@st.cache_data(ttl=config.CACHE_TTL_HUBSPOT, show_spinner="Cargando planificación…")
def cargar_plan():
    """Planificación trimestral (Google Sheet en vivo). Devuelve
    (estructura {pestaña: [bloques]}, origen, detalle)."""
    return plan.obtener_plan()


def cargar_todo(desde, hasta) -> DatosDashboard:
    g_df, g_o, g_d = _cargar_google(desde, hasta)
    m_df, m_o, m_d = _cargar_meta(desde, hasta)
    a_df, a_o, a_d, af_df, ac_df, ar_df, ae_df = _cargar_ga4(desde, hasta)
    l_df, l_o, l_d, d_df = _cargar_hubspot(desde, hasta)
    li_df, ni_df, oi = _cargar_importados()
    return DatosDashboard(
        google=g_df, meta=m_df, ga4=a_df, leads=l_df, deals=d_df,
        origenes={
            "Google Ads": g_o,
            "Meta Ads": m_o,
            "Google Analytics": a_o,
            "HubSpot": l_o,
        },
        detalles={
            "Google Ads": g_d,
            "Meta Ads": m_d,
            "Google Analytics": a_d,
            "HubSpot": l_d,
        },
        leads_import=li_df, negocios_import=ni_df, origen_import=oi,
        ga4_fuente=af_df, ga4_campana=ac_df, ga4_resumen=ar_df, ga4_eventos=ae_df,
    )
