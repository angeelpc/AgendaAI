"""Genera un archivo .ics (calendario) para una cita. Sirve en Android y iPhone."""
from datetime import datetime


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def ics_de_cita(cita, negocio_nombre: str, barbero_nombre: str) -> str:
    ahora = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    resumen = f"Cita en {negocio_nombre}".strip()
    desc = f"Con {barbero_nombre}. Servicio: {cita.servicio or ''}".strip()
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//AgendaAI//ES\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:cita-{cita.id}@agendaai\r\n"
        f"DTSTAMP:{ahora}\r\n"
        f"DTSTART:{_fmt(cita.inicio)}\r\n"
        f"DTEND:{_fmt(cita.fin)}\r\n"
        f"SUMMARY:{resumen}\r\n"
        f"DESCRIPTION:{desc}\r\n"
        f"LOCATION:{negocio_nombre}\r\n"
        "BEGIN:VALARM\r\n"
        "TRIGGER:-PT2H\r\n"
        "ACTION:DISPLAY\r\n"
        "DESCRIPTION:Recordatorio de tu cita\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
