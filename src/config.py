"""
Configuración central del Dashboard UVic / WeRise.

Todos los identificadores de cuenta, objetivos de negocio y el mapeo de
campañas viven aquí para que las páginas y los conectores lean de una
única fuente de verdad.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Cuentas de plataforma
# --------------------------------------------------------------------------- #

# Google Ads (EUR). La cuenta con las campañas WeRise es la 2970533333 "UVic".
# Verificado: contiene WeRise_Search_NAC_* + LISA-2026 + BRANDING UVIC-UCC.
# El MCC de login puede ser Nuclio (3963262878) o "UVic MCC - Rise Marketing"
# (9010916591) según con qué credenciales se autentique la API directa.
GOOGLE_ADS_CUSTOMER_ID = "2970533333"
GOOGLE_ADS_LOGIN_CUSTOMER_ID = "4885772142"  # MCC - Rise Marketing (gestiona UVic)

# Meta Ads: cuenta publicitaria UVic-UCC.
META_AD_ACCOUNT_ID = "act_33542477"
META_BUSINESS_ID = "127243537925769"
META_PIXEL_DATASET_ID = "201468227580360"  # "Cloud Pages Pixel" (el bueno)

# Google Analytics 4: "Cloud Pages Salesforce - GA4".
GA4_PROPERTY_ID = "properties/308288730"

# HubSpot: portal objetivo "Rise Education" (144637943). OJO: pendiente de conectar
# vía /mcp — el conector activo apunta a otro portal (143302790). No usar el 143302790
# para datos de UVic salvo confirmación.
HUBSPOT_PORTAL_ID = "144637943"

# --------------------------------------------------------------------------- #
# Objetivos de negocio (Etapa 1 — referencia jun-2026)
# --------------------------------------------------------------------------- #

# Objetivo de referencia: ~17.002 €/mes de inversión -> 57 matrículas.
OBJETIVO_INVERSION_MENSUAL = 17002.0
OBJETIVO_MATRICULAS = 57

# Valor económico medio de una matrícula (EUR) — PVP medio confirmado por UVic/WeRise.
# Input clave para el cálculo de ROAS (ingresos = matrículas × VALOR_MATRICULA).
VALOR_MATRICULA = 2100.0

# CPL objetivo — rango acordado en la replanificación (jul-2026): 50-70 €.
# El semáforo usa el máximo del rango como umbral verde.
CPL_OBJETIVO_MIN = 50.0
CPL_OBJETIVO_MAX = 70.0
CPL_OBJETIVO = CPL_OBJETIVO_MAX  # compatibilidad: umbral del semáforo

# Tasa de conversión lead -> matrícula esperada (para el forecast del embudo).
TASA_LEAD_A_MATRICULA = 0.06  # 6%

MONEDA = "EUR"
SIMBOLO_MONEDA = "€"

# --------------------------------------------------------------------------- #
# Benchmarks para el semáforo (verde/ámbar/rojo). Alineados con la skill de
# performance-report y ajustados al sector educación/captación. Editables.
#   mejor='alto'  -> ok si valor >= ok;  warn si valor >= warn;  si no, off
#   mejor='bajo'  -> ok si valor <= ok;  warn si valor <= warn;  si no, off
# --------------------------------------------------------------------------- #
BENCH = {
    "ctr_search":  dict(mejor="alto", ok=0.04,  warn=0.02),   # CTR búsqueda (Google)
    "ctr_social":  dict(mejor="alto", ok=0.009, warn=0.005),  # CTR social (Meta)
    "cpc_search":  dict(mejor="bajo", ok=1.5,   warn=3.0),
    "cpc_social":  dict(mejor="bajo", ok=0.70,  warn=1.20),
    "cpm_social":  dict(mejor="bajo", ok=5.0,   warn=10.0),
    "rebote":      dict(mejor="bajo", ok=0.45,  warn=0.60),
    "cpl":         dict(mejor="bajo", ok=CPL_OBJETIVO, warn=CPL_OBJETIVO * 2),
    "roas":        dict(mejor="alto", ok=3.0,   warn=1.0),
}


def estado_bench(tipo: str, valor: float | None) -> str | None:
    """Devuelve 'ok'|'warn'|'off' según el benchmark, o None si no aplica."""
    b = BENCH.get(tipo)
    if not b or valor is None or valor == 0:
        return None
    if b["mejor"] == "alto":
        return "ok" if valor >= b["ok"] else ("warn" if valor >= b["warn"] else "off")
    return "ok" if valor <= b["ok"] else ("warn" if valor <= b["warn"] else "off")

# --------------------------------------------------------------------------- #
# Caché (segundos). HubSpot cambia a diario -> refresco corto. Los ads cambian
# despacio y sus APIs tienen cuotas -> refresco más largo.
# --------------------------------------------------------------------------- #
CACHE_TTL_HUBSPOT = 300   # 5 min
CACHE_TTL_ADS = 1800      # 30 min
CACHE_TTL_GA4 = 1800      # 30 min


# --------------------------------------------------------------------------- #
# Mapeo de campañas WeRise  ->  programa académico
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Programa:
    """Un programa académico, sus campañas en cada plataforma y su valor en
    HubSpot (propiedad de contacto `uvic_curso`)."""
    nombre: str
    slug: str
    campana_google: str
    campana_meta: str
    uvic_curso: str  # valor de la propiedad uvic_curso en HubSpot


PROGRAMAS: list[Programa] = [
    Programa(
        nombre="MBA Executive",
        slug="mba-executive",
        campana_google="WeRise_Search_NAC_MBA_Executive",
        campana_meta="WeRise_Executive MBA",
        uvic_curso="WeRise_ExecutiveMBA",
    ),
    Programa(
        nombre="Marketing Deportivo",
        slug="marketing-deportivo",
        campana_google="WeRise_Search_NAC_Master_Marqueting_Esportiu",
        campana_meta="WeRise_Màster_Gestió i Màrqueting Esportiu",
        uvic_curso="WeRise_Gestió_Màrqueting_Esportiu",
    ),
    Programa(
        nombre="Documentación Social",
        slug="documentacion-social",
        campana_google="WeRise_Search_NAC_Postgrau_Documental_Social",
        campana_meta="WeRise_Postgrau_Documental Social",
        uvic_curso="WeRise_Documental_Social",
    ),
    Programa(
        nombre="Comunicación Científica",
        slug="comunicacion-cientifica",
        campana_google="WeRise_Search_NAC_Postgrau_Comunicacio_Cientifica",
        campana_meta="WeRise_Postgrau_Comunicació Científica",
        uvic_curso="WeRise_Comunicació_Científica",
    ),
    Programa(
        nombre="Liderazgo IA",
        slug="liderazgo-ia",
        campana_google="WeRise_Search_NAC_Postgrau_Lideratge_IA",
        campana_meta="WeRise_EP_Lidera en entorns d'Intel·ligència Artificial",
        uvic_curso="WeRise_Lidera_en_entorns_IA",
    ),
]


def _normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y solo alfanuméricos: unifica nombres de campaña
    de Google (ASCII) y Meta (con acentos), y tolera separadores _ - espacio ·."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return "".join(c for c in t.lower() if c.isalnum())


# Palabras clave distintivas por programa (normalizadas). Sirven para asignar
# CUALQUIER variante de campaña (Search, PMAX, DemandGen, Meta…) a su programa.
_KEYWORDS_PROGRAMA = {
    "MBA Executive": ("mbaexecutive", "executivemba"),
    "Marketing Deportivo": ("marquetingesportiu", "sportmanagement", "gestioimarqueting"),
    "Documentación Social": ("documentalsocial",),
    "Comunicación Científica": ("comunicaciocientifica", "comunicaciocientifica"),
    "Liderazgo IA": ("lideratgeia", "lideraenentorns", "intelligencia"),
}


def programa_por_campana(nombre_campana: str) -> str:
    """Devuelve el nombre del programa dado el nombre de campaña (Google o Meta).

    Coincide por palabra clave normalizada, así reconoce todas las variantes
    (WeRise_Search_…, WeRise_PMAX_…, WeRise-DemandGen_…, nombres de Meta…).
    """
    if not nombre_campana:
        return "Sin asignar"
    n = _normalizar(nombre_campana)
    for prog, claves in _KEYWORDS_PROGRAMA.items():
        if any(k in n for k in claves):
            return prog
    return "Otras / Branding"


def es_campana_werise(nombre_campana: str) -> bool:
    """True si la campaña es nuestra: cualquier campaña cuyo nombre empiece por
    'WeRise' (Google o Meta). Así las campañas nuevas aparecen automáticamente,
    sin tener que mantener una lista fija de programas."""
    return _normalizar(nombre_campana).startswith("werise")


def clave_campana(nombre: str) -> str:
    """Clave normalizada para emparejar un mismo nombre de campaña entre la
    plataforma (Google/Meta) y la `uvic_utm_campaign` de HubSpot, tolerando
    mayúsculas, acentos y separadores (p.ej. 'Werise-DemandGen' == 'WeRise_DemandGen')."""
    return _normalizar(nombre)


def estado_legible(raw: str) -> str:
    """Normaliza el estado de una campaña (Google: ENABLED/PAUSED; Meta:
    ACTIVE/PAUSED/…) a una etiqueta en español."""
    r = (raw or "").upper()
    if r in ("ENABLED", "ACTIVE"):
        return "Activa"
    if "PAUSED" in r:
        return "Pausada"
    if r in ("REMOVED", "ARCHIVED", "DELETED"):
        return "Archivada"
    return "Otra"


def es_webinar(utm_campaign: str) -> bool:
    """True si uvic_utm_campaign contiene 'webinar' (p.ej. 'WebInar',
    'WEBINAR EMBA - IA ABRIL')."""
    return "webinar" in (utm_campaign or "").lower()


def excluir_webinar(utm_campaign: str, utm_source: str = "", utm_medium: str = "") -> bool:
    """True si el lead debe salir de la captación por ser de webinar.
    EXCEPCIÓN: si sus UTMs apuntan a una plataforma de pago (Meta/Google,
    p.ej. ig/ads), es lead de ads aunque la campaña diga webinar → se queda
    en captación. El resto de webinars va a la hoja de Leads Importados."""
    return (es_webinar(utm_campaign)
            and plataforma_por_utm(utm_source, utm_medium) not in ("Meta", "Google"))


def plataforma_por_utm(source: str, medium: str) -> str:
    """Deriva la plataforma desde las UTM de HubSpot (uvic_utm_source/medium).
    Meta = ig/fb/facebook/meta; Google = google. Sin UTM si viene vacío."""
    s = (source or "").strip().lower()
    m = (medium or "").strip().lower()
    if not s and not m:
        return "Sin UTM"
    if s in ("ig", "fb", "facebook", "meta", "instagram") or m == "paid-social":
        return "Meta"
    if s == "google" or m in ("cpc", "ppc"):
        return "Google"
    return s or "Otra"


def programa_por_curso(uvic_curso: str) -> str:
    """Devuelve el nombre del programa dado el valor de `uvic_curso` (HubSpot)."""
    if not uvic_curso:
        return "Sin asignar"
    u = uvic_curso.strip()
    for p in PROGRAMAS:
        if p.uvic_curso == u:
            return p.nombre
    return "Sin asignar"


# --------------------------------------------------------------------------- #
# GA4 — landings de cada programa (solo se muestra el tráfico de estas 5 URLs)
# Dominio: https://cloud.info-uvic.cat  (en GA4 el pagePath es solo la ruta)
# --------------------------------------------------------------------------- #
LANDING_PROGRAMA = {
    # MBA Executive
    "/master-executive-mba-uvic": "MBA Executive",
    "/mba-executive-uvic": "MBA Executive",
    "/esp-emba": "MBA Executive",
    # Marketing Deportivo
    "/master-sport-management-uvic": "Marketing Deportivo",
    # Documentación Social
    "/Postgrau-Documental-Social": "Documentación Social",
    # Comunicación Científica
    "/Comunicacio-Cientifica": "Comunicación Científica",
    "/comunicacion-cientifica-uvic": "Comunicación Científica",
    "/esp-comunicacion-cientifica": "Comunicación Científica",
    # Liderazgo IA
    "/Lideratge-entorns-IA": "Liderazgo IA",
    "/lideratge-ia-uvic": "Liderazgo IA",
    "/esp-liderazgo-ia": "Liderazgo IA",
}
LANDINGS = list(LANDING_PROGRAMA.keys())

# Fuentes de prueba/test a EXCLUIR del tráfico y eventos de GA4 (no son reales).
GA4_FUENTES_EXCLUIR = ["pixel-doctor", "metaCLAUDETEST"]

# Eventos clave de GA4 que cuentan como conversión (los demás se ignoran).
GA4_EVENTOS_CLAVE = ["LEAD", "form_submit"]


def programa_por_landing(page_path: str) -> str:
    """Mapea la ruta de una landing (GA4 pagePath/landingPage) a su programa."""
    if not page_path:
        return "Sin asignar"
    # normaliza: quita query string y barra final
    p = page_path.split("?")[0].rstrip("/") or "/"
    return LANDING_PROGRAMA.get(p, "Sin asignar")


# --------------------------------------------------------------------------- #
# HubSpot — Pipeline UVIC y etapas del embudo (portal 144637943)
# --------------------------------------------------------------------------- #
HUBSPOT_PIPELINE_UVIC = "3920516288"
HUBSPOT_STAGE_MATRICULA = "5604424920"  # "Cierre ganado"

# Etapas del Pipeline UVIC en orden (id -> etiqueta). El embudo se dibuja así.
HUBSPOT_ETAPAS_UVIC = [
    ("5604424915", "Oportunidad"),
    ("5604424916", "Entrevista concertada"),
    ("5604424917", "Entrevista realizada"),
    ("5604424918", "Envío de inscripción"),
    ("5604424920", "Cierre ganado"),
]
HUBSPOT_ETAPA_PERDIDO = ("5604424921", "Cierre perdido")
HUBSPOT_ETAPAS_MAP = dict(HUBSPOT_ETAPAS_UVIC + [HUBSPOT_ETAPA_PERDIDO])


# --------------------------------------------------------------------------- #
# Paleta y colores por plataforma (consistentes en todo el dashboard)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Tema:
    # Colores corporativos UVic (extraídos del CSS de uvic.cat): rojo granate.
    primario: str = "#CF0A2C"       # rojo UVic (color de marca principal)
    secundario: str = "#7C061A"     # granate oscuro (acento)
    gris_uvic: str = "#4B4B4B"      # gris corporativo
    texto: str = "#212529"          # texto casi negro
    # Colores de identidad por plataforma (se mantienen para distinguir series).
    # Meta usa el violeta de su degradado de marca para no confundirse con el
    # azul de Google en las gráficas.
    color_google: str = "#4285F4"
    color_meta: str = "#A333C8"
    color_ga4: str = "#E8710A"
    color_hubspot: str = "#FF7A59"
    # Semáforo de estado.
    verde_ok: str = "#198754"       # verde de la paleta UVic/bootstrap
    ambar_riesgo: str = "#D97706"
    rojo_off: str = "#CF0A2C"
    # Paleta de gráficos: lidera el granate UVic, luego neutros y acentos.
    paleta: tuple = field(default_factory=lambda: (
        "#CF0A2C", "#4B4B4B", "#7C061A", "#E8710A", "#A333C8", "#198754",
    ))


TEMA = Tema()

COLOR_PLATAFORMA = {
    "Google Ads": TEMA.color_google,
    "Meta Ads": TEMA.color_meta,
    "Google Analytics": TEMA.color_ga4,
    "HubSpot": TEMA.color_hubspot,
    # Fuentes UTM de los leads (mismos colores de identidad que la plataforma).
    "Google": TEMA.color_google,
    "Meta": TEMA.color_meta,
    "Sin UTM": TEMA.gris_uvic,
}
