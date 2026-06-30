from datetime import datetime

from app.models import Barberia
from app.service import handle_incoming


def test_muestra_dias_que_atiende(db):
    barberia = db.query(Barberia).first()  # Carlos #1 days_off="0" (lunes)
    ahora = datetime(2030, 6, 11, 9, 0)
    handle_incoming(db, barberia, "521900", "quiero una cita", ahora=ahora, send=False)
    r = handle_incoming(db, barberia, "521900", "1", ahora=ahora, send=False)
    assert "atiende" in r.text.lower()
    assert "martes" in r.text.lower()
    assert "lunes" not in r.text.lower()


def test_valida_dia_no_atendido(db):
    barberia = db.query(Barberia).first()
    ahora = datetime(2030, 6, 11, 9, 0)
    handle_incoming(db, barberia, "521901", "quiero una cita", ahora=ahora, send=False)
    handle_incoming(db, barberia, "521901", "1", ahora=ahora, send=False)
    r = handle_incoming(db, barberia, "521901", "el lunes", ahora=ahora, send=False)
    assert "no atiende los lunes" in r.text.lower()
