"""Página: detalle de Meta Ads (social) — con benchmarks, tendencia e insights."""
from __future__ import annotations

import streamlit as st

from src import config
from src.data import loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, eur, num, pct

st.set_page_config(page_title="Meta Ads · UVic", page_icon="📱", layout="wide")
aplicar_tema()

desde, hasta, etiqueta = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes, datos.detalles)

ui.cabecera("Meta Ads", f"Cuenta {config.META_AD_ACCOUNT_ID} · social WeRise · {etiqueta}")

# --- Ámbito de las campañas -------------------------------------------------- #
_todas = datos.meta_todas if not datos.meta_todas.empty else datos.meta
_n_todas = _todas["campana"].nunique() if not _todas.empty else 0
_n_werise = (_todas[_todas["es_werise"]]["campana"].nunique()
             if not _todas.empty and "es_werise" in _todas.columns else 0)
_ambito = st.radio(
    "Ámbito",
    [f"Campañas WeRise ({_n_werise})", f"Toda la cuenta ({_n_todas})"],
    horizontal=True, label_visibility="collapsed", key="ambito_meta",
)
_solo_werise = _ambito.startswith("Campañas WeRise")
df = datos.meta if _solo_werise else _todas
if df.empty:
    st.warning("No hay datos de Meta Ads.")
    st.stop()
if not _solo_werise:
    st.caption(
        "Mostrando **todas las campañas** de la cuenta, incluidas las que no son de "
        "WeRise (grados, másteres oficiales…). Esas campañas no tienen leads en "
        "HubSpot, así que el CPL real y la comparativa de medición solo son válidos "
        "para el ámbito WeRise."
    )

r = metrics.resumen_plataforma(df).iloc[0]
t_inv = metrics.tendencia(df, "coste", "fecha")
resultados = int(r["conversiones"])                       # leads web atribuidos por Meta
tasa_resultados = resultados / r["clics"] if r["clics"] else 0
coste_resultado = r["coste"] / resultados if resultados else 0

# CPL real: eventos clave de GA4 llegados desde fuentes Meta (meta/fb/ig/an).
_FUENTES_META = {"meta", "fb", "ig", "an", "facebook", "instagram"}
ev_meta = 0
gf = datos.ga4_fuente
if not gf.empty and "fuente" in gf.columns and "eventos_clave" in gf.columns:
    ev_meta = int(gf[gf["fuente"].str.lower().isin(_FUENTES_META)]["eventos_clave"].sum())
cpl_real = r["coste"] / ev_meta if ev_meta else 0

st.subheader("Volumen y coste")
c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Inversión", eur(r["coste"]), delta=t_inv["delta"], delta_bueno=True)
ui.kpi(c2, "Impresiones", num(r["impresiones"]), "Alcance social")
ui.kpi(c3, "Clics", num(r["clics"]), f"CTR {pct(r['ctr'],2)}",
       estado=config.estado_bench("ctr_social", r["ctr"]))
ui.kpi(c4, "CPM", eur(r["cpm"], 2), f"Benchmark ≤ {eur(config.BENCH['cpm_social']['ok'],1)}",
       estado=config.estado_bench("cpm_social", r["cpm"]))

st.subheader("Eficiencia y resultado")
c5, c6, c7, c8 = st.columns(4)
ui.kpi(c5, "CPC medio", eur(r["cpc"], 2), f"Benchmark ≤ {eur(config.BENCH['cpc_social']['ok'],2)}",
       estado=config.estado_bench("cpc_social", r["cpc"]))
ui.kpi(c6, "Resultados (leads web)", num(resultados),
       f"Tasa {pct(tasa_resultados,2)} sobre clics",
       estado="ok" if resultados > 0 else "off")
ui.kpi(c7, "Coste/resultado", eur(coste_resultado, 2) if resultados else "—",
       "Inversión / resultados Meta",
       estado=config.estado_bench("cpl", coste_resultado) if resultados else "off")
# Leads reales en HubSpot con UTM de Meta (uvic_utm_source in ig/fb/facebook/meta).
leads_meta_hs = datos.leads[datos.leads["fuente"] == "Meta"] if "fuente" in datos.leads else datos.leads.iloc[0:0]
n_leads_hs = len(leads_meta_hs)
cpl_hs = r["coste"] / n_leads_hs if n_leads_hs else 0
ui.kpi(c8, "CPL real (HubSpot)", eur(cpl_hs, 2) if n_leads_hs else "—",
       f"{num(n_leads_hs)} leads con UTM de Meta",
       estado=config.estado_bench("cpl", cpl_hs) if n_leads_hs else None)

# --- Métricas de alcance y comportamiento ------------------------------------ #
_alc = int(df["alcance"].max()) if "alcance" in df.columns and not df.empty else 0
_frec = float(df["frecuencia"].mean()) if "frecuencia" in df.columns and not df.empty else 0.0
_cenl = int(df["clics_enlace"].sum()) if "clics_enlace" in df.columns else 0
_vlp = int(df["vistas_landing"].sum()) if "vistas_landing" in df.columns else 0
_nat = int(df["leads_nativos"].sum()) if "leads_nativos" in df.columns else 0
_inter = int(df["interacciones"].sum()) if "interacciones" in df.columns else 0
_repro = int(df["reproducciones"].sum()) if "reproducciones" in df.columns else 0
st.subheader("Alcance y comportamiento")
c9, c10, c11, c12 = st.columns(4)
ui.kpi(c9, "Alcance", num(_alc), "Personas distintas (máx. diario)")
ui.kpi(c10, "Frecuencia media", f"{_frec:.2f}",
       "Impactos por persona · >3 indica fatiga",
       estado="off" if _frec >= 3 else "ok" if _frec else None)
ui.kpi(c11, "Clics en el enlace", num(_cenl),
       f"{pct(_cenl/r['clics'] if r['clics'] else 0,1)} de los clics")
ui.kpi(c12, "Vistas de la landing", num(_vlp),
       f"{pct(_vlp/_cenl if _cenl else 0,1)} de los clics en el enlace llegan",
       estado="off" if _cenl and _vlp/_cenl < 0.5 else "ok" if _vlp else None)
c13, c14, c15, c16 = st.columns(4)
ui.kpi(c13, "Leads en formulario nativo", num(_nat), "Formularios instantáneos de Meta")
ui.kpi(c14, "Interacciones", num(_inter), "Post engagement")
ui.kpi(c15, "Reproducciones de vídeo", num(_repro), "Video views")
ui.kpi(c16, "Clics únicos", num(int(df["clics_unicos"].sum()) if "clics_unicos" in df.columns else 0),
       "Personas distintas que hicieron clic")

if resultados == 0:
    st.warning(
        f"Meta no está atribuyendo conversiones pese a que HubSpot registra "
        f"**{num(len(datos.leads))} leads UVic**. Revisa la página *Tracking & Atribución*."
    )
else:
    st.caption(
        f"Las 3 mediciones · Meta atribuye **{num(resultados)}** leads web · GA4 registra "
        f"**{num(ev_meta)}** eventos clave de fuentes Meta (CPL {eur(cpl_real,2) if ev_meta else '—'}) · "
        f"HubSpot tiene **{num(n_leads_hs)}** leads con UTM de Meta de {num(len(datos.leads))} totales."
    )

# --- Comparativa de medición por campaña ------------------------------------- #
st.subheader("Comparativa de medición por campaña")
st.caption("Resultados según cada fuente: Meta (plataforma) · HubSpot (leads con `uvic_utm_campaign`) · GA4 (eventos clave de fuentes meta/fb/ig).")
_mm = df.groupby("campana")["conversiones"].sum().astype(int)
# Emparejar leads↔campaña por clave normalizada (tolera mayúsculas/separadores en la UTM).
_lh = {}
if n_leads_hs:
    _tmp = leads_meta_hs.copy()
    _tmp["_k"] = _tmp["campana"].map(config.clave_agrupacion_campana)
    _lh = _tmp.groupby("_k").size().to_dict()
_gm = datos.ga4_campana
# Eventos GA4 por campaña, emparejados por clave normalizada (igual que los leads).
_gv = {}
if not _gm.empty and {"fuente", "campana", "eventos_clave"}.issubset(_gm.columns):
    _g = _gm[_gm["fuente"].str.lower().isin(_FUENTES_META)].copy()
    _g["_k"] = _g["campana"].map(config.clave_agrupacion_campana)
    _gv = _g.groupby("_k")["eventos_clave"].sum().to_dict()
_comp = []
for camp in _mm.index:
    _comp.append(dict(
        campana=camp,
        resultados_meta=int(_mm.get(camp, 0)),
        leads_hubspot=int(_lh.get(config.clave_agrupacion_campana(camp), 0)),
        eventos_ga4=int(_gv.get(config.clave_agrupacion_campana(camp), 0)),
    ))
import pandas as _pd
ui.tabla_totales(
    _pd.DataFrame(_comp),
    columnas=["campana", "resultados_meta", "leads_hubspot", "eventos_ga4"],
    sum_cols=["resultados_meta", "leads_hubspot", "eventos_ga4"],
    column_config={
        "campana": "Campaña",
        "resultados_meta": st.column_config.NumberColumn("Resultados Meta", format="%d"),
        "leads_hubspot": st.column_config.NumberColumn("Leads HubSpot (UTM)", format="%d"),
        "eventos_ga4": st.column_config.NumberColumn("Eventos clave GA4", format="%d"),
    },
)

# --- Comparativa de medición por campaña y grupo de anuncios ----------------- #
st.subheader("Comparativa de medición por campaña y grupo de anuncios")
_ads = datos.meta_adsets
if _solo_werise and not _ads.empty and "es_werise" in _ads.columns:
    _ads = _ads[_ads["es_werise"]]
if _ads.empty:
    st.info("Sin datos de grupos de anuncios para el periodo.")
else:
    # GA4: Meta rellena utm_content con el ID del grupo en la mayoría de campañas,
    # así que emparejamos por ID y, si no, por nombre del grupo.
    _ga = datos.ga4_adset
    _ev_id, _ev_nom = {}, {}
    if not _ga.empty and {"contenido", "eventos_clave"}.issubset(_ga.columns):
        _gm = _ga[_ga["fuente"].str.lower().isin(_FUENTES_META)] if "fuente" in _ga.columns else _ga
        for _, _r in _gm.iterrows():
            _k = str(_r["contenido"]).strip()
            _ev_id[_k] = _ev_id.get(_k, 0) + int(_r["eventos_clave"])
            _ev_nom[_k.lower()] = _ev_nom.get(_k.lower(), 0) + int(_r["eventos_clave"])

    # HubSpot no guarda utm_content, así que solo se puede atribuir el lead al
    # grupo cuando la campaña tiene un único grupo con gasto: en el resto, "—".
    _grupos_por_camp = _ads[_ads["coste"] > 0].groupby("campana")["grupo"].nunique().to_dict()

    _filas = []
    for _, _r in _ads.sort_values("coste", ascending=False).iterrows():
        _c = _r["campana"]
        _clave = config.clave_agrupacion_campana(_c)
        _leads_camp = _lh.get(_clave, 0)
        _unico = _grupos_por_camp.get(_c, 0) == 1 and _r["coste"] > 0
        _ga4 = _ev_id.get(str(_r["grupo_id"]), _ev_nom.get(str(_r["grupo"]).lower(), 0))
        _filas.append(dict(
            campana=_c, grupo=_r["grupo"],
            coste=_r["coste"], resultados_meta=int(_r["conversiones"]),
            leads_hubspot=(int(_leads_camp) if _unico else None),
            eventos_ga4=int(_ga4),
            clics_enlace=int(_r["clics_enlace"]), frecuencia=_r["frecuencia"],
            cpl_meta=_r["cpl"],
        ))
    _df_ads = _pd.DataFrame(_filas)
    ui.tabla_totales(
        _df_ads,
        columnas=["campana", "grupo", "coste", "clics_enlace", "frecuencia",
                  "resultados_meta", "cpl_meta", "leads_hubspot", "eventos_ga4"],
        sum_cols=["coste", "clics_enlace", "resultados_meta", "leads_hubspot", "eventos_ga4"],
        ratios={"cpl_meta": ("coste", "resultados_meta", 1, " €")},
        column_config={
            "campana": "Campaña",
            "grupo": "Grupo de anuncios",
            "coste": st.column_config.NumberColumn("Inversión", format="%.2f €"),
            "clics_enlace": st.column_config.NumberColumn("Clics enlace", format="%d"),
            "frecuencia": st.column_config.NumberColumn("Frec.", format="%.2f"),
            "resultados_meta": st.column_config.NumberColumn("Resultados Meta", format="%d"),
            "cpl_meta": st.column_config.NumberColumn("CPL Meta", format="%.2f €"),
            "leads_hubspot": st.column_config.NumberColumn("Leads HubSpot (UTM)", format="%d"),
            "eventos_ga4": st.column_config.NumberColumn("Eventos clave GA4", format="%d"),
        },
    )
    st.caption(
        "**Leads HubSpot** solo puede atribuirse al grupo cuando la campaña tiene un "
        "único grupo activo: HubSpot guarda `utm_campaign` pero no `utm_content`, así "
        "que en campañas con varios grupos aparece vacío (el total sí está en la tabla "
        "por campaña). **Eventos GA4** se emparejan por el `utm_content` que Meta "
        "rellena con el ID del grupo."
    )

camp = metrics.resumen_campana(df)

st.divider()

st.subheader("Inversión y clics diarios")
serie = df.groupby("fecha", as_index=False).agg(coste=("coste", "sum"), clics=("clics", "sum"))
ui.linea_temporal(serie, x="fecha", y="coste", color=None, titulo="Inversión €/día", y_label="€")

st.subheader("Rendimiento por campaña")
ui.barras(camp, x="coste", y="campana", color="programa",
          titulo="Inversión por campaña", orientacion="h")
_cols_base = ["campana", "programa", "impresiones", "clics", "ctr", "cpc", "coste", "conversiones"]
if "estado" in camp.columns:
    _cols_base.insert(1, "estado")
tab = camp[_cols_base].copy()
tab["ctr"] = (tab["ctr"] * 100).round(2)  # ratio -> %
tab["cpl_meta"] = tab.apply(
    lambda r: r["coste"] / r["conversiones"] if r["conversiones"] else 0, axis=1)
tab["leads_hubspot"] = tab["campana"].map(
    lambda c: _lh.get(config.clave_agrupacion_campana(c), 0)).astype(int)
_cols_tab = ["campana", "programa", "impresiones", "clics", "ctr", "cpc", "coste",
             "conversiones", "cpl_meta", "leads_hubspot"]
if "estado" in tab.columns:
    _cols_tab.insert(2, "estado")
ui.tabla_totales(
    tab,
    columnas=_cols_tab,
    sum_cols=["impresiones", "clics", "coste", "conversiones", "leads_hubspot"],
    ratios={
        "ctr": ("clics", "impresiones", 100, "%"),
        "cpc": ("coste", "clics", 1, " €"),
        "cpl_meta": ("coste", "conversiones", 1, " €"),
    },
    column_config={
        "campana": "Campaña", "programa": "Programa", "estado": "Estado",
        "impresiones": st.column_config.NumberColumn("Impr.", format="%d"),
        "clics": st.column_config.NumberColumn("Clics", format="%d"),
        "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
        "cpc": st.column_config.NumberColumn("CPC", format="%.2f €"),
        "coste": st.column_config.NumberColumn("Inversión", format="%.0f €"),
        "conversiones": st.column_config.NumberColumn("Resultados Meta", format="%d"),
        "cpl_meta": st.column_config.NumberColumn("CPL Meta", format="%.2f €"),
        "leads_hubspot": st.column_config.NumberColumn("Leads HubSpot", format="%d"),
    },
)
st.caption(
    "**Resultados Meta** = leads web atribuidos por la plataforma · **CPL Meta** = inversión / "
    "resultados Meta · **Leads HubSpot** = leads reales con `uvic_utm_campaign` de esa campaña."
)

st.divider()

# --- Insights del periodo (siempre al final, tras los gráficos) --------------- #
st.subheader("Insights del periodo")
wins, concerns = [], []
if not camp.empty:
    mejor = camp.sort_values("ctr", ascending=False).iloc[0]
    wins.append(f"Mejor CTR: **{mejor['programa']}** ({pct(mejor['ctr'],2)}, CPC {eur(mejor['cpc'],2)}).")
    caro = camp.sort_values("cpc", ascending=False).iloc[0]
    if config.estado_bench("cpc_social", caro["cpc"]) == "off":
        concerns.append(f"CPC social alto en **{caro['programa']}** ({eur(caro['cpc'],2)}): posible fatiga de creatividad.")
        concerns.append("Refresca creatividades cada 2 semanas para frenar la fatiga (CPM al alza).")
ui.caja_insights(wins, concerns)
