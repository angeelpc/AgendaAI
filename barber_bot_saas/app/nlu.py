"""Extraccion de entidades en espanol (fechas, horas, barbero, intencion).

Se usa en el motor de reglas (modo offline). El cerebro con IA no lo necesita,
pero comparte el mismo motor de agenda.
"""
import re
import unicodedata
from datetime import date, datetime, time as dtime, timedelta

WEEKDAYS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
}

CONFIRM_WORDS = {"si", "sí", "confirmar", "confirmo", "claro", "va", "vale",
                 "sale", "ok", "okay", "dale", "perfecto", "esa", "ese", "correcto"}

CANCEL_WORDS = {"cancelar", "cancela", "anular"}

ESCALATION_WORDS = {"humano", "persona", "gerente", "reembolso", "reclamo",
                    "queja", "devolucion", "devolución", "encargado", "dueño",
                    "molesto", "pesimo", "pésimo", "demanda"}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    return strip_accents(s.lower().strip())


def has_any(text: str, words: set) -> bool:
    t = norm(text)
    return any(norm(w) in t.split() or norm(w) in t for w in words)


def parse_barbero_numero(text: str, nombres: dict | None = None):
    """Devuelve el numero de barbero (1-4) o None.
    nombres: dict {nombre_normalizado: numero} para detectar por nombre."""
    t = norm(text)
    m = re.search(r"barbero\s*(\d)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\bel\s*(\d)\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\bcon\s+el\s+(\d)\b", t)
    if m:
        return int(m.group(1))
    if nombres:
        for nombre, num in nombres.items():
            if nombre in t:
                return num
    # un digito suelto 1-4
    m = re.search(r"\b([1-4])\b", t)
    if m:
        return int(m.group(1))
    return None


def parse_dia(text: str, hoy: date | None = None):
    """Devuelve una fecha o None."""
    hoy = hoy or date.today()
    t = norm(text)
    if "pasado manana" in t:
        return hoy + timedelta(days=2)
    if "manana" in t and "pasado" not in t:
        # "manana" puede ser dia o periodo; aqui lo tratamos como dia siguiente
        # solo si no hay palabra de periodo cercana tipo "en la manana"
        if not re.search(r"(en la|por la)\s+manana", t):
            return hoy + timedelta(days=1)
    if "hoy" in t:
        return hoy
    for nombre, wd in WEEKDAYS.items():
        if norm(nombre) in t:
            delta = (wd - hoy.weekday()) % 7
            return hoy + timedelta(days=delta)
    # fecha tipo 25/12 o 25-12
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})\b", t)
    if m:
        d, mth = int(m.group(1)), int(m.group(2))
        try:
            yr = hoy.year
            f = date(yr, mth, d)
            if f < hoy:
                f = date(yr + 1, mth, d)
            return f
        except ValueError:
            return None
    return None


def parse_periodo(text: str):
    """'manana' (matutino), 'tarde', 'noche' o None."""
    t = norm(text)
    if re.search(r"(en la|por la)\s+manana", t) or "matutino" in t:
        return "manana"
    if "tarde" in t:
        return "tarde"
    if "noche" in t:
        return "noche"
    return None


def parse_hora(text: str):
    """Devuelve un objeto time o None."""
    t = norm(text)
    # 16:45 / 4:45
    m = re.search(r"\b(\d{1,2})[:\.](\d{2})\b", t)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        # contexto pm si dice "tarde" y h<12
        if h < 8 and ("tarde" in t or "pm" in t or "noche" in t):
            h += 12
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return dtime(h, mi)
    # 4 pm / 4pm / a las 5
    m = re.search(r"\b(\d{1,2})\s*(am|pm)\b", t)
    if m:
        h = int(m.group(1))
        if m.group(2) == "pm" and h < 12:
            h += 12
        if m.group(2) == "am" and h == 12:
            h = 0
        return dtime(h, 0)
    m = re.search(r"a\s+las\s+(\d{1,2})\b", t)
    if m:
        h = int(m.group(1))
        if h < 8 and ("tarde" in t or "noche" in t):
            h += 12
        return dtime(h, 0)
    return None


def parse_nombre(text: str):
    """Intenta extraer un nombre propio."""
    t = text.strip()
    m = re.search(r"(?:me llamo|soy|mi nombre es)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ ]{2,30})", t, re.I)
    if m:
        return m.group(1).strip().title()
    # si es una sola palabra/dos, asumir nombre
    palabras = [p for p in re.split(r"\s+", t) if p]
    if 1 <= len(palabras) <= 3 and all(re.match(r"^[A-Za-zÁÉÍÓÚáéíóúñÑ]+$", p) for p in palabras):
        return t.title()
    return None
