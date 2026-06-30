from datetime import datetime

from app.models import Barberia
from app.service import handle_incoming
from app import whatsapp


def test_recurso_devuelve_opciones(db):
    barberia = db.query(Barberia).first()
    ahora = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    r = handle_incoming(db, barberia, "521777001", "quiero una cita",
                        ahora=ahora, send=False)
    assert r.opciones, "debe ofrecer opciones de recurso"
    ids = [o["id"] for o in r.opciones]
    assert "1" in ids  # el barbero numero 1 existe


def test_boton_id_avanza_igual_que_texto(db):
    """Elegir por id de boton ('1') debe avanzar igual que escribir '1'."""
    barberia = db.query(Barberia).first()
    ahora = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    handle_incoming(db, barberia, "521777002", "quiero una cita", ahora=ahora, send=False)
    r = handle_incoming(db, barberia, "521777002", "1", ahora=ahora, send=False)
    # tras elegir barbero, pide el día
    assert "día" in r.text.lower() or "dia" in r.text.lower()


def test_confirmacion_ofrece_si_no(db):
    barberia = db.query(Barberia).first()
    tel = "521777003"
    ahora = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    import json
    from app.models import Conversacion
    handle_incoming(db, barberia, tel, "cita el sábado con el 1", ahora=ahora, send=False)
    conv = db.query(Conversacion).filter(Conversacion.telefono == tel).first()
    hora = datetime.fromisoformat(json.loads(conv.contexto)["offered"][0]).strftime("%H:%M")
    handle_incoming(db, barberia, tel, hora, ahora=ahora, send=False)
    r = handle_incoming(db, barberia, tel, "Pedro", ahora=ahora, send=False)
    ids = [o["id"] for o in (r.opciones or [])]
    assert "si" in ids and "no" in ids


def test_send_buttons_simulado(db):
    out = whatsapp.send_buttons("521", "Elige", [{"id": "1", "title": "Uno"}], None)
    assert out.get("simulado") is True
