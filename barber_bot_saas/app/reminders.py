"""Recordatorios automaticos de citas.

Busca citas agendadas que ocurren dentro de la ventana de recordatorio
(por defecto 24h: el dia antes) y que aun no han sido recordadas, manda el
mensaje por WhatsApp y las marca para no reenviar.

Se puede correr:
  - Manualmente desde el panel (POST /api/recordatorios/enviar).
  - Programado, una o varias veces al dia:  python -m app.reminders
El campo `recordatorio_enviado` evita duplicados aunque corra varias veces.
"""
from datetime import datetime, timedelta

from .config import settings
from .database import SessionLocal, init_db
from .models import Barberia, Barbero, Cita
from .branding import Textos
from . import whatsapp, plans

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _texto(cita: Cita, barbero_nombre: str, t: Textos) -> str:
    d = cita.inicio
    dia = DIAS[d.weekday()]
    hora = d.strftime("%H:%M")
    nombre = cita.cliente_nombre or "hola"
    return t.recordatorio(nombre, dia, hora, barbero_nombre)


def citas_por_recordar(db, barberia_id: int, ahora: datetime, ventana_horas: int):
    """Citas agendadas, dentro de la ventana, no recordadas y con telefono."""
    limite = ahora + timedelta(hours=ventana_horas)
    return (
        db.query(Cita)
        .filter(
            Cita.barberia_id == barberia_id,
            Cita.estado == "agendada",
            Cita.recordatorio_enviado.is_(False),
            Cita.inicio > ahora,
            Cita.inicio <= limite,
            Cita.cliente_telefono.isnot(None),
            Cita.cliente_telefono != "",
        )
        .order_by(Cita.inicio)
        .all()
    )


def enviar_recordatorios(db, barberia: Barberia, ahora: datetime | None = None,
                         ventana_horas: int | None = None, send: bool = True) -> int:
    """Envia recordatorios pendientes de una barberia. Devuelve cuantos mando.

    Respeta el plan: no envia si la suscripcion no esta activa, y no excede el
    cupo de recordatorios del mes.
    """
    ahora = ahora or datetime.now()
    ventana = ventana_horas if ventana_horas is not None else settings.REMINDER_HOURS

    # 1) suscripcion debe estar activa (en prueba o pagada vigente)
    if not plans.suscripcion_activa(barberia, ahora):
        return 0

    # 2) cupo mensual del plan (se reinicia cada mes)
    mes = ahora.strftime("%Y-%m")
    if barberia.recordatorios_mes_ref != mes:
        barberia.recordatorios_mes_ref = mes
        barberia.recordatorios_mes_count = 0
    restantes = plans.limite_recordatorios(barberia) - (barberia.recordatorios_mes_count or 0)
    if restantes <= 0:
        db.commit()
        return 0

    citas = citas_por_recordar(db, barberia.id, ahora, ventana)
    if not citas:
        db.commit()
        return 0

    barberos = {b.id: b.nombre for b in
                db.query(Barbero).filter(Barbero.barberia_id == barberia.id)}
    t = Textos(barberia)

    enviados = 0
    for c in citas:
        if enviados >= restantes:
            break  # se agoto el cupo del plan este mes
        texto = _texto(c, barberos.get(c.barbero_id, t.recurso), t)
        if send:
            whatsapp.send_text(c.cliente_telefono, texto, barberia.whatsapp_phone_id)
        c.recordatorio_enviado = True
        enviados += 1
    barberia.recordatorios_mes_count = (barberia.recordatorios_mes_count or 0) + enviados
    db.commit()
    return enviados


def correr_todas(ahora: datetime | None = None) -> int:
    """Recorre todas las barberias activas y manda sus recordatorios pendientes."""
    init_db()
    db = SessionLocal()
    total = 0
    try:
        for b in db.query(Barberia).filter(Barberia.activo.is_(True)).all():
            total += enviar_recordatorios(db, b, ahora=ahora)
    finally:
        db.close()
    return total


if __name__ == "__main__":
    n = correr_todas()
    print(f"Recordatorios enviados: {n}")
