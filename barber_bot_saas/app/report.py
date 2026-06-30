"""Informe diario por correo: uso de Gemini + actividad del bot.

Correr programado (cron):  python -m app.report
Sin SMTP configurado, imprime el informe (modo simulado).
"""
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from .config import settings
from .database import SessionLocal, init_db
from .models import Barberia, Cita, Conversacion, Mensaje, MetricaIA


def resumen_dia(db, dia: date | None = None) -> dict:
    dia = dia or date.today()
    ini = datetime.combine(dia, datetime.min.time())
    fin = ini + timedelta(days=1)

    metr = db.get(MetricaIA, dia.isoformat())
    gemini = metr.llamadas if metr else 0

    negocios = []
    for b in db.query(Barberia).filter(Barberia.activo.is_(True)).all():
        msgs = (db.query(Mensaje)
                .filter(Mensaje.barberia_id == b.id, Mensaje.direccion == "in",
                        Mensaje.creado >= ini, Mensaje.creado < fin).count())
        citas = (db.query(Cita)
                 .filter(Cita.barberia_id == b.id,
                         Cita.creada >= ini, Cita.creada < fin).count())
        noshow = (db.query(Cita)
                  .filter(Cita.barberia_id == b.id, Cita.estado == "no_show",
                          Cita.inicio >= ini, Cita.inicio < fin).count())
        escal = (db.query(Conversacion)
                 .filter(Conversacion.barberia_id == b.id,
                         Conversacion.estado == "humano").count())
        negocios.append({"nombre": b.nombre, "mensajes": msgs, "citas": citas,
                         "no_shows": noshow, "escalados": escal})
    return {"fecha": dia.isoformat(), "gemini_llamadas": gemini, "negocios": negocios}


def _texto_reporte(r: dict) -> str:
    L = [f"Informe del {r['fecha']}",
         f"Llamadas al cerebro IA (Gemini): {r['gemini_llamadas']}", ""]
    if not r["negocios"]:
        L.append("Sin negocios activos.")
    for n in r["negocios"]:
        L.append(f"• {n['nombre']}: {n['mensajes']} mensajes, {n['citas']} citas, "
                 f"{n['no_shows']} no-shows, {n['escalados']} chats con persona")
    L += ["", "— AgendaAI"]
    return "\n".join(L)


def enviar_email(asunto: str, cuerpo: str) -> dict:
    """Envia el informe por SMTP. Sin config, simula (imprime)."""
    destino = settings.REPORT_TO
    if not (settings.SMTP_HOST and settings.SMTP_USER and destino):
        print("[report] SIMULADO (falta SMTP/REPORT_TO):\n" + cuerpo)
        return {"simulado": True}
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = settings.REPORT_FROM or settings.SMTP_USER
    msg["To"] = destino
    msg.set_content(cuerpo)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as s:
        s.starttls()
        s.login(settings.SMTP_USER, settings.SMTP_PASS)
        s.send_message(msg)
    print(f"[report] enviado a {destino}")
    return {"ok": True, "to": destino}


def correr():
    init_db()
    db = SessionLocal()
    try:
        r = resumen_dia(db)
        cuerpo = _texto_reporte(r)
        return enviar_email(f"AgendaAI — informe {r['fecha']}", cuerpo)
    finally:
        db.close()


if __name__ == "__main__":
    print(correr())
