"""
Conector de HubSpot (CRM API v3/v4) — portal Rise Education (144637943).

Modelo UVic (verificado):
- **Leads UVic** = contactos con la propiedad `uvic_curso` (que mapea a programa).
  La atribución de campaña llega como OFFLINE/INTEGRATION (se pierde el gclid/fbclid),
  así que la asociación lead↔campaña se hace POR PROGRAMA, no por nombre de campaña.
- **Matrícula** = Deal en etapa "Cierre ganado" del Pipeline UVIC (3920516288).

Expone:
- obtener(desde, hasta)       -> ResultadoConector con el DataFrame de leads (contactos).
- obtener_deals(desde, hasta) -> ResultadoConector con el DataFrame de deals (Pipeline UVIC).

Orden de resolución en ambos: API real -> caché -> datos de ejemplo.

Credenciales en .streamlit/secrets.toml:
    [hubspot]
    access_token = "pat-eu1-..."
    portal_id = "144637943"
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src import config
from src.connectors.base import (
    ResultadoConector,
    _leer_secreto,
    guardar_cache,
    leer_cache,
)
from src.data import sample_data

API = "https://api.hubapi.com"

# Resultados de llamada por defecto de HubSpot (fallback si falla el endpoint).
_DISPOSICIONES_DEFAULT = {
    "9d9162e7-6cf3-4944-bf63-4dff82258764": "Ocupado",
    "f240bbac-87c9-4f6e-bf70-924b57d47db7": "Conectado",
    "a4c4c377-d246-4b32-a13b-75a56a4cd0ff": "Dejó mensaje en directo",
    "b2cf5968-551e-4856-9783-52b3da59a7d0": "Buzón de voz",
    "73a0d17f-1163-4015-bdd5-ec830791da20": "Sin respuesta",
    "17b47fee-58de-441e-a44c-c6300d46f273": "Número incorrecto",
}

# Mapeo de lifecyclestage de contacto -> etiqueta de estado del lead.
MAPA_LIFECYCLE = {
    "subscriber": "Suscriptor", "lead": "Lead", "marketingqualifiedlead": "MQL",
    "salesqualifiedlead": "SQL", "opportunity": "Oportunidad",
    "customer": "Matriculado", "evangelist": "Prescriptor", "other": "Otro",
}


# --------------------------------------------------------------------------- #
# Leads (contactos con uvic_curso)
# --------------------------------------------------------------------------- #
def obtener(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("hubspot")
    if creds and creds.get("access_token"):
        try:
            df = _fetch_leads(creds, desde, hasta)
            if df is not None:
                if not df.empty:
                    guardar_cache(df, "hubspot_leads")
                return ResultadoConector(df, "api", "HubSpot (uvic_curso)")
        except Exception as e:  # noqa: BLE001
            cache = leer_cache("hubspot_leads")
            if cache is not None:
                return ResultadoConector(cache, "cache", f"API falló ({e}); caché")

    cache = leer_cache("hubspot_leads")
    if cache is not None and not cache.empty:
        return ResultadoConector(cache, "cache", "Caché local")
    return ResultadoConector(sample_data.hubspot_leads((hasta - desde).days + 1),
                             "sample", "Datos de ejemplo")


def obtener_deals(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("hubspot")
    if creds and creds.get("access_token"):
        try:
            df = _fetch_deals(creds, desde, hasta)
            if df is not None:
                if not df.empty:
                    guardar_cache(df, "hubspot_deals")
                return ResultadoConector(df, "api", "HubSpot Pipeline UVIC")
        except Exception as e:  # noqa: BLE001
            cache = leer_cache("hubspot_deals")
            if cache is not None:
                return ResultadoConector(cache, "cache", f"API falló ({e}); caché")

    cache = leer_cache("hubspot_deals")
    if cache is not None and not cache.empty:
        return ResultadoConector(cache, "cache", "Caché local")
    return ResultadoConector(sample_data.hubspot_deals((hasta - desde).days + 1),
                             "sample", "Datos de ejemplo")


# --------------------------------------------------------------------------- #
# Llamadas a la API
# --------------------------------------------------------------------------- #
def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _rango_ms(desde, hasta) -> tuple[int, int]:
    """(inicio, fin) del rango en milisegundos epoch: desde 00:00 hasta 23:59:59."""
    from datetime import datetime as _dt, time as _time
    ini = int(_dt.combine(desde, _time.min).timestamp() * 1000)
    fin = int(_dt.combine(hasta, _time.max).timestamp() * 1000)
    return ini, fin


def _a_fecha(iso: str):
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc).date()


def _fetch_leads(creds: dict, desde, hasta) -> pd.DataFrame:
    import requests

    token = creds["access_token"]
    ini_ms, fin_ms = _rango_ms(desde, hasta)
    payload = {
        "filterGroups": [{
            "filters": [
                {"propertyName": "uvic_curso", "operator": "HAS_PROPERTY"},
                {"propertyName": "createdate", "operator": "GTE", "value": str(ini_ms)},
                {"propertyName": "createdate", "operator": "LTE", "value": str(fin_ms)},
                # Excluir leads antiguos importados (no son de las campañas actuales).
                {"propertyName": "hs_object_source", "operator": "NEQ", "value": "IMPORT"},
            ]
        }],
        "properties": ["uvic_curso", "uvic_nivel_estudios", "createdate",
                       "lifecyclestage", "hs_lead_status", "hs_analytics_source",
                       "hs_object_source", "hs_analytics_source_data_1",
                       "uvic_utm_source", "uvic_utm_medium", "uvic_utm_campaign"],
        "limit": 100,
    }
    filas, after = [], None
    while True:
        if after:
            payload["after"] = after
        r = requests.post(f"{API}/crm/v3/objects/contacts/search",
                          headers=_headers(token), json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        for c in data.get("results", []):
            p = c.get("properties", {})
            # Segundo filtro (por si el server-side no lo cazó): descartar importados.
            if p.get("hs_object_source") == "IMPORT" or p.get("hs_analytics_source_data_1") == "IMPORT":
                continue
            # Descartar leads de webinar SIN UTMs de ads: van a la hoja de Leads
            # Importados. Si traen ig/ads etc., son leads de campaña y se quedan.
            if config.excluir_webinar(p.get("uvic_utm_campaign"),
                                      p.get("uvic_utm_source"), p.get("uvic_utm_medium")):
                continue
            curso = p.get("uvic_curso") or ""
            estado = MAPA_LIFECYCLE.get((p.get("lifecyclestage") or "").lower(), "Lead")
            utm_source = p.get("uvic_utm_source") or ""
            utm_medium = p.get("uvic_utm_medium") or ""
            filas.append(dict(
                lead_id=c.get("id"),
                fecha_creacion=_a_fecha(p.get("createdate")),
                # Fuente derivada de las UTM propias (uvic_utm_*): Meta/Google/Sin UTM.
                fuente=config.plataforma_por_utm(utm_source, utm_medium),
                utm_source=utm_source,
                utm_medium=utm_medium,
                campana=p.get("uvic_utm_campaign") or "",
                programa=config.programa_por_curso(curso),
                nivel=p.get("uvic_nivel_estudios") or "",
                estado=estado,
                es_matricula=(estado == "Matriculado"),
            ))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return pd.DataFrame(filas)


def _fetch_deals(creds: dict, desde, hasta) -> pd.DataFrame:
    """Deals del Pipeline UVIC + programa (vía contacto asociado y su uvic_curso).

    Un negocio pertenece al periodo por su fecha relevante: los **cerrados**
    (ganado/perdido) por su **fecha de cierre**; los **abiertos** por su **fecha de
    creación**. Así matrículas y cierres perdidos se cuentan cuando ocurrieron y las
    oportunidades abiertas cuando entraron. Se pide el superset (creado O cerrado en
    el periodo) y luego se afina en Python."""
    import requests

    token = creds["access_token"]
    ini_ms, fin_ms = _rango_ms(desde, hasta)
    _pipe = {"propertyName": "pipeline", "operator": "EQ", "value": config.HUBSPOT_PIPELINE_UVIC}
    payload = {
        # OR: creado en el periodo  O  cerrado en el periodo.
        "filterGroups": [
            {"filters": [_pipe,
                         {"propertyName": "createdate", "operator": "GTE", "value": str(ini_ms)},
                         {"propertyName": "createdate", "operator": "LTE", "value": str(fin_ms)}]},
            {"filters": [_pipe,
                         {"propertyName": "closedate", "operator": "GTE", "value": str(ini_ms)},
                         {"propertyName": "closedate", "operator": "LTE", "value": str(fin_ms)}]},
        ],
        "properties": ["dealstage", "amount", "createdate", "closedate", "dealname",
                       config.HUBSPOT_PROP_MOTIVO_PERDIDO],
        "limit": 100,
    }
    deals, after = [], None
    while True:
        if after:
            payload["after"] = after
        r = requests.post(f"{API}/crm/v3/objects/deals/search",
                          headers=_headers(token), json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        deals.extend(data.get("results", []))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break

    # Mapa deal -> {programa, fuente, webinar} vía contacto asociado (best-effort).
    deal_ids = [d["id"] for d in deals]
    info_por_deal = _programa_por_deal(token, deal_ids) if deal_ids else {}

    _cerradas = (config.HUBSPOT_STAGE_MATRICULA, config.HUBSPOT_ETAPA_PERDIDO[0])
    filas = []
    vistos = set()
    for d in deals:
        did = d.get("id")
        if did in vistos:  # el superset OR puede devolver un deal en ambos grupos
            continue
        vistos.add(did)
        info = info_por_deal.get(did, {})
        # Excluir deals de leads de webinar (van a la hoja de Leads Importados).
        if info.get("webinar"):
            continue
        p = d.get("properties", {})
        etapa_id = p.get("dealstage") or ""
        es_perdido = (etapa_id == config.HUBSPOT_ETAPA_PERDIDO[0])
        fcrea = _a_fecha(p.get("createdate"))
        fcierre = _a_fecha(p.get("closedate"))
        # Regla de pertenencia al periodo: cerrado→por cierre; abierto→por creación.
        if etapa_id in _cerradas:
            en_periodo = bool(fcierre and desde <= fcierre <= hasta)
        else:
            en_periodo = bool(fcrea and desde <= fcrea <= hasta)
        if not en_periodo:
            continue
        motivo = (p.get(config.HUBSPOT_PROP_MOTIVO_PERDIDO) or "").strip()
        filas.append(dict(
            deal_id=did,
            fecha_creacion=fcrea,
            fecha_cierre=fcierre,
            etapa_id=etapa_id,
            etapa=config.HUBSPOT_ETAPAS_MAP.get(etapa_id, etapa_id),
            programa=info.get("programa", "Sin asignar"),
            fuente=info.get("fuente", "Sin UTM"),
            amount=float(p.get("amount") or 0),
            es_ganado=(etapa_id == config.HUBSPOT_STAGE_MATRICULA),
            es_perdido=es_perdido,
            motivo_perdido=(motivo or "Sin motivo indicado") if es_perdido else "",
        ))
    return pd.DataFrame(filas)


def _programa_por_deal(token: str, deal_ids: list[str]) -> dict:
    """Asocia cada deal a su contacto y devuelve {deal_id: {programa, webinar}}
    leyendo uvic_curso y uvic_utm_campaign del contacto asociado."""
    import requests

    # 1) deal -> contacto (associations v4 batch)
    try:
        r = requests.post(
            f"{API}/crm/v4/associations/deal/contact/batch/read",
            headers=_headers(token),
            json={"inputs": [{"id": i} for i in deal_ids]}, timeout=60)
        r.raise_for_status()
        res = r.json().get("results", [])
    except Exception:  # noqa: BLE001
        return {}

    deal_to_contact, contact_ids = {}, set()
    for item in res:
        frm = str(item.get("from", {}).get("id"))
        tos = item.get("to", [])
        if tos:
            cid = str(tos[0].get("toObjectId"))
            deal_to_contact[frm] = cid
            contact_ids.add(cid)
    if not contact_ids:
        return {}

    # 2) contacto -> uvic_curso + UTMs (batch read)
    try:
        r = requests.post(
            f"{API}/crm/v3/objects/contacts/batch/read",
            headers=_headers(token),
            json={"properties": ["uvic_curso", "uvic_utm_campaign",
                                 "uvic_utm_source", "uvic_utm_medium"],
                  "inputs": [{"id": c} for c in contact_ids]}, timeout=60)
        r.raise_for_status()
        props_por_contacto = {
            str(c["id"]): c.get("properties", {})
            for c in r.json().get("results", [])
        }
    except Exception:  # noqa: BLE001
        return {}

    out = {}
    for did, cid in deal_to_contact.items():
        p = props_por_contacto.get(cid, {})
        out[did] = dict(
            programa=config.programa_por_curso(p.get("uvic_curso") or ""),
            # Fuente (Meta/Google/Sin UTM) del contacto → permite matrículas por plataforma.
            fuente=config.plataforma_por_utm(p.get("uvic_utm_source"), p.get("uvic_utm_medium")),
            webinar=config.excluir_webinar(p.get("uvic_utm_campaign"),
                                           p.get("uvic_utm_source"), p.get("uvic_utm_medium")),
        )
    return out


# --------------------------------------------------------------------------- #
# Leads IMPORTADOS / WEBINAR (control aparte) — contactos uvic_curso con
# fuente = IMPORT o con uvic_utm_campaign de webinar. Sin filtro de fecha:
# se listan TODOS, y los nuevos que cumplan cualquiera de los dos criterios
# caen aquí solos (y quedan fuera del resto del dashboard).
# --------------------------------------------------------------------------- #
def importados():
    """Devuelve (leads_import_df, negocios_import_df, origen)."""
    creds = _leer_secreto("hubspot")
    if creds and creds.get("access_token"):
        try:
            leads, negocios = _fetch_importados(creds)
            guardar_cache(leads, "hubspot_import_leads")
            guardar_cache(negocios, "hubspot_import_negocios")
            return leads, negocios, "api"
        except Exception:  # noqa: BLE001
            lc = leer_cache("hubspot_import_leads")
            if lc is not None:
                dc = leer_cache("hubspot_import_negocios")
                return lc, (dc if dc is not None else pd.DataFrame()), "cache"

    lc = leer_cache("hubspot_import_leads")
    if lc is not None and not lc.empty:
        dc = leer_cache("hubspot_import_negocios")
        return lc, (dc if dc is not None else pd.DataFrame()), "cache"
    return sample_data.import_leads(), sample_data.import_negocios(), "sample"


def _mapa_etapas_deals(token: str) -> dict:
    """Mapa {stage_id: etiqueta} y {pipeline_id: etiqueta} de todos los pipelines."""
    import requests
    stages, pipelines = {}, {}
    try:
        r = requests.get(f"{API}/crm/v3/pipelines/deals", headers=_headers(token), timeout=60)
        r.raise_for_status()
        for p in r.json().get("results", []):
            pipelines[p["id"]] = p.get("label", p["id"])
            for s in p.get("stages", []):
                stages[s["id"]] = s.get("label", s["id"])
    except Exception:  # noqa: BLE001
        pass
    return {"stages": stages, "pipelines": pipelines}


def _fetch_importados(creds: dict):
    import requests
    token = creds["access_token"]
    mapa = _mapa_etapas_deals(token)

    payload = {
        # Dos grupos = OR: importados clásicos O leads de webinar (por UTM campaign).
        "filterGroups": [
            {"filters": [
                {"propertyName": "uvic_curso", "operator": "HAS_PROPERTY"},
                {"propertyName": "hs_object_source", "operator": "EQ", "value": "IMPORT"},
            ]},
            {"filters": [
                {"propertyName": "uvic_curso", "operator": "HAS_PROPERTY"},
                {"propertyName": "uvic_utm_campaign", "operator": "CONTAINS_TOKEN", "value": "webinar"},
            ]},
        ],
        "properties": ["uvic_curso", "uvic_nivel_estudios", "createdate", "lifecyclestage",
                       "hs_lead_status", "firstname", "lastname", "email", "num_associated_deals",
                       "uvic_utm_campaign", "uvic_utm_source", "uvic_utm_medium",
                       "hs_object_source"],
        "limit": 100,
    }
    contactos, after = [], None
    while True:
        if after:
            payload["after"] = after
        r = requests.post(f"{API}/crm/v3/objects/contacts/search",
                          headers=_headers(token), json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        contactos.extend(data.get("results", []))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break

    filas = []
    for c in contactos:
        p = c.get("properties", {})
        es_import = p.get("hs_object_source") == "IMPORT"
        # Un webinar CON UTMs de ads (p.ej. ig/ads) es lead de campaña: no va aquí
        # (salvo que además sea IMPORT).
        if not es_import and not config.excluir_webinar(
                p.get("uvic_utm_campaign"), p.get("uvic_utm_source"), p.get("uvic_utm_medium")):
            continue
        nombre = f"{p.get('firstname','') or ''} {p.get('lastname','') or ''}".strip()
        filas.append(dict(
            lead_id=c.get("id"),
            nombre=nombre or (p.get("email") or "—"),
            email=p.get("email") or "",
            fecha_creacion=_a_fecha(p.get("createdate")),
            programa=config.programa_por_curso(p.get("uvic_curso") or ""),
            nivel=p.get("uvic_nivel_estudios") or "",
            estado=MAPA_LIFECYCLE.get((p.get("lifecyclestage") or "").lower(), "Lead"),
            lead_status=p.get("hs_lead_status") or "",
            n_negocios=int(p.get("num_associated_deals") or 0),
            campana=p.get("uvic_utm_campaign") or "",
            motivo=("Webinar" if config.es_webinar(p.get("uvic_utm_campaign"))
                    else "Importado"),
        ))
    leads = pd.DataFrame(filas)

    ids = leads["lead_id"].tolist() if not leads.empty else []
    negocios = _negocios_de_contactos(token, ids, mapa)
    return leads, negocios


def _negocios_de_contactos(token: str, contact_ids: list, mapa: dict) -> pd.DataFrame:
    """Negocios (deals) asociados a una lista de contactos, con etapa y pipeline."""
    import requests
    if not contact_ids:
        return pd.DataFrame()

    # contacto -> deals
    deal_to_contact, deal_ids = {}, set()
    try:
        r = requests.post(f"{API}/crm/v4/associations/contact/deal/batch/read",
                          headers=_headers(token),
                          json={"inputs": [{"id": i} for i in contact_ids]}, timeout=60)
        r.raise_for_status()
        for it in r.json().get("results", []):
            frm = str(it.get("from", {}).get("id"))
            for t in it.get("to", []):
                did = str(t.get("toObjectId"))
                deal_ids.add(did)
                deal_to_contact.setdefault(did, frm)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()
    if not deal_ids:
        return pd.DataFrame()

    # deals -> propiedades
    try:
        r = requests.post(f"{API}/crm/v3/objects/deals/batch/read",
                          headers=_headers(token),
                          json={"properties": ["dealname", "dealstage", "pipeline", "amount", "createdate"],
                                "inputs": [{"id": d} for d in deal_ids]}, timeout=60)
        r.raise_for_status()
        res = r.json().get("results", [])
    except Exception:  # noqa: BLE001
        return pd.DataFrame()

    filas = []
    for x in res:
        p = x.get("properties", {})
        filas.append(dict(
            deal_id=x.get("id"),
            contacto=deal_to_contact.get(str(x.get("id"))),
            dealname=p.get("dealname") or "—",
            pipeline=mapa["pipelines"].get(p.get("pipeline"), p.get("pipeline") or "—"),
            etapa=mapa["stages"].get(p.get("dealstage"), p.get("dealstage") or "—"),
            importe=float(p.get("amount") or 0),
            fecha_creacion=_a_fecha(p.get("createdate")),
        ))
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------- #
# INFORME DE ACTIVIDAD — leads UVIC (uvic_curso, comercial Vanina) y su gestión
# (intentos de contacto, llamadas, emails, reuniones, tareas). Todo scoped a UVIC.
# --------------------------------------------------------------------------- #
def _disposiciones(token: str) -> dict:
    """Mapa id->etiqueta de resultados de llamada del portal (o el estándar)."""
    import requests
    try:
        r = requests.get(f"{API}/calling/v1/dispositions",
                         headers=_headers(token), timeout=30)
        if r.status_code == 200:
            m = {d.get("id"): d.get("label") for d in r.json() if d.get("id")}
            if m:
                return m
    except Exception:  # noqa: BLE001
        pass
    return dict(_DISPOSICIONES_DEFAULT)


def _asociadas(token: str, ids: list, tipo: str) -> set:
    """IDs de actividades de `tipo` (calls/emails/…) asociadas a esos contactos."""
    import requests
    got = set()
    for i in range(0, len(ids), 100):
        try:
            r = requests.post(f"{API}/crm/v4/associations/contact/{tipo}/batch/read",
                              headers=_headers(token),
                              json={"inputs": [{"id": c} for c in ids[i:i + 100]]}, timeout=60)
            if r.status_code not in (200, 207):
                continue
            for it in r.json().get("results", []):
                for t in it.get("to", []):
                    got.add(str(t.get("toObjectId")))
        except Exception:  # noqa: BLE001
            continue
    return got


def actividad_uvic():
    """Devuelve (estructura, origen). estructura = dict con la actividad de los
    leads UVIC (contacto=uvic_curso + owner Vanina, sin IMPORT/webinar):
    df de leads, resumen de intentos, conteo de actividades y detalle de llamadas."""
    from datetime import date, datetime, timezone

    import requests

    creds = _leer_secreto("hubspot")
    if not (creds and creds.get("access_token")):
        return None, "sample"
    token = creds["access_token"]

    # 1) Contactos UVIC de Vanina (sin IMPORT/webinar) con propiedades de actividad.
    props = ["firstname", "lastname", "email", "uvic_curso", "num_contacted_notes",
             "num_notes", "notes_last_contacted", "hs_lead_status", "hs_object_source",
             "uvic_utm_campaign", "uvic_utm_source", "uvic_utm_medium"]
    payload = {
        "filterGroups": [{"filters": [
            {"propertyName": "uvic_curso", "operator": "HAS_PROPERTY"},
            {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": config.HUBSPOT_OWNER_UVIC},
        ]}],
        "properties": props, "limit": 100,
    }
    ids, filas, after = [], [], None
    hoy = date.today()
    try:
        while True:
            if after:
                payload["after"] = after
            r = requests.post(f"{API}/crm/v3/objects/contacts/search",
                              headers=_headers(token), json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            for c in data.get("results", []):
                p = c.get("properties", {})
                if p.get("hs_object_source") == "IMPORT":
                    continue
                if config.excluir_webinar(p.get("uvic_utm_campaign"),
                                          p.get("uvic_utm_source"), p.get("uvic_utm_medium")):
                    continue
                ids.append(c["id"])
                ult = _a_fecha(p.get("notes_last_contacted"))
                dias = (hoy - ult).days if ult else None
                nombre = f"{p.get('firstname','') or ''} {p.get('lastname','') or ''}".strip()
                filas.append(dict(
                    nombre=nombre or (p.get("email") or "—"),
                    email=p.get("email") or "",
                    programa=config.programa_por_curso(p.get("uvic_curso") or ""),
                    intentos=int(p.get("num_contacted_notes") or 0),
                    actividades=int(p.get("num_notes") or 0),
                    ult_contacto=ult,
                    dias_sin_contacto=dias,
                    estado=p.get("hs_lead_status") or "Sin estado",
                ))
            after = data.get("paging", {}).get("next", {}).get("after")
            if not after:
                break
    except Exception as e:  # noqa: BLE001
        return None, f"error ({e})"

    leads = pd.DataFrame(filas)

    # 2) Actividades asociadas a esos contactos (scoped a UVIC).
    act = {t: len(_asociadas(token, ids, t)) for t in ("emails", "meetings", "tasks")}
    call_ids = list(_asociadas(token, ids, "calls"))

    # 3) Detalle de llamadas: resultado (disposition) y duración.
    disp = _disposiciones(token)
    por_res, dur = {}, []
    for i in range(0, len(call_ids), 100):
        try:
            r = requests.post(f"{API}/crm/v3/objects/calls/batch/read",
                              headers=_headers(token),
                              json={"properties": ["hs_call_disposition", "hs_call_duration"],
                                    "inputs": [{"id": c} for c in call_ids[i:i + 100]]}, timeout=60)
            for x in r.json().get("results", []):
                pp = x.get("properties", {})
                lbl = disp.get(pp.get("hs_call_disposition"), "Sin resultado")
                por_res[lbl] = por_res.get(lbl, 0) + 1
                d = pp.get("hs_call_duration")
                if d and int(d) > 0:
                    dur.append(int(d) / 1000)
        except Exception:  # noqa: BLE001
            continue

    n = len(leads)
    intentos = leads["intentos"] if n else pd.Series(dtype=int)
    conect = por_res.get("Conectado", 0)
    estruct = dict(
        leads=leads,
        n_leads=n,
        intentos_total=int(intentos.sum()) if n else 0,
        media_intentos=float(intentos.mean()) if n else 0.0,
        max_intentos=int(intentos.max()) if n else 0,
        sin_contactar=int((intentos == 0).sum()) if n else 0,
        sin_contacto_7d=int(leads["dias_sin_contacto"].fillna(999).ge(7).sum()) if n else 0,
        actividades=dict(calls=len(call_ids), **act),
        llamadas=dict(total=len(call_ids), conectadas=conect,
                      tasa=(conect / len(call_ids)) if call_ids else 0.0,
                      dur_media=(sum(dur) / len(dur)) if dur else 0.0,
                      por_resultado=por_res),
    )
    return estruct, "api"
