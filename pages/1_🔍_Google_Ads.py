"""Página: detalle de Google Ads (búsqueda) — con benchmarks, tendencia e insights."""
from __future__ import annotations

import streamlit as st

from src import config
from src.data import loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, eur, num, pct

st.set_page_config(page_title="Google Ads · UVic", page_icon="🔍", layout="wide")
aplicar_tema()

desde, hasta, etiqueta = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes, datos.detalles)

ui.cabecera("Google Ads", f"Cuenta {config.GOOGLE_ADS_CUSTOMER_ID} · búsqueda WeRise · {etiqueta}")

df = datos.google
if df.empty:
    st.warning("No hay datos de Google Ads.")
    st.stop()

r = metrics.resumen_plataforma(df).iloc[0]
t_inv = metrics.tendencia(df, "coste", "fecha")
resultados = int(r["conversiones"])
tasa_resultados = resultados / r["clics"] if r["clics"] else 0
coste_resultado = r["coste"] / resultados if resultados else 0

# CPL real: eventos clave de GA4 llegados desde Google de pago (google / cpc).
ev_google = 0
gf = datos.ga4_fuente
if not gf.empty and {"fuente", "medio", "eventos_clave"}.issubset(gf.columns):
    mask = (gf["fuente"].str.lower() == "google") & (gf["medio"].astype(str).str.lower() == "cpc")
    ev_google = int(gf[mask]["eventos_clave"].sum())
cpl_real = r["coste"] / ev_google if ev_google else 0

st.subheader("Volumen y coste")
c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Inversión", eur(r["coste"]), delta=t_inv["delta"], delta_bueno=True)
ui.kpi(c2, "Impresiones", num(r["impresiones"]), "Alcance de búsqueda")
ui.kpi(c3, "Clics", num(r["clics"]), f"CTR {pct(r['ctr'],2)}",
       estado=config.estado_bench("ctr_search", r["ctr"]))
ui.kpi(c4, "CPM", eur(r["cpm"], 2), "Coste por mil impresiones")

st.subheader("Eficiencia y resultado")
c5, c6, c7, c8 = st.columns(4)
ui.kpi(c5, "CPC medio", eur(r["cpc"], 2), f"Benchmark ≤ {eur(config.BENCH['cpc_search']['ok'],1)}",
       estado=config.estado_bench("cpc_search", r["cpc"]))
ui.kpi(c6, "Resultados (conversiones)", num(resultados),
       f"Tasa {pct(tasa_resultados,2)} sobre clics",
       estado="ok" if resultados > 0 else "off")
ui.kpi(c7, "Coste/resultado", eur(coste_resultado, 2) if resultados else "—",
       "Inversión / conversiones Google",
       estado=config.estado_bench("cpl", coste_resultado) if resultados else "off")
# Leads reales en HubSpot con UTM de Google.
leads_g_hs = datos.leads[datos.leads["fuente"] == "Google"] if "fuente" in datos.leads else datos.leads.iloc[0:0]
n_leads_g = len(leads_g_hs)
cpl_hs = r["coste"] / n_leads_g if n_leads_g else 0
ui.kpi(c8, "CPL real (HubSpot)", eur(cpl_hs, 2) if n_leads_g else "—",
       f"{num(n_leads_g)} leads con UTM de Google",
       estado=config.estado_bench("cpl", cpl_hs) if n_leads_g else None)

if resultados == 0:
    st.warning("Google no está atribuyendo conversiones pese al gasto. Revisa *Tracking & Atribución*.")
else:
    st.caption(
        f"Las 3 mediciones · Google atribuye **{num(resultados)}** conversiones · GA4 registra "
        f"**{num(ev_google)}** eventos clave de google/cpc (CPL {eur(cpl_real,2) if ev_google else '—'}) · "
        f"HubSpot tiene **{num(n_leads_g)}** leads con UTM de Google de {num(len(datos.leads))} totales."
    )

# --- Comparativa de medición por campaña ------------------------------------- #
st.subheader("Comparativa de medición por campaña")
st.caption("Resultados según cada fuente: Google (plataforma) · HubSpot (leads con `uvic_utm_campaign`) · GA4 (eventos clave de google/cpc).")
_gg = df.groupby("campana")["conversiones"].sum().astype(int)
# Emparejar leads↔campaña por clave normalizada (tolera mayúsculas/separadores en la UTM).
_lh = {}
if n_leads_g:
    _tmp = leads_g_hs.copy()
    _tmp["_k"] = _tmp["campana"].map(config.clave_agrupacion_campana)
    _lh = _tmp.groupby("_k").size().to_dict()
_gc = datos.ga4_campana
# Eventos GA4 por campaña, emparejados por clave normalizada (igual que los leads).
_gv = {}
if not _gc.empty and {"fuente", "campana", "eventos_clave"}.issubset(_gc.columns):
    _g = _gc[_gc["fuente"].str.lower() == "google"].copy()
    _g["_k"] = _g["campana"].map(config.clave_agrupacion_campana)
    _gv = _g.groupby("_k")["eventos_clave"].sum().to_dict()
_comp = []
for _camp in _gg.index:
    _comp.append(dict(
        campana=_camp,
        resultados_google=int(_gg.get(_camp, 0)),
        leads_hubspot=int(_lh.get(config.clave_agrupacion_campana(_camp), 0)),
        eventos_ga4=int(_gv.get(config.clave_agrupacion_campana(_camp), 0)),
    ))
import pandas as _pd
ui.tabla_totales(
    _pd.DataFrame(_comp),
    columnas=["campana", "resultados_google", "leads_hubspot", "eventos_ga4"],
    sum_cols=["resultados_google", "leads_hubspot", "eventos_ga4"],
    column_config={
        "campana": "Campaña",
        "resultados_google": st.column_config.NumberColumn("Resultados Google", format="%d"),
        "leads_hubspot": st.column_config.NumberColumn("Leads HubSpot (UTM)", format="%d"),
        "eventos_ga4": st.column_config.NumberColumn("Eventos clave GA4", format="%d"),
    },
)

camp = metrics.resumen_campana(df)

st.divider()

st.subheader("Inversión y clics diarios")
serie = df.groupby("fecha", as_index=False).agg(coste=("coste", "sum"), clics=("clics", "sum"))
ui.linea_temporal(serie, x="fecha", y="coste", color=None, titulo="Inversión €/día", y_label="€")

st.subheader("Rendimiento por campaña")
ui.barras(camp.head(10), x="coste", y="campana", color="programa",
          titulo="Inversión por campaña", orientacion="h")
_cols_base = ["campana", "programa", "impresiones", "clics", "ctr", "cpc", "coste", "conversiones"]
if "estado" in camp.columns:
    _cols_base.insert(1, "estado")
tab = camp[_cols_base].copy()
tab["ctr"] = (tab["ctr"] * 100).round(2)  # ratio -> %
tab["cpl_google"] = tab.apply(
    lambda r: r["coste"] / r["conversiones"] if r["conversiones"] else 0, axis=1)
tab["leads_hubspot"] = tab["campana"].map(
    lambda c: _lh.get(config.clave_agrupacion_campana(c), 0)).astype(int)
_cols_tab = ["campana", "programa", "impresiones", "clics", "ctr", "cpc", "coste",
             "conversiones", "cpl_google", "leads_hubspot"]
if "estado" in tab.columns:
    _cols_tab.insert(2, "estado")
ui.tabla_totales(
    tab,
    columnas=_cols_tab,
    sum_cols=["impresiones", "clics", "coste", "conversiones", "leads_hubspot"],
    ratios={
        "ctr": ("clics", "impresiones", 100, "%"),
        "cpc": ("coste", "clics", 1, " €"),
        "cpl_google": ("coste", "conversiones", 1, " €"),
    },
    column_config={
        "campana": "Campaña", "programa": "Programa", "estado": "Estado",
        "impresiones": st.column_config.NumberColumn("Impr.", format="%d"),
        "clics": st.column_config.NumberColumn("Clics", format="%d"),
        "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
        "cpc": st.column_config.NumberColumn("CPC", format="%.2f €"),
        "coste": st.column_config.NumberColumn("Inversión", format="%.0f €"),
        "conversiones": st.column_config.NumberColumn("Resultados Google", format="%d"),
        "cpl_google": st.column_config.NumberColumn("CPL Google", format="%.2f €"),
        "leads_hubspot": st.column_config.NumberColumn("Leads HubSpot", format="%d"),
    },
)
st.caption(
    "**Resultados Google** = conversiones atribuidas por la plataforma · **CPL Google** = inversión / "
    "resultados Google · **Leads HubSpot** = leads reales con `uvic_utm_campaign` de esa campaña."
)
st.caption(
    "Las 5 campañas `WeRise_Search_NAC_` traen el grueso de leads cualificados. "
    "El CPL real por programa está en la página *Leads (HubSpot)*."
)

st.divider()

# --- Insights del periodo (siempre al final, tras los gráficos) --------------- #
st.subheader("Insights del periodo")
wins, concerns = [], []
if r["conversiones"] <= 1:
    concerns.append(
        f"**{int(r['conversiones'])} conversiones** registradas pese a {eur(r['coste'])} de gasto: "
        "el tracking no atribuye. Los leads reales están en HubSpot (página *Leads*)."
    )
if not camp.empty:
    mejor = camp.sort_values("ctr", ascending=False).iloc[0]
    wins.append(f"Mejor CTR: **{mejor['programa']}** ({pct(mejor['ctr'],2)}, CPC {eur(mejor['cpc'],2)}).")
    caro = camp.sort_values("cpc", ascending=False).iloc[0]
    if config.estado_bench("cpc_search", caro["cpc"]) == "off":
        concerns.append(f"CPC alto en **{caro['programa']}** ({eur(caro['cpc'],2)}): revisa puja y Quality Score.")
ui.caja_insights(wins, concerns)
