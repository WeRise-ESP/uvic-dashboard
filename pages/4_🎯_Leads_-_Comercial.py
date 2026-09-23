"""Página: Leads - Comercial — leads UVic por programa, CPL, embudo, pipeline y tasas."""
from __future__ import annotations

import pandas as pd
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
_vista_pipe = st.radio(
    "Vista del pipeline", ["Tablero completo (hoy)", "Solo el periodo seleccionado"],
    horizontal=True, label_visibility="collapsed", key="vista_pipeline",
)
if _vista_pipe.startswith("Tablero"):
    _pipe_df, _pipe_origen, _pipe_detalle = loader.cargar_pipeline_actual()
    if _pipe_origen != "api":
        st.warning(f"No se pudo leer el tablero de HubSpot · {_pipe_detalle}")
    st.caption(
        "Dónde está **ahora** cada negocio del *Pipeline UVIC*, **sin filtro de fechas**: "
        "cuadra 1:1 con el tablero de HubSpot. Un negocio abierto hace meses sigue "
        "contando en su etapa actual."
    )
else:
    _pipe_df = deals
    st.caption(
        f"Solo los negocios del periodo **{etiqueta}** (cerrados por fecha de cierre, "
        "abiertos por fecha de creación). Los negocios creados antes del periodo y aún "
        "abiertos **no** aparecen aquí; para verlos, usa el tablero completo."
    )
pipe_et = metrics.pipeline_por_etapa(_pipe_df)
if pipe_et.empty:
    st.info("Sin negocios en el pipeline.")
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
# Desglose por programa: captación y actividad comercial del periodo
# --------------------------------------------------------------------------- #
st.subheader("Captación y actividad comercial por programa")
_act, _act_origen = loader.cargar_actividad_programa(desde, hasta)
if _act is None:
    st.warning(f"No se pudo leer la actividad comercial de HubSpot · {_act_origen}")
else:
    _comerciales = " y ".join(config.HUBSPOT_OWNERS_UVIC.values())
    _t = _act["totales"]
    st.caption(
        f"Periodo **{etiqueta}**. Los **leads** se cuentan por fecha de creación; las "
        f"**actividades** por su propia fecha, y solo las de leads UVic (cartera de "
        f"{_comerciales}: {num(_t['cartera'])} contactos con `uvic_curso`). "
        "Una actividad de un lead captado antes del periodo cuenta igual, porque el "
        "trabajo comercial se hizo dentro del periodo."
    )

    a1, a2, a3, a4, a5 = st.columns(5)
    ui.kpi(a1, "Leads del periodo", num(_t["leads"]), "Altas con `uvic_curso`")
    ui.kpi(a2, "Intentos de contacto", num(_t["intentos"]),
           f"{num(_t['intentos']/_t['leads'],1) if _t['leads'] else 0} por lead")
    ui.kpi(a3, "Llamadas", num(_t["llamadas"]),
           f"{pct(_act['llamadas']['tasa'],1)} conectadas",
           estado="ok" if _act["llamadas"]["tasa"] >= 0.3 else "warn")
    ui.kpi(a4, "Emails", num(_t["emails"]), "Enviados en el periodo")
    ui.kpi(a5, "Reuniones y tareas", num(_t["reuniones"] + _t["tareas"]),
           f"{num(_t['reuniones'])} reuniones · {num(_t['tareas'])} tareas")

    # --- Tabla maestra: captación + actividad, por programa ------------------ #
    _lp = _act["leads_prog"]
    _ap = _act["act_prog"]
    tabla_prog = _ap.merge(_lp, on="programa", how="outer").fillna(0)
    for _c in ("leads", "intentos", "sin_contactar", "llamadas", "emails",
               "reuniones", "tareas", "actividades"):
        if _c in tabla_prog.columns:
            tabla_prog[_c] = tabla_prog[_c].astype(int)
    tabla_prog["act_por_lead"] = tabla_prog.apply(
        lambda r: r["actividades"] / r["leads"] if r["leads"] else 0, axis=1).round(1)
    tabla_prog = tabla_prog.sort_values("leads", ascending=False)

    ui.tabla_totales(
        tabla_prog,
        columnas=["programa", "leads", "intentos", "media_intentos", "sin_contactar",
                  "llamadas", "emails", "reuniones", "tareas", "actividades",
                  "act_por_lead"],
        sum_cols=["leads", "intentos", "sin_contactar", "llamadas", "emails",
                  "reuniones", "tareas", "actividades"],
        ratios={
            "media_intentos": ("intentos", "leads", 1, ""),
            "act_por_lead": ("actividades", "leads", 1, ""),
        },
        column_config={
            "programa": "Programa",
            "leads": st.column_config.NumberColumn("Leads", format="%d"),
            "intentos": st.column_config.NumberColumn("Intentos", format="%d"),
            "media_intentos": st.column_config.NumberColumn("Intentos/lead", format="%.2f"),
            "sin_contactar": st.column_config.NumberColumn("Sin contactar", format="%d"),
            "llamadas": st.column_config.NumberColumn("Llamadas", format="%d"),
            "emails": st.column_config.NumberColumn("Emails", format="%d"),
            "reuniones": st.column_config.NumberColumn("Reuniones", format="%d"),
            "tareas": st.column_config.NumberColumn("Tareas", format="%d"),
            "actividades": st.column_config.NumberColumn("Actividades", format="%d"),
            "act_por_lead": st.column_config.NumberColumn("Activ./lead", format="%.1f"),
        },
    )
    st.caption(
        "**Intentos** = `num_contacted_notes` de los leads captados en el periodo. "
        "**Actividades** = llamadas, emails, reuniones y tareas registradas en el "
        "periodo sobre leads UVic."
    )

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown("**Leads captados por programa**")
        _g = tabla_prog[tabla_prog["leads"] > 0][["programa", "leads"]]
        if _g.empty:
            st.info("Sin leads en el periodo.")
        else:
            ui.barras_horizontales(_g.sort_values("leads", ascending=False),
                                   "programa", "leads", x_label="Leads")
    with col_p2:
        st.markdown("**Actividades por programa**")
        _g2 = tabla_prog[tabla_prog["actividades"] > 0][["programa", "actividades"]]
        if _g2.empty:
            st.info("Sin actividad en el periodo.")
        else:
            ui.barras_horizontales(_g2.sort_values("actividades", ascending=False),
                                   "programa", "actividades", x_label="Actividades")

    # --- Llamadas por resultado --------------------------------------------- #
    _res = _act["llamadas"]["por_resultado"]
    if _res:
        col_r1, col_r2 = st.columns([0.45, 0.55])
        with col_r1:
            st.markdown("**Resultado de las llamadas**")
            _dfr = (pd.DataFrame([{"resultado": k, "llamadas": v} for k, v in _res.items()])
                    .sort_values("llamadas", ascending=False))
            ui.tabla_totales(
                _dfr, columnas=["resultado", "llamadas"], sum_cols=["llamadas"],
                column_config={
                    "resultado": "Resultado",
                    "llamadas": st.column_config.NumberColumn("Llamadas", format="%d"),
                },
            )
        with col_r2:
            st.markdown("**Duración media de llamada**")
            st.metric("Segundos por llamada conectada",
                      f"{_act['llamadas']['dur_media']:.0f} s")
            st.caption(
                f"{num(_act['llamadas']['conectadas'])} llamadas conectadas de "
                f"{num(_act['llamadas']['total'])} ({pct(_act['llamadas']['tasa'],1)})."
            )

    # --- Detalle por lead ---------------------------------------------------- #
    _det = _act["detalle"]
    if not _det.empty:
        with st.expander(f"Detalle de los {len(_det)} leads del periodo", expanded=False):
            _progs = ["Todos"] + sorted(_det["programa"].unique().tolist())
            _sel = st.selectbox("Programa", _progs, key="prog_detalle_act")
            _d = _det if _sel == "Todos" else _det[_det["programa"] == _sel]
            st.dataframe(
                _d[["nombre", "email", "programa", "comercial", "fecha_creacion",
                    "intentos", "ult_contacto", "estado"]]
                .sort_values("intentos", ascending=False),
                width="stretch", hide_index=True,
                column_config={
                    "nombre": "Lead", "email": "Email", "programa": "Programa",
                    "comercial": "Propietario",
                    "fecha_creacion": st.column_config.DateColumn("Alta", format="DD/MM/YYYY"),
                    "intentos": st.column_config.NumberColumn("Intentos", format="%d"),
                    "ult_contacto": st.column_config.DateColumn("Últ. contacto", format="DD/MM/YYYY"),
                    "estado": "Estado",
                },
            )

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
