"""
Dashboard de Marketing — UVic / WeRise
Página principal: Resumen Global (inversión, leads, CPL, ROAS, embudo e insights).

Ejecutar:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from src import config
from src.data import insights, loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, eur, num, pct

st.set_page_config(
    page_title="UVic · Dashboard Marketing",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)
aplicar_tema()

# --------------------------------------------------------------------------- #
# Datos
# --------------------------------------------------------------------------- #
desde, hasta, etiqueta = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes, datos.detalles)

k = metrics.kpis_globales(datos.ads, datos.leads, datos.deals)
ins = insights.generar(datos)

# Tendencias (mitad reciente vs anterior del periodo)
t_inv = metrics.tendencia(datos.ads, "coste", "fecha")
t_leads = metrics.tendencia(metrics.serie_diaria_leads(datos.leads), "leads", "fecha")
serie_deals = (datos.deals.groupby("fecha_creacion").size().reset_index(name="deals")
               .rename(columns={"fecha_creacion": "fecha"})) if not datos.deals.empty else None
t_deals = metrics.tendencia(serie_deals, "deals", "fecha") if serie_deals is not None else {"delta": None}

# --------------------------------------------------------------------------- #
# Cabecera + resumen ejecutivo
# --------------------------------------------------------------------------- #
ui.cabecera("Resumen Global", etiqueta)

_headline = ins["concerns"][0] if ins["concerns"] else ins["wins"][0]
st.info(
    f"**Resumen** · En el período **{etiqueta}** se han invertido **{eur(k['inversion'])}** en las 5 "
    f"campañas WeRise, generando **{num(k['leads_total'])} leads UVic** (CPL neto {eur(k['cpl_neto'],2)}). "
    f"Hay **{num(k['deals_totales'])} oportunidades** en el Pipeline UVIC y **{num(k['matriculas'])} "
    f"matrículas**. → {_headline}"
)

# --------------------------------------------------------------------------- #
# Fila A — Inversión y eficiencia de medios
# --------------------------------------------------------------------------- #
c1, c2, c3, c4 = st.columns(4)
pace = k["inversion"] / config.OBJETIVO_INVERSION_MENSUAL if config.OBJETIVO_INVERSION_MENSUAL else 0
ui.kpi(c1, "Inversión (G+M)", eur(k["inversion"]),
       f"{pct(pace)} del objetivo mensual", delta=t_inv["delta"], delta_bueno=True)
ui.kpi(c2, "CTR medio", pct(k["ctr_medio"], 2), "Clics / impresiones")
ui.kpi(c3, "CPC medio", eur(k["cpc_medio"], 2), "Inversión / clics")
ui.kpi(c4, "CPL neto", eur(k["cpl_neto"], 2),
       f"Objetivo {num(config.CPL_OBJETIVO_MIN)}–{num(config.CPL_OBJETIVO_MAX)} €",
       estado=config.estado_bench("cpl", k["cpl_neto"]))

st.write("")

# --------------------------------------------------------------------------- #
# Fila B — Embudo comercial
# --------------------------------------------------------------------------- #
c5, c6, c7, c8, c9 = st.columns(5)
ui.kpi(c5, "Leads UVic", num(k["leads_total"]),
       "Contactos con uvic_curso", delta=t_leads["delta"], delta_bueno=True)
n_webinar = int((datos.leads_import["motivo"] == "Webinar").sum()) \
    if "motivo" in datos.leads_import.columns else 0
ui.kpi(c6, "Leads WebInar", num(n_webinar),
       "Fuera del cómputo de campañas")
ui.kpi(c7, "Oportunidades", num(k["deals_totales"]),
       f"Coste/oport. {eur(k['coste_por_oportunidad'])}",
       delta=t_deals["delta"], delta_bueno=True)
ui.kpi(c8, "Matrículas", num(k["matriculas"]))
ui.kpi(c9, "ROAS", f"{num(k['roas'],2)}×",
       f"Ingresos est.: {eur(k['ingresos'])}",
       estado=config.estado_bench("roas", k["roas"]))

# Métricas secundarias del embudo (una línea)
st.caption(
    f"**Tasas de conversión** · Clic→Lead {pct(k['tasa_click_lead'],1)} · "
    f"Lead→Oportunidad {pct(k['tasa_lead_oportunidad'],1)} · "
    f"Lead→Matrícula {pct(k['tasa_lead_matricula'],1)} · "
    f"Coste/matrícula {eur(k['cp_matricula'])} · "
    f"Forecast matrículas {num(k['matriculas_forecast'],1)} (tasa {pct(config.TASA_LEAD_A_MATRICULA)})"
)

st.divider()

# --------------------------------------------------------------------------- #
# Gráficos principales
# --------------------------------------------------------------------------- #
col_izq, col_der = st.columns([0.58, 0.42])
with col_izq:
    st.subheader("Inversión diaria por plataforma")
    ui.linea_temporal(metrics.serie_diaria_inversion(datos.ads),
                      x="fecha", y="coste", color="plataforma", titulo="", y_label="€/día")
with col_der:
    st.subheader("Reparto de inversión")
    resumen = metrics.resumen_plataforma(datos.ads)
    if not resumen.empty:
        ui.donut(resumen, nombres="plataforma", valores="coste", titulo="")

# --- Tablas diarias: conversiones de plataforma y leads de HubSpot ----------- #
col_t1, col_t2 = st.columns(2)
with col_t1:
    st.subheader("Conversiones diarias · plataformas")
    if not datos.ads.empty:
        conv = (datos.ads.pivot_table(index="fecha", columns="plataforma",
                                      values="conversiones", aggfunc="sum", fill_value=0)
                .astype(int).reset_index().sort_values("fecha", ascending=False))
        conv.columns.name = None
        plat_cols = [c for c in ("Google Ads", "Meta Ads") if c in conv.columns]
        conv["total"] = conv[plat_cols].sum(axis=1)
        ui.tabla_totales(
            conv,
            columnas=["fecha", *plat_cols, "total"],
            sum_cols=[*plat_cols, "total"],
            column_config={
                "fecha": st.column_config.DateColumn("Día", format="DD/MM/YYYY"),
                **{c: st.column_config.NumberColumn(c, format="%d") for c in plat_cols},
                "total": st.column_config.NumberColumn("Total", format="%d"),
            },
        )
        st.caption("Conversiones atribuidas por cada plataforma (Google/Meta) por día.")
    else:
        st.info("Sin datos de plataformas.")
with col_t2:
    st.subheader("Leads diarios · HubSpot")
    if not datos.leads.empty:
        ld = (datos.leads.pivot_table(index="fecha_creacion", columns="fuente",
                                      values="lead_id", aggfunc="count", fill_value=0)
              .astype(int).reset_index().sort_values("fecha_creacion", ascending=False)
              .rename(columns={"fecha_creacion": "fecha"}))
        ld.columns.name = None
        fuente_cols = [c for c in ("Meta", "Google", "Sin UTM") if c in ld.columns]
        otras = [c for c in ld.columns if c not in ("fecha", *fuente_cols)]
        fuente_cols += otras
        ld["total"] = ld[fuente_cols].sum(axis=1)
        ui.tabla_totales(
            ld,
            columnas=["fecha", *fuente_cols, "total"],
            sum_cols=[*fuente_cols, "total"],
            column_config={
                "fecha": st.column_config.DateColumn("Día", format="DD/MM/YYYY"),
                **{c: st.column_config.NumberColumn(c, format="%d") for c in fuente_cols},
                "total": st.column_config.NumberColumn("Total", format="%d"),
            },
        )
        st.caption("Leads reales creados en HubSpot por día, desglosados por fuente UTM.")
    else:
        st.info("Sin leads en el período.")

# --- Gráficos diarios totales (inversión, leads, conversiones) --------------- #
st.divider()
st.subheader("Evolución diaria · totales")

st.markdown("**Inversión diaria total** · Google Ads + Meta Ads")
if not datos.ads.empty:
    serie_inv = datos.ads.groupby("fecha", as_index=False)["coste"].sum()
    ui.linea_temporal(serie_inv, x="fecha", y="coste",
                      color=None, titulo="", y_label="€/día")
else:
    st.info("Sin datos de plataformas.")

st.markdown("**Leads diarios totales** · HubSpot")
if not datos.leads.empty:
    serie_leads = (datos.leads.groupby("fecha_creacion", as_index=False)
                   .agg(leads=("lead_id", "count"))
                   .rename(columns={"fecha_creacion": "fecha"}))
    ui.linea_temporal(serie_leads, x="fecha", y="leads",
                      color=None, titulo="", y_label="Leads/día")
else:
    st.info("Sin leads en el período.")

st.markdown("**Conversiones diarias totales** · Google Ads + Meta Ads")
if not datos.ads.empty:
    serie_conv = datos.ads.groupby("fecha", as_index=False)["conversiones"].sum()
    ui.linea_temporal(serie_conv, x="fecha", y="conversiones",
                      color=None, titulo="", y_label="Conversiones/día")
else:
    st.info("Sin datos de plataformas.")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Embudo Pipeline UVIC (deals)")
    st.caption("Oportunidad → Entrevista → Envío inscripción → Cierre ganado (= matrícula).")
    ui.embudo_chart(metrics.embudo(datos.deals))
with col_b:
    st.subheader("Leads UVic por programa")
    st.caption("Atribución de campaña perdida (leads OFFLINE); se asocian por programa vía `uvic_curso`.")
    ui.donut(metrics.leads_por_programa_dist(datos.leads),
             nombres="programa", valores="leads", titulo="")

st.divider()

# --------------------------------------------------------------------------- #
# Tabla resumen por programa
# --------------------------------------------------------------------------- #
st.subheader("Rendimiento por programa")
cruce = metrics.cruce_inversion_leads(datos.ads, datos.leads, datos.deals)
if not cruce.empty:
    tabla = cruce[["programa", "coste", "clics", "ctr", "cpc",
                   "leads", "cpl", "matriculas", "roas"]].copy()
    tabla["ctr"] = (tabla["ctr"] * 100).round(2)  # ratio -> %
    st.dataframe(
        tabla, width='stretch', hide_index=True,
        column_config={
            "programa": "Programa",
            "coste": st.column_config.NumberColumn("Inversión (G+M)", format="%.0f €"),
            "clics": st.column_config.NumberColumn("Clics", format="%d"),
            "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
            "cpc": st.column_config.NumberColumn("CPC", format="%.2f €"),
            "leads": st.column_config.NumberColumn("Leads", format="%d"),
            "cpl": st.column_config.NumberColumn("CPL", format="%.2f €"),
            "matriculas": st.column_config.NumberColumn("Matrículas", format="%d"),
            "roas": st.column_config.NumberColumn("ROAS", format="%.2f×"),
        },
    )
    st.caption(
        "**Inversión (G+M)** = Google Ads + Meta del programa. **CPL** = inversión / leads "
        "(`uvic_curso`) del programa. La campaña exacta no se aísla (atribución OFFLINE)."
    )

st.divider()

# --------------------------------------------------------------------------- #
# Insights y recomendaciones (skill: what worked / needs improvement / recos)
# — siempre al final, después de todos los gráficos.
# --------------------------------------------------------------------------- #
st.subheader("Insights del periodo")
ui.caja_insights(ins["wins"], ins["concerns"])
with st.expander("💡 Recomendaciones priorizadas (impacto × esfuerzo)", expanded=True):
    ui.tabla_recomendaciones(ins["recos"])
