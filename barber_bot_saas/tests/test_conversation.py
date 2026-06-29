import json
from datetime import datetime, timedelta

from app.models import Barberia, Conversacion, Cita
from app.service import handle_incoming


def _ahora():
    return datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)


def _offered(db, barberia_id, tel):
    conv = (db.query(Conversacion)
            .filter(Conversacion.barberia_id == barberia_id,
                    Conversacion.telefono == tel).first())
    ctx = json.loads(conv.contexto or "{}")
    off = ctx.get("offered") or []
    return datetime.fromisoformat(off[0]).strftime("%H:%M") if off else None


def test_flujo_completo_agenda_cita(db):
    barberia = db.query(Barberia).first()
    tel = "5211111111111"
    ahora = _ahora()
    handle_incoming(db, barberia, tel, "hola quiero corte el sábado", ahora=ahora, send=False)
    handle_incoming(db, barberia, tel, "con el 2 en la tarde", ahora=ahora, send=False)
    hora = _offered(db, barberia.id, tel)
    assert hora is not None
    handle_incoming(db, barberia, tel, f"{hora}", ahora=ahora, send=False)
    handle_incoming(db, barberia, tel, "Angel", ahora=ahora, send=False)
    r = handle_incoming(db, barberia, tel, "sí", ahora=ahora, send=False)

    assert r.booked_cita_id is not None
    cita = db.get(Cita, r.booked_cita_id)
    assert cita.cliente_nombre == "Angel"
    assert cita.estado == "agendada"


def test_escalacion_a_humano(db):
    barberia = db.query(Barberia).first()
    tel = "5212222222222"
    r = handle_incoming(db, barberia, tel,
                        "quiero un reembolso, el corte quedó pésimo",
                        ahora=_ahora(), send=False)
    assert r.escalate is True
    conv = (db.query(Conversacion)
            .filter(Conversacion.telefono == tel).first())
    assert conv.estado == "humano"
    # tras escalar, el bot ya no responde
    r2 = handle_incoming(db, barberia, tel, "hola?", ahora=_ahora(), send=False)
    assert r2.text == ""


def test_eleccion_de_barbero_por_nombre(db):
    barberia = db.query(Barberia).first()
    tel = "5213333333333"
    ahora = _ahora()
    handle_incoming(db, barberia, tel, "me agendas con Luis mañana", ahora=ahora, send=False)
    conv = (db.query(Conversacion)
            .filter(Conversacion.telefono == tel).first())
    ctx = json.loads(conv.contexto)
    assert ctx.get("barbero_numero") == 3  # Luis es el 3
