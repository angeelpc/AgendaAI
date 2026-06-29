from datetime import datetime, timedelta, date

from app.models import Barberia
from app.agenda import AgendaService


def _proximo_sabado(ahora):
    d = ahora.date()
    delta = (5 - d.weekday()) % 7
    delta = delta or 7
    return d + timedelta(days=delta)


def test_disponibilidad_genera_slots(db):
    barberia = db.query(Barberia).first()
    ag = AgendaService(db, barberia.id)
    memo = ag.barbero_por_numero(2)
    ahora = datetime.now().replace(hour=8, minute=0)
    slots = ag.get_availability(memo, _proximo_sabado(ahora), 45, ahora)
    assert len(slots) > 0
    # Memo trabaja 10:00-20:00 -> primer slot 10:00
    assert slots[0].time().hour == 10


def test_no_doble_reserva(db):
    barberia = db.query(Barberia).first()
    ag = AgendaService(db, barberia.id)
    memo = ag.barbero_por_numero(2)
    ahora = datetime.now().replace(hour=8, minute=0)
    sab = _proximo_sabado(ahora)
    slots = ag.get_availability(memo, sab, 45, ahora)
    inicio = slots[0]

    ag.book(memo, inicio, 45, "Angel", "5210000000000", "Corte")

    # mismo horario debe fallar
    try:
        ag.book(memo, inicio, 45, "Otro", "5219999999999", "Corte")
        assert False, "deberia haber lanzado ValueError"
    except ValueError:
        pass

    # y ese slot ya no aparece como disponible
    slots2 = ag.get_availability(memo, sab, 45, ahora)
    assert inicio not in slots2


def test_dia_libre_sin_slots(db):
    barberia = db.query(Barberia).first()
    ag = AgendaService(db, barberia.id)
    carlos = ag.barbero_por_numero(1)  # libre lunes (0)
    # buscar el proximo lunes
    ahora = datetime.now().replace(hour=8, minute=0)
    d = ahora.date()
    delta = (0 - d.weekday()) % 7
    lunes = d + timedelta(days=delta or 7)
    slots = ag.get_availability(carlos, lunes, 45, ahora)
    assert slots == []
