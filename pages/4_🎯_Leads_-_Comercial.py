"""Página: Leads - Comercial — leads UVic por programa, CPL, embudo, pipeline y tasas."""
from __future__ import annotations

import streamlit as st

from src import config
from src.data import loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, eur, num, pct
from src.config import TEMA

st.set_page_config(page_title="Leads - Comercial", page_icon="🎯", layout="wide")
aplicar_tema()

desde, hasta, etiqueta = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes, datos.detalles)

ui.cabecera("Leads - Comercial", f"Rise Education · leads UVic por programa · {etiqueta}")

leads = datos.leads
deals = datos.deals
if leads.empty and deals.empty:
    st.warning("No hay datos de HubSpot.")
    st.stop()

total = len(leads)
con_programa = int((leads["programa"] != "Sin asignar").sum()) if total else 0
deals_tot = len(deals)
matriculas = int(deals["es_ganado"].sum()) if not deals.empty else 0
t_leads = metrics.tendencia(metrics.serie_diaria_leads(leads), "leads", "fecha")

c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Leads UVic", num(total), "Contactos con uvic_curso",
       delta=t_leads["delta"], delta_bueno=True)
ui.kpi(c2, "Oportunidades", num(deals_tot),
       f"Lead→Oport. {pct(deals_tot/total if total else 0)}")
ui.kpi(c3, "Matrículas", num(matriculas),
       f"Lead→Matríc. {pct(matriculas/total if total else 0)}",
       estado="ok" if matriculas > 0 else "off")
ui.kpi(c4, "Con programa", pct(con_programa/total if total else 0),
       "Leads con uvic_curso",
       estado="ok" if total and con_programa/total >= 0.9 else "warn")

cruce = metrics.cruce_inversion_leads(datos.ads, leads, deals)

st.divider()

col_a, col_b = st.columns([0.5, 0.5])
with col_a:
    st.subheader("Leads por programa")
    por_prog = metrics.resumen_leads_por_programa(leads)
    ui.barras(por_prog.sort_values("leads"), x="leads", y="programa",
              color=None, titulo="", orientacion="h")
with col_b:
    st.subheader("Embudo Pipeline UVIC")
    ui.embudo_chart(metrics.embudo(deals))

# --- Atribución por UTM (fuente y campaña) ----------------------------------- #
st.subheader("Atribución por UTM (fuente y campaña)")
con_utm = int((leads["fuente"] != "Sin UTM").sum()) if "fuente" in leads.columns else 0
st.caption(
    f"**{pct(con_utm/total if total else 0)}** de los leads llega con UTM "
    f"({num(con_utm)} de {num(total)}). Fuente derivada de `uvic_utm_source/medium`; "
    "campaña de `uvic_utm_campaign`."
)
col_c, col_d = st.columns([0.4, 0.6])
with col_c:
    por_fuente = leads.groupby("fuente", as_index=False)["lead_id"].count().rename(
        columns={"lead_id": "leads"})
    ui.donut(por_fuente, nombres="fuente", valores="leads", titulo="")
with col_d:
    con_camp = leads[leads["campana"] != ""]
    if not con_camp.empty:
        por_camp = (con_camp.groupby(["fuente", "campana"], as_index=False)["lead_id"].count()
                    .rename(columns={"lead_id": "leads"})
                    .sort_values("leads", ascending=False))
        ui.tabla_totales(
            por_camp,
            columnas=["fuente", "campana", "leads"],
            sum_cols=["leads"],
            column_config={
                "fuente": "Fuente", "campana": "Campaña (UTM)",
                "leads": st.column_config.NumberColumn("Leads", format="%d"),
            },
        )
    else:
        st.info("Ningún lead del periodo trae campaña en la UTM.")

st.subheader("Tasas de conversión del embudo")
te = metrics.tasas_embudo(deals)
if not te.empty:
    te2 = te.copy()
    te2["pct"] = (te2["pct"] * 100).round(1)
    te2["conv_paso"] = (te2["conv_paso"] * 100).round(1)
    st.dataframe(
        te2[["etapa", "leads", "pct", "conv_paso"]],
        width='stretch', hide_index=True,
        column_config={
            "etapa": "Etapa",
            "leads": st.column_config.NumberColumn("Deals", format="%d"),
            "pct": st.column_config.NumberColumn("% del total", format="%.1f%%"),
            "conv_paso": st.column_config.NumberColumn("Conv. desde anterior", format="%.1f%%"),
        },
    )

st.divider()

# --------------------------------------------------------------------------- #
# Pipeline de ventas — reparto por etapa ACTUAL (vista de tablero HubSpot)
# --------------------------------------------------------------------------- #
st.subheader("Pipeline de ventas · Pipeline UVIC")
st.caption(
    "Dónde está **ahora** cada negocio del *Pipeline UVIC*. A diferencia del embudo "
    "(acumulado), aquí cada deal cuenta en su etapa actual e incluye los cierres "
    "ganados y perdidos."
)
pipe_et = metrics.pipeline_por_etapa(deals)
if pipe_et.empty:
    st.info("Sin negocios en el pipeline para este periodo.")
else:
    _hay_importe = float(pipe_et["importe"].sum()) > 0
    cols_et = st.columns(len(pipe_et))
    for c, (_, r) in zip(cols_et, pipe_et.iterrows()):
        est = ("ok" if r["etapa"] == "Cierre ganado"
               else "off" if r["etapa"] == "Cierre perdido" else None)
        sub = pct(r["pct"], 1) + (f" · {eur(r['importe'], 0)}" if _hay_importe else "")
        ui.kpi(c, r["etapa"], num(r["deals"], 0), sub, estado=est)

    st.write("")
    _COL_ETAPA = {"Cierre ganado": TEMA.verde_ok, "Cierre perdido": TEMA.rojo_off}
    graf = pipe_et.copy()
    graf["txt"] = graf["deals"].apply(lambda v: num(v, 0))
    ui.barras_horizontales(
        graf, "etapa", "deals", texto_col="txt",
        colores=[_COL_ETAPA.get(e, TEMA.primario) for e in graf["etapa"]],
        x_label="Negocios")

    tp = pipe_et.copy()
    tp["pct"] = (tp["pct"] * 100).round(1)
    _cols = ["etapa", "deals", "pct"] + (["importe"] if _hay_importe else [])
    _cfg = {
        "etapa": "Etapa",
        "deals": st.column_config.NumberColumn("Negocios", format="%d"),
        "pct": st.column_config.NumberColumn("% del pipeline", format="%.1f%%"),
        "importe": st.column_config.NumberColumn("Importe", format="%.0f €"),
    }
    ui.tabla_totales(tp, columnas=_cols,
                     sum_cols=["deals"] + (["importe"] if _hay_importe else []),
                     column_config=_cfg)

st.divider()

# --------------------------------------------------------------------------- #
# Motivos de cierre perdido
# --------------------------------------------------------------------------- #
st.subheader("Motivos de cierre perdido")
mot = metrics.motivos_perdida_detalle(deals)
if mot.empty:
    st.info("No hay negocios en 'Cierre perdido' en este periodo.")
else:
    n_perd = int(mot["deals"].sum())
    st.caption(
        f"Los **{num(n_perd)} negocios perdidos** del periodo, por su *Motivo de cierre "
        f"perdido* (HubSpot). El importe es el valor que se quedó por el camino."
    )
    c_izq, c_der = st.columns([0.45, 0.55])
    with c_izq:
        graf_mot = mot.copy()
        graf_mot["txt"] = graf_mot["deals"].apply(lambda v: num(v, 0))
        ui.barras_horizontales(graf_mot, "motivo", "deals", texto_col="txt",
                               x_label="Negocios perdidos")
    with c_der:
        tm = mot.copy()
        tm["pct"] = (tm["pct"] * 100).round(1)
        _hay_imp_m = float(mot["importe"].sum()) > 0
        _cols_m = ["motivo", "deals", "pct"] + (["importe"] if _hay_imp_m else [])
        ui.tabla_totales(
            tm, columnas=_cols_m,
            sum_cols=["deals"] + (["importe"] if _hay_imp_m else []),
            column_config={
                "motivo": "Motivo",
                "deals": st.column_config.NumberColumn("Negocios", format="%d"),
                "pct": st.column_config.NumberColumn("%", format="%.1f%%"),
                "importe": st.column_config.NumberColumn("Importe", format="%.0f €"),
            },
        )

st.divider()

st.subheader("Inversión ↔ leads por programa (CPL, coste/matrícula, ROAS)")
if not cruce.empty:
    tab = cruce[["programa", "coste", "clics", "leads", "cpl",
                 "matriculas", "cp_matricula", "roas"]].copy()
    st.dataframe(
        tab, width='stretch', hide_index=True,
        column_config={
            "programa": "Programa",
            "coste": st.column_config.NumberColumn("Inversión (G+M)", format="%.0f €"),
            "clics": st.column_config.NumberColumn("Clics", format="%d"),
            "leads": st.column_config.NumberColumn("Leads", format="%d"),
            "cpl": st.column_config.NumberColumn("CPL", format="%.2f €"),
            "matriculas": st.column_config.NumberColumn("Matrículas", format="%d"),
            "cp_matricula": st.column_config.NumberColumn("Coste/matrícula", format="%.0f €"),
            "roas": st.column_config.NumberColumn("ROAS", format="%.2f×"),
        },
    )

st.subheader("Leads recientes")
cols = [c for c in ["lead_id", "fecha_creacion", "programa", "nivel", "estado", "fuente", "campana"]
        if c in leads.columns]
st.dataframe(
    leads.sort_values("fecha_creacion", ascending=False).head(50)[cols],
    width='stretch', hide_index=True,
    column_config={
        "lead_id": "ID", "fecha_creacion": "Creado", "programa": "Programa",
        "nivel": "Nivel estudios", "estado": "Estado", "fuente": "Fuente",
        "campana": "Campaña (UTM)",
    },
)
st.caption(
    "La **fuente y campaña** vienen de las UTMs propias (`uvic_utm_*`), que hoy llegan en parte de "
    "los leads; el resto entra sin UTM. La asociación con inversión sigue siendo **por programa** "
    "(`uvic_curso`), que cubre el 100%. Elevar el % de leads con UTM es la palanca para medir CPL "
    "por campaña de forma completa."
)

st.divider()

# --- Insights del periodo (siempre al final, tras los gráficos) --------------- #
st.subheader("Insights del periodo")
wins, concerns = [], []
con_leads = cruce[cruce["leads"] > 0] if not cruce.empty else cruce
if not con_leads.empty:
    mejor = con_leads.sort_values("cpl").iloc[0]
    wins.append(f"Programa más eficiente: **{mejor['programa']}** (CPL {eur(mejor['cpl'],2)}).")
    peor = con_leads.sort_values("cpl").iloc[-1]
    if len(con_leads) > 1 and peor["cpl"] > mejor["cpl"] * 1.5:
        concerns.append(f"CPL más caro: **{peor['programa']}** ({eur(peor['cpl'],2)}).")
if total and con_programa / total < 0.95:
    concerns.append(f"Solo el {pct(con_programa/total)} de leads tiene `uvic_curso`: mejora el etiquetado para medir bien el CPL.")
ui.caja_insights(wins, concerns)
