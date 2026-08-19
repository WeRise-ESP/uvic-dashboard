"""
Cálculo de métricas de marketing: agregados de plataforma, CPL (plataforma y
neto), ROAS, embudo lead->matrícula y asociación de leads de HubSpot a campañas.

Definiciones (alineadas con la skill de performance-report):
- CPL plataforma  = coste de la plataforma / leads atribuidos EN esa plataforma.
- CPL neto        = inversión total / leads válidos totales (incluye no atribuidos).
- CPA/CP-matrícula= inversión total / nº de matrículas.
- ROAS            = (matrículas * valor_matrícula) / inversión total.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config


def _safe_div(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


# --------------------------------------------------------------------------- #
# Agregados por plataforma
# --------------------------------------------------------------------------- #
def resumen_plataforma(df_ads: pd.DataFrame) -> pd.DataFrame:
    """Agrega gasto/clics/impresiones/conversiones por plataforma."""
    if df_ads.empty:
        return pd.DataFrame()
    g = (
        df_ads.groupby("plataforma", as_index=False)
        .agg(
            impresiones=("impresiones", "sum"),
            clics=("clics", "sum"),
            coste=("coste", "sum"),
            conversiones=("conversiones", "sum"),
        )
    )
    g["ctr"] = g.apply(lambda r: _safe_div(r["clics"], r["impresiones"]), axis=1)
    g["cpc"] = g.apply(lambda r: _safe_div(r["coste"], r["clics"]), axis=1)
    g["cpm"] = g.apply(lambda r: _safe_div(r["coste"] * 1000, r["impresiones"]), axis=1)
    return g


def resumen_campana(df_ads: pd.DataFrame) -> pd.DataFrame:
    """Agrega por campaña y añade el programa académico asociado."""
    if df_ads.empty:
        return pd.DataFrame()
    agg = dict(
        impresiones=("impresiones", "sum"),
        clics=("clics", "sum"),
        coste=("coste", "sum"),
        conversiones=("conversiones", "sum"),
    )
    if "estado" in df_ads.columns:
        agg["estado"] = ("estado", "first")  # el estado es constante por campaña
    g = df_ads.groupby(["plataforma", "campana"], as_index=False).agg(**agg)
    g["programa"] = g["campana"].map(config.programa_por_campana)
    g["ctr"] = g.apply(lambda r: _safe_div(r["clics"], r["impresiones"]), axis=1)
    g["cpc"] = g.apply(lambda r: _safe_div(r["coste"], r["clics"]), axis=1)
    return g.sort_values("coste", ascending=False)


# --------------------------------------------------------------------------- #
# Leads (HubSpot) y su cruce con inversión — TODO POR PROGRAMA
# --------------------------------------------------------------------------- #
def resumen_ads_por_programa(df_ads: pd.DataFrame) -> pd.DataFrame:
    """Agrega inversión/clics/impresiones por programa (mapeando campaña→programa)."""
    if df_ads.empty:
        return pd.DataFrame()
    df = df_ads.copy()
    df["programa"] = df["campana"].map(config.programa_por_campana)
    return df.groupby("programa", as_index=False).agg(
        impresiones=("impresiones", "sum"),
        clics=("clics", "sum"),
        coste=("coste", "sum"),
    )


def resumen_leads_por_programa(df_leads: pd.DataFrame) -> pd.DataFrame:
    """Cuenta leads por programa."""
    if df_leads.empty:
        return pd.DataFrame()
    return (
        df_leads.groupby("programa", as_index=False)
        .agg(leads=("lead_id", "count"))
        .sort_values("leads", ascending=False)
    )


def matriculas_por_programa(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Cuenta matrículas (deals ganados) por programa."""
    if df_deals.empty:
        return pd.DataFrame(columns=["programa", "matriculas"])
    ganados = df_deals[df_deals["es_ganado"] == True]  # noqa: E712
    if ganados.empty:
        return pd.DataFrame(columns=["programa", "matriculas"])
    return ganados.groupby("programa", as_index=False).agg(matriculas=("deal_id", "count"))


def cruce_inversion_leads(df_ads: pd.DataFrame, df_leads: pd.DataFrame,
                          df_deals: pd.DataFrame | None = None) -> pd.DataFrame:
    """Une, POR PROGRAMA, inversión (Google+Meta) con leads (uvic_curso) y
    matrículas (deals ganados), y calcula CPL, coste/matrícula y ROAS."""
    ads = resumen_ads_por_programa(df_ads)
    if ads.empty:
        return pd.DataFrame()
    leads = resumen_leads_por_programa(df_leads)
    mats = matriculas_por_programa(df_deals if df_deals is not None else pd.DataFrame())

    m = ads.merge(leads, on="programa", how="left")
    if not mats.empty:
        m = m.merge(mats, on="programa", how="left")
    else:
        m["matriculas"] = 0
    m["leads"] = m["leads"].fillna(0).astype(int)
    m["matriculas"] = m["matriculas"].fillna(0).astype(int)

    m["ctr"] = m.apply(lambda r: _safe_div(r.get("clics", 0), r.get("impresiones", 0)), axis=1)
    m["cpc"] = m.apply(lambda r: _safe_div(r["coste"], r.get("clics", 0)), axis=1)
    m["conv_click_lead"] = m.apply(lambda r: _safe_div(r["leads"], r.get("clics", 0)), axis=1)
    m["cpl"] = m.apply(lambda r: _safe_div(r["coste"], r["leads"]), axis=1)
    m["cp_matricula"] = m.apply(lambda r: _safe_div(r["coste"], r["matriculas"]), axis=1)
    m["ingresos"] = m["matriculas"] * config.VALOR_MATRICULA
    m["roas"] = m.apply(lambda r: _safe_div(r["ingresos"], r["coste"]), axis=1)
    # Excluir campañas no-WeRise sin programa asignado del foco principal.
    m = m[m["programa"] != "Otras / Branding"]
    return m.sort_values("coste", ascending=False)


# --------------------------------------------------------------------------- #
# KPIs globales
# --------------------------------------------------------------------------- #
def kpis_globales(df_ads: pd.DataFrame, df_leads: pd.DataFrame,
                  df_deals: pd.DataFrame | None = None) -> dict:
    """KPIs de cabecera. Leads = contactos uvic_curso; matrículas = deals ganados
    del Pipeline UVIC. Solo inversión de campañas con programa WeRise asignado."""
    if not df_ads.empty:
        ads = df_ads.copy()
        ads["programa"] = ads["campana"].map(config.programa_por_campana)
        inversion = float(ads[ads["programa"] != "Otras / Branding"]["coste"].sum())
    else:
        inversion = 0.0

    # Clics/impresiones de las campañas WeRise (para CTR/CPC globales).
    clics = impresiones = 0
    if not df_ads.empty:
        werise = ads[ads["programa"] != "Otras / Branding"]
        clics = int(werise["clics"].sum())
        impresiones = int(werise["impresiones"].sum())

    leads_total = int(len(df_leads)) if not df_leads.empty else 0
    leads_con_programa = (
        int((df_leads["programa"] != "Sin asignar").sum()) if not df_leads.empty else 0
    )
    if df_deals is not None and not df_deals.empty:
        matriculas = int(df_deals["es_ganado"].sum())
        deals_totales = int(len(df_deals))
    else:
        matriculas = 0
        deals_totales = 0
    ingresos = matriculas * config.VALOR_MATRICULA

    cpl_neto = _safe_div(inversion, leads_total)
    cp_matricula = _safe_div(inversion, matriculas)
    coste_por_oportunidad = _safe_div(inversion, deals_totales)
    roas = _safe_div(ingresos, inversion)
    pct_programa = _safe_div(leads_con_programa, leads_total)
    ctr_medio = _safe_div(clics, impresiones)
    cpc_medio = _safe_div(inversion, clics)
    tasa_click_lead = _safe_div(leads_total, clics)       # clic -> lead
    tasa_lead_oportunidad = _safe_div(deals_totales, leads_total)
    tasa_lead_matricula = _safe_div(matriculas, leads_total)
    matriculas_forecast = leads_total * config.TASA_LEAD_A_MATRICULA

    return dict(
        inversion=inversion,
        clics=clics,
        impresiones=impresiones,
        ctr_medio=ctr_medio,
        cpc_medio=cpc_medio,
        leads_total=leads_total,
        leads_con_programa=leads_con_programa,
        pct_programa=pct_programa,
        deals_totales=deals_totales,
        matriculas=matriculas,
        matriculas_forecast=matriculas_forecast,
        ingresos=ingresos,
        cpl_neto=cpl_neto,
        cp_matricula=cp_matricula,
        coste_por_oportunidad=coste_por_oportunidad,
        roas=roas,
        tasa_click_lead=tasa_click_lead,
        tasa_lead_oportunidad=tasa_lead_oportunidad,
        tasa_lead_matricula=tasa_lead_matricula,
        objetivo_matriculas=config.OBJETIVO_MATRICULAS,
        objetivo_inversion=config.OBJETIVO_INVERSION_MENSUAL,
    )


# --------------------------------------------------------------------------- #
# Tendencia (2ª mitad del periodo vs 1ª) — para flechas de KPI
# --------------------------------------------------------------------------- #
def tendencia(df: pd.DataFrame, valor_col: str, fecha_col: str = "fecha") -> dict:
    """Compara la mitad reciente del periodo con la anterior. Devuelve
    {delta, actual, previo, dir}. delta=None si no hay datos suficientes."""
    vacio = dict(delta=None, actual=0.0, previo=0.0, dir="flat")
    if df is None or df.empty or fecha_col not in df or valor_col not in df:
        return vacio
    s = df.groupby(fecha_col)[valor_col].sum().sort_index()
    if len(s) < 2:
        return dict(delta=None, actual=float(s.sum()), previo=0.0, dir="flat")
    corte = len(s) // 2
    previo = float(s.iloc[:corte].sum())
    actual = float(s.iloc[corte:].sum())
    delta = (actual - previo) / previo if previo else None
    direccion = "flat" if delta is None else ("up" if delta > 0.02 else ("down" if delta < -0.02 else "flat"))
    return dict(delta=delta, actual=actual, previo=previo, dir=direccion)


# --------------------------------------------------------------------------- #
# Tasas de conversión entre etapas del embudo
# --------------------------------------------------------------------------- #
def pipeline_por_etapa(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Deals que están AHORA en cada etapa del Pipeline UVIC (vista de tablero).

    A diferencia de `embudo` (acumulado y sin perdidos), reparte cada deal en su
    etapa ACTUAL e incluye 'Cierre ganado' y 'Cierre perdido'. Devuelve
    [etapa, deals, importe, pct] en el orden del pipeline."""
    cols = ["etapa", "deals", "importe", "pct"]
    if df_deals is None or df_deals.empty or "etapa" not in df_deals:
        return pd.DataFrame(columns=cols)
    g = df_deals.groupby("etapa").agg(deals=("deal_id", "count"), importe=("amount", "sum"))
    total = int(g["deals"].sum()) or 1
    filas = []
    for etapa in config.HUBSPOT_ETAPAS_TODAS:
        n = int(g["deals"].get(etapa, 0))
        filas.append(dict(etapa=etapa, deals=n,
                          importe=float(g["importe"].get(etapa, 0.0)),
                          pct=_safe_div(n, total)))
    # Etapas fuera del orden conocido (por si HubSpot añade alguna nueva).
    for etapa, r in g.iterrows():
        if etapa not in config.HUBSPOT_ETAPAS_TODAS:
            filas.append(dict(etapa=etapa, deals=int(r["deals"]),
                              importe=float(r["importe"]),
                              pct=_safe_div(int(r["deals"]), total)))
    return pd.DataFrame(filas, columns=cols)


def motivos_perdida_detalle(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Motivos de cierre perdido con nº de deals, % sobre perdidos e importe."""
    cols = ["motivo", "deals", "pct", "importe"]
    if df_deals is None or df_deals.empty or "es_perdido" not in df_deals:
        return pd.DataFrame(columns=cols)
    perdidos = df_deals[df_deals["es_perdido"] == True]  # noqa: E712
    if perdidos.empty or "motivo_perdido" not in perdidos:
        return pd.DataFrame(columns=cols)
    g = perdidos.groupby("motivo_perdido", as_index=False).agg(
        deals=("deal_id", "count"), importe=("amount", "sum"))
    g = g.rename(columns={"motivo_perdido": "motivo"})
    total = int(g["deals"].sum()) or 1
    g["pct"] = g["deals"] / total
    return g.sort_values("deals", ascending=False)[cols].reset_index(drop=True)


def tasas_embudo(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Embudo con la tasa de paso desde la etapa anterior (conv_paso)."""
    e = embudo(df_deals)
    if e.empty:
        return e
    e = e.copy()
    prev = e["leads"].shift(1)
    e["conv_paso"] = e["leads"] / prev
    e.loc[e.index[0], "conv_paso"] = 1.0
    e["conv_paso"] = e["conv_paso"].fillna(0.0)
    return e


# --------------------------------------------------------------------------- #
# Embudo del Pipeline UVIC (deals)
# --------------------------------------------------------------------------- #
ORDEN_EMBUDO = [lbl for _id, lbl in config.HUBSPOT_ETAPAS_UVIC]


def embudo(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Embudo acumulado por etapa del Pipeline UVIC (un deal en una etapa avanzada
    pasó por las anteriores). Excluye 'Cierre perdido'."""
    if df_deals.empty:
        return pd.DataFrame()
    idx = {etapa: i for i, etapa in enumerate(ORDEN_EMBUDO)}
    df = df_deals.copy()
    df["nivel"] = df["etapa"].map(idx)
    df = df.dropna(subset=["nivel"])  # descarta 'Cierre perdido' u otras
    filas = []
    for i, etapa in enumerate(ORDEN_EMBUDO):
        n = int((df["nivel"] >= i).sum())
        filas.append(dict(etapa=etapa, leads=n))
    out = pd.DataFrame(filas)
    total = out["leads"].iloc[0] if not out.empty else 0
    out["pct"] = out["leads"].apply(lambda x: _safe_div(x, total))
    return out


# --------------------------------------------------------------------------- #
# Series temporales
# --------------------------------------------------------------------------- #
def serie_diaria_inversion(df_ads: pd.DataFrame) -> pd.DataFrame:
    if df_ads.empty:
        return pd.DataFrame()
    return (
        df_ads.groupby(["fecha", "plataforma"], as_index=False)["coste"].sum()
    )


def serie_diaria_leads(df_leads: pd.DataFrame) -> pd.DataFrame:
    if df_leads.empty:
        return pd.DataFrame()
    g = df_leads.groupby("fecha_creacion", as_index=False)["lead_id"].count()
    return g.rename(columns={"fecha_creacion": "fecha", "lead_id": "leads"})


def leads_por_programa_dist(df_leads: pd.DataFrame) -> pd.DataFrame:
    """Reparto de leads por programa (para el donut del resumen)."""
    if df_leads.empty:
        return pd.DataFrame()
    return (
        df_leads.groupby("programa", as_index=False)["lead_id"].count()
        .rename(columns={"lead_id": "leads"})
    )
