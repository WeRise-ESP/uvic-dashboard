"""Página: Actividad comercial — cómo se han trabajado los leads UVIC.

Todo scoped a UVIC: contactos con `uvic_curso` asignados a Vanina Correa (el
comercial de UVIC), sin importados ni webinar. Las actividades (llamadas, emails,
reuniones, tareas) se cuentan SOLO las asociadas a esos contactos, no las del
portal entero.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import TEMA
from src.data import loader
from src.ui import components as ui
from src.ui.theme import aplicar_tema, badge_origen, num, pct

st.set_page_config(page_title="Actividad · UVic", page_icon="📞", layout="wide")
aplicar_tema()

est, origen = loader.cargar_actividad()

# Sidebar: origen + refresco (esta página es acumulada, no usa filtro de fechas).
st.sidebar.markdown("**Origen de los datos**")
st.sidebar.markdown(f"Actividad HubSpot: {badge_origen(origen)}", unsafe_allow_html=True)
if st.sidebar.button("🔄 Actualizar ahora", width="stretch"):
    st.cache_data.clear()
    st.rerun()

ui.cabecera("Actividad comercial",
            "Cómo se han trabajado los leads UVIC · comercial Vanina Correa")

if not est or est.get("n_leads", 0) == 0:
    st.warning("No hay datos de actividad (revisa la conexión con HubSpot).")
    st.stop()

leads = est["leads"]

# --------------------------------------------------------------------------- #
# Fila A — Gestión de leads (intentos de contacto)
# --------------------------------------------------------------------------- #
st.subheader("Gestión de los leads")
c1, c2, c3, c4, c5 = st.columns(5)
ui.kpi(c1, "Leads UVIC", num(est["n_leads"]), "Contactos de Vanina")
ui.kpi(c2, "Intentos de contacto", num(est["intentos_total"]),
       f"Media {num(est['media_intentos'], 1)}/lead · máx {est['max_intentos']}")
ui.kpi(c3, "Media por lead", num(est["media_intentos"], 1), "Veces contactado")
sin = est["sin_contactar"]
ui.kpi(c4, "Sin contactar", num(sin), f"{pct(sin / est['n_leads'])} de los leads",
       estado="off" if sin else "ok")
frio = est["sin_contacto_7d"]
ui.kpi(c5, "Enfriándose (7+ días)", num(frio), f"{pct(frio / est['n_leads'])} sin contacto reciente",
       estado="off" if frio > est["n_leads"] * 0.4 else "warn")

st.caption(
    "«Intentos de contacto» = veces que el comercial ha registrado un contacto con el lead "
    "(propiedad de HubSpot). Es una vista **acumulada** de toda la base de leads UVIC."
)

st.divider()

# --------------------------------------------------------------------------- #
# Fila B — Actividad por tipo (scoped a UVIC)
# --------------------------------------------------------------------------- #
st.subheader("Actividad registrada (solo leads UVIC)")
a = est["actividades"]
d1, d2, d3, d4 = st.columns(4)
ui.kpi(d1, "📞 Llamadas", num(a.get("calls", 0)))
ui.kpi(d2, "✉️ Emails", num(a.get("emails", 0)))
ui.kpi(d3, "📅 Reuniones", num(a.get("meetings", 0)))
ui.kpi(d4, "✅ Tareas", num(a.get("tasks", 0)))
st.caption(
    "Actividades **asociadas a los contactos UVIC** (no las del portal entero). "
    "El portal tiene mucha más actividad de otros comerciales que aquí queda fuera."
)

st.divider()

# --------------------------------------------------------------------------- #
# Fila C — Detalle de llamadas + distribución de intentos
# --------------------------------------------------------------------------- #
col_izq, col_der = st.columns(2)

with col_izq:
    st.subheader("Llamadas · resultado")
    ll = est["llamadas"]
    k1, k2, k3 = st.columns(3)
    ui.kpi(k1, "Llamadas", num(ll["total"]))
    ui.kpi(k2, "Tasa de conexión", pct(ll["tasa"]),
           f"{num(ll['conectadas'])} conectadas",
           estado="ok" if ll["tasa"] >= 0.3 else ("warn" if ll["tasa"] >= 0.15 else "off"))
    ui.kpi(k3, "Duración media", f"{int(ll['dur_media'] // 60)}m {int(ll['dur_media'] % 60):02d}s",
           "Llamadas conectadas")
    pr = ll["por_resultado"]
    if pr:
        dfp = pd.DataFrame(sorted(pr.items(), key=lambda x: -x[1]), columns=["resultado", "n"])
        ui.donut(dfp, nombres="resultado", valores="n", titulo="")

with col_der:
    st.subheader("Distribución de intentos de contacto")
    bandas = [("0 (sin contactar)", (leads["intentos"] == 0).sum()),
              ("1-2", leads["intentos"].between(1, 2).sum()),
              ("3-5", leads["intentos"].between(3, 5).sum()),
              ("6-10", leads["intentos"].between(6, 10).sum()),
              ("10+", (leads["intentos"] > 10).sum())]
    dfb = pd.DataFrame(bandas, columns=["banda", "leads"])
    dfb["txt"] = dfb["leads"].apply(lambda v: num(v))
    ui.barras_horizontales(dfb, "banda", "leads", texto_col="txt", x_label="Leads")

st.divider()

# --------------------------------------------------------------------------- #
# Fila D — Leads que necesitan seguimiento (accionable)
# --------------------------------------------------------------------------- #
st.subheader("Leads que necesitan seguimiento")
segui = leads.copy()
segui["dias"] = segui["dias_sin_contacto"]
# Nunca contactados primero (dias = None -> 9999), luego los más fríos.
segui["_orden"] = segui["dias"].fillna(9999)
segui = segui[(segui["intentos"] == 0) | (segui["_orden"] >= 7)].sort_values(
    "_orden", ascending=False)
if segui.empty:
    st.success("Todos los leads tienen contacto reciente. 👍")
else:
    st.caption(f"{num(len(segui))} leads sin contactar o sin contacto en 7+ días, "
               "ordenados por los más fríos primero.")
    vista = segui.copy()
    vista["ult_contacto"] = vista["ult_contacto"].astype(str).replace("None", "Nunca")
    vista["dias_txt"] = vista["dias"].apply(lambda v: "Nunca" if pd.isna(v) else f"{int(v)} días")
    st.dataframe(
        vista[["nombre", "programa", "intentos", "actividades", "ult_contacto", "dias_txt", "estado"]],
        width="stretch", hide_index=True,
        column_config={
            "nombre": "Lead", "programa": "Programa",
            "intentos": st.column_config.NumberColumn("Intentos", format="%d"),
            "actividades": st.column_config.NumberColumn("Actividades", format="%d"),
            "ult_contacto": "Último contacto", "dias_txt": "Sin contacto",
            "estado": "Estado",
        },
    )

st.divider()

# --------------------------------------------------------------------------- #
# Fila E — Actividad por programa
# --------------------------------------------------------------------------- #
st.subheader("Actividad por programa")
prog = leads.groupby("programa", as_index=False).agg(
    leads=("nombre", "count"), intentos=("intentos", "sum"), actividades=("actividades", "sum"))
prog["media"] = (prog["intentos"] / prog["leads"]).round(1)
ui.tabla_totales(
    prog.sort_values("leads", ascending=False),
    columnas=["programa", "leads", "intentos", "media", "actividades"],
    sum_cols=["leads", "intentos", "actividades"],
    column_config={
        "programa": "Programa",
        "leads": st.column_config.NumberColumn("Leads", format="%d"),
        "intentos": st.column_config.NumberColumn("Intentos", format="%d"),
        "media": st.column_config.NumberColumn("Media/lead", format="%.1f"),
        "actividades": st.column_config.NumberColumn("Actividades", format="%d"),
    },
)

st.caption(
    "Scope: contactos con `uvic_curso` asignados a **Vanina Correa** (comercial UVIC), sin "
    "importados ni webinar. Los intentos/actividades son acumulados de cada lead."
)
