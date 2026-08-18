"""Página: Google Analytics 4 — tráfico de las 5 landings WeRise, por programa."""
from __future__ import annotations

import streamlit as st

from src import config
from src.data import loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, num, pct

st.set_page_config(page_title="Google Analytics · UVic", page_icon="📈", layout="wide")
aplicar_tema()

desde, hasta, etiqueta = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes, datos.detalles)

ui.cabecera("Google Analytics 4",
            f"Tráfico de las 5 landings WeRise · {etiqueta}")

df = datos.ga4
if df.empty:
    st.warning("No hay datos de GA4.")
    st.stop()

t_ses = metrics.tendencia(df, "sesiones", "fecha")

# Totales exactos del periodo (consulta sin fecha); fallback a sumas diarias.
if not datos.ga4_resumen.empty:
    res = datos.ga4_resumen.iloc[0]
    tot_ses = int(res["sesiones"]); tot_usr = int(res["usuarios"])
    nuevos = int(res["usuarios_nuevos"]); tot_vis = int(res["vistas"])
    engagement = float(res["engagement"]); duracion = float(res["duracion_media"])
    conversiones = int(res["eventos_clave"])
else:
    tot_ses = int(df["sesiones"].sum()); tot_usr = int(df["usuarios"].sum())
    nuevos = 0; tot_vis = int(df["vistas"].sum()) if "vistas" in df else 0
    engagement = 1 - (df["rebote"].mean() if "rebote" in df else 0)
    w = df["sesiones"].sum()
    duracion = float((df["duracion_media"] * df["sesiones"]).sum() / w) if w else 0
    conversiones = int(datos.ga4_fuente["eventos_clave"].sum()) if not datos.ga4_fuente.empty else 0

pct_nuevos = nuevos / tot_usr if tot_usr else 0
pags_ses = tot_vis / tot_ses if tot_ses else 0
tasa_conv = conversiones / tot_ses if tot_ses else 0
dur_fmt = f"{int(duracion // 60)}m {int(duracion % 60):02d}s"

st.subheader("Adquisición")
c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Sesiones", num(tot_ses), delta=t_ses["delta"], delta_bueno=True)
ui.kpi(c2, "Usuarios", num(tot_usr), f"{num(nuevos)} nuevos" if nuevos else "Únicos")
ui.kpi(c3, "% Usuarios nuevos", pct(pct_nuevos), "Nuevos / totales")
ui.kpi(c4, "Páginas / sesión", f"{pags_ses:.2f}".replace(".", ","), "Profundidad de visita")

st.subheader("Engagement y conversión")
c5, c6, c7, c8 = st.columns(4)
ui.kpi(c5, "Tasa de engagement", pct(engagement), "Sesiones con interacción",
       estado=config.estado_bench("rebote", 1 - engagement))
ui.kpi(c6, "Duración media sesión", dur_fmt, "Por sesión")
ui.kpi(c7, "Conversiones", num(conversiones), "Eventos clave (key events)",
       estado="ok" if conversiones > 0 else "off")
ui.kpi(c8, "Tasa de conversión", pct(tasa_conv, 2), "Conversiones / sesiones")

por_prog = df.groupby("programa", as_index=False).agg(
    sesiones=("sesiones", "sum"), rebote=("rebote", "mean"))

st.divider()

st.subheader("Sesiones diarias por programa")
serie = df.groupby(["fecha", "programa"], as_index=False)["sesiones"].sum()
ui.linea_temporal(serie, x="fecha", y="sesiones", color="programa", titulo="", y_label="Sesiones")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Sesiones por programa")
    ui.barras(por_prog.sort_values("sesiones"), x="sesiones", y="programa",
              color=None, titulo="", orientacion="h")
with col_b:
    st.subheader("Reparto de tráfico")
    ui.donut(por_prog, nombres="programa", valores="sesiones", titulo="")

st.subheader("Detalle por landing")
detalle = df.groupby(["programa", "landing"], as_index=False).agg(
    sesiones=("sesiones", "sum"),
    usuarios=("usuarios", "sum"),
    vistas=("vistas", "sum"),
    rebote=("rebote", "mean"),
    duracion_media=("duracion_media", "mean"),
).sort_values("sesiones", ascending=False)
detalle["rebote"] = (detalle["rebote"] * 100).round(1)  # ratio -> %
# Ruta clickable → URL completa de la landing (se abre en otra pestaña).
detalle["landing"] = config.LANDING_BASE_URL + detalle["landing"]
ui.tabla_totales(
    detalle,
    columnas=["programa", "landing", "sesiones", "usuarios", "vistas", "rebote", "duracion_media"],
    sum_cols=["sesiones", "usuarios", "vistas"],
    weighted=["rebote", "duracion_media"], weight_col="sesiones",
    column_config={
        "programa": "Programa",
        "landing": st.column_config.LinkColumn(
            "Landing (ruta)", display_text=r"https://cloud\.info-uvic\.cat(/.*)"),
        "sesiones": st.column_config.NumberColumn("Sesiones", format="%d"),
        "usuarios": st.column_config.NumberColumn("Usuarios", format="%d"),
        "vistas": st.column_config.NumberColumn("Páginas vistas", format="%d"),
        "rebote": st.column_config.NumberColumn("Rebote", format="%.1f%%"),
        "duracion_media": st.column_config.NumberColumn("Dur. media (s)", format="%.0f"),
    },
)
st.caption(
    "Solo tráfico de las landings de programa en `cloud.info-uvic.cat` (haz clic en la ruta para "
    "abrir la landing). Los leads/conversiones se miden en HubSpot (página *Leads*)."
)

st.divider()

# --- Tráfico por fuente / medio --------------------------------------------- #
st.subheader("Detalle por fuente / medio")
fm = datos.ga4_fuente
if fm.empty:
    st.info("Sin datos de fuente/medio.")
else:
    ui.tabla_totales(
        fm,
        columnas=["fuente", "medio", "sesiones", "usuarios", "eventos", "eventos_clave"],
        sum_cols=["sesiones", "usuarios", "eventos", "eventos_clave"],
        column_config={
            "fuente": "Fuente", "medio": "Medio",
            "sesiones": st.column_config.NumberColumn("Sesiones", format="%d"),
            "usuarios": st.column_config.NumberColumn("Usuarios", format="%d"),
            "eventos": st.column_config.NumberColumn("Eventos", format="%d"),
            "eventos_clave": st.column_config.NumberColumn("Eventos clave", format="%d"),
        },
    )

# --- Tráfico por campaña ---------------------------------------------------- #
st.subheader("Detalle por campaña")
cg = datos.ga4_campana
if cg.empty:
    st.info("Sin datos de campaña.")
else:
    cg = cg.copy()
    cg["programa"] = cg["campana"].map(config.programa_por_campana)
    _mets = dict(sesiones=("sesiones", "sum"), usuarios=("usuarios", "sum"),
                 eventos=("eventos", "sum"), eventos_clave=("eventos_clave", "sum"))
    modo = st.radio("Agrupar por", ["Programa", "Campaña (UTM)"], horizontal=True,
                    help="Las UTM llegan con formatos distintos (guiones, acentos, +, castellano/català…) "
                         "y GA4 fragmenta la misma campaña. 'Programa' consolida todas las variantes.")
    if modo == "Programa":
        # Consolida TODAS las variantes por programa (la clave más robusta).
        cons = cg.groupby("programa", as_index=False).agg(**_mets).sort_values(
            "sesiones", ascending=False)
        ui.tabla_totales(
            cons,
            columnas=["programa", "sesiones", "usuarios", "eventos", "eventos_clave"],
            sum_cols=["sesiones", "usuarios", "eventos", "eventos_clave"],
            column_config={
                "programa": "Programa",
                "sesiones": st.column_config.NumberColumn("Sesiones", format="%d"),
                "usuarios": st.column_config.NumberColumn("Usuarios", format="%d"),
                "eventos": st.column_config.NumberColumn("Eventos", format="%d"),
                "eventos_clave": st.column_config.NumberColumn("Eventos clave", format="%d"),
            },
        )
    else:
        # Detalle por campaña, deduplicando variantes idénticas (clave normalizada)
        # y etiquetando cada una con su programa. Con filtros de fuente y campaña.
        cg["_k"] = cg["campana"].map(config.clave_campana)
        _rep = (cg.sort_values("sesiones", ascending=False)
                .groupby("_k", as_index=False).first()[["_k", "campana", "programa", "fuente"]])
        _ag = cg.groupby("_k", as_index=False).agg(**_mets)
        det = _rep.merge(_ag, on="_k").drop(columns="_k").sort_values(
            ["programa", "sesiones"], ascending=[True, False])
        fcol1, fcol2 = st.columns(2)
        fuentes = sorted(det["fuente"].dropna().unique())
        sel_f = fcol1.multiselect("Filtrar por fuente", fuentes, placeholder="Todas las fuentes")
        det_f = det[det["fuente"].isin(sel_f)] if sel_f else det
        campanas = sorted(det_f["campana"].dropna().unique())
        sel_c = fcol2.multiselect("Filtrar por campaña", campanas, placeholder="Todas las campañas")
        if sel_c:
            det_f = det_f[det_f["campana"].isin(sel_c)]
        ui.tabla_totales(
            det_f,
            columnas=["programa", "campana", "fuente", "sesiones", "usuarios", "eventos", "eventos_clave"],
            sum_cols=["sesiones", "usuarios", "eventos", "eventos_clave"],
            column_config={
                "programa": "Programa", "fuente": "Fuente", "campana": "Campaña (UTM)",
                "sesiones": st.column_config.NumberColumn("Sesiones", format="%d"),
                "usuarios": st.column_config.NumberColumn("Usuarios", format="%d"),
                "eventos": st.column_config.NumberColumn("Eventos", format="%d"),
                "eventos_clave": st.column_config.NumberColumn("Eventos clave", format="%d"),
            },
        )
st.caption(
    "**Eventos** = total de interacciones registradas. **Eventos clave** = los marcados como conversión "
    "en GA4. Vista **Programa** = consolida todas las variantes de UTM de un mismo programa; vista "
    "**Campaña (UTM)** = una fila por campaña (variantes idénticas ya unificadas). Filtrado a las landings WeRise."
)

st.divider()

# --- LEAD vs form_submit por campaña WeRise ---------------------------------- #
st.subheader("Eventos clave por campaña: LEAD vs form_submit")
st.caption(
    "Comparativa de los dos eventos marcados como conversión, solo campañas **WeRise**. "
    "Sirve para detectar dónde falla cada tag antes de decidir cuál es el evento real."
)
ev = datos.ga4_eventos
if ev.empty:
    st.info("Sin datos de eventos por campaña.")
else:
    cols_ev = [c for c in config.GA4_EVENTOS_CLAVE if c in ev.columns]
    ui.tabla_totales(
        ev,
        columnas=["campana", *cols_ev],
        sum_cols=cols_ev,
        column_config={
            "campana": "Campaña",
            **{c: st.column_config.NumberColumn(c, format="%d") for c in cols_ev},
        },
    )
    # Diagnóstico automático: campañas donde uno de los eventos no dispara.
    avisos = []
    for c in cols_ev:
        rotas = ev[ev[c] == 0]["campana"].tolist()
        if rotas:
            avisos.append(f"**{c}** no registra nada en: {', '.join(rotas)}.")
    if avisos:
        st.warning("⚠️ " + " · ".join(avisos) + " Revisa el tag en esa(s) landing(s).")

st.divider()

# --- Insights del periodo (siempre al final, tras los gráficos) --------------- #
st.subheader("Insights del periodo")
wins, concerns = [], []
if not por_prog.empty:
    top = por_prog.sort_values("sesiones", ascending=False).iloc[0]
    wins.append(f"Landing con más tráfico: **{top['programa']}** ({num(int(top['sesiones']))} sesiones).")
    peor = por_prog.sort_values("rebote", ascending=False).iloc[0]
    if config.estado_bench("rebote", peor["rebote"]) == "off":
        concerns.append(f"Rebote alto en **{peor['programa']}** ({pct(peor['rebote'])}): revisa coherencia anuncio→landing, velocidad y CTA.")
ui.caja_insights(wins, concerns)
