from datetime import datetime, timedelta

from app.models import Barberia, Barbero, Cita
from app.reminders import enviar_recordatorios, citas_por_recordar


def _cita(db, barberia, when, tel="5211112223", recordado=False):
    bar = db.query(Barbero).filter(Barbero.numero == 1).first()
    c = Cita(barberia_id=barberia.id, barbero_id=bar.id, cliente_nombre="Ana",
             cliente_telefono=tel, servicio="Corte",
             inicio=when, fin=when + timedelta(minutes=45),
             estado="agendada", recordatorio_enviado=recordado)
    db.add(c); db.commit(); db.refresh(c)
    return c


def test_recuerda_cita_dentro_de_ventana(db):
    barberia = db.query(Barberia).first()
    ahora = datetime(2030, 6, 10, 9, 0)
    _cita(db, barberia, ahora + timedelta(hours=20))  # manana
    n = enviar_recordatorios(db, barberia, ahora=ahora, ventana_horas=24, send=False)
    assert n == 1


def test_no_recuerda_fuera_de_ventana(db):
    barberia = db.query(Barberia).first()
    ahora = datetime(2030, 6, 10, 9, 0)
    _cita(db, barberia, ahora + timedelta(hours=72))  # dentro de 3 dias
    n = enviar_recordatorios(db, barberia, ahora=ahora, ventana_horas=24, send=False)
    assert n == 0


def test_no_reenvia_dos_veces(db):
    barberia = db.query(Barberia).first()
    ahora = datetime(2030, 6, 10, 9, 0)
    _cita(db, barberia, ahora + timedelta(hours=10))
    primera = enviar_recordatorios(db, barberia, ahora=ahora, ventana_horas=24, send=False)
    segunda = enviar_recordatorios(db, barberia, ahora=ahora, ventana_horas=24, send=False)
    assert primera == 1 and segunda == 0


def test_ignora_citas_sin_telefono(db):
    barberia = db.query(Barberia).first()
    ahora = datetime(2030, 6, 10, 9, 0)
    _cita(db, barberia, ahora + timedelta(hours=5), tel="")
    assert citas_por_recordar(db, barberia.id, ahora, 24) == []
