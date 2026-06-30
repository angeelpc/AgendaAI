from datetime import datetime, date, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.models import Barberia, Barbero, Cita
from app.agenda import AgendaService

client = TestClient(app)


def test_horario_partido(db):
    barberia = db.query(Barberia).first()
    bar = db.query(Barbero).filter(Barbero.numero == 1).first()
    bar.bloques = "10:00-12:00,14:00-16:00"
    db.commit()
    ag = AgendaService(db, barberia.id)
    dia = date(2030, 6, 12)        # miércoles
    ahora = datetime(2030, 6, 11, 9, 0)
    slots = ag.get_availability(bar, dia, 60, ahora=ahora)
    horas = [s.strftime("%H:%M") for s in slots]
    assert "10:00" in horas and "11:00" in horas      # primer bloque
    assert "14:00" in horas and "15:00" in horas      # segundo bloque
    assert "12:00" not in horas and "13:00" not in horas  # hueco intermedio


def test_rangos_simple_sin_bloques(db):
    bar = db.query(Barbero).filter(Barbero.numero == 1).first()
    bar.bloques = ""
    assert bar.rangos() == [(bar.work_start, bar.work_end)]


def test_ics_endpoint(db):
    barberia = db.query(Barberia).first()
    bar = db.query(Barbero).filter(Barbero.numero == 1).first()
    c = Cita(barberia_id=barberia.id, barbero_id=bar.id, cliente_nombre="X",
             cliente_telefono="521", servicio="Corte",
             inicio=datetime(2030, 7, 1, 10, 0), fin=datetime(2030, 7, 1, 10, 45))
    db.add(c); db.commit(); db.refresh(c)
    r = client.get(f"/ics/{c.id}")
    assert r.status_code == 200
    assert "BEGIN:VEVENT" in r.text
    assert "text/calendar" in r.headers["content-type"]
