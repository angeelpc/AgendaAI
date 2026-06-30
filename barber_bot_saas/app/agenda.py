"""Motor de agenda: disponibilidad, reserva y cancelacion por barbero.

Reglas:
- Cada barbero tiene horario laboral y dias libres.
- Los slots se generan por la duracion del servicio.
- Nunca se permite doble reserva (se valida contra citas existentes).
- No se ofrecen horarios pasados.
"""
from datetime import datetime, date, timedelta, time as dtime

from .models import Barbero, Cita


def _hhmm(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and a_end > b_start


class AgendaService:
    def __init__(self, db, barberia_id: int):
        self.db = db
        self.barberia_id = barberia_id

    def barbero_por_numero(self, numero: int):
        return (
            self.db.query(Barbero)
            .filter(Barbero.barberia_id == self.barberia_id, Barbero.numero == numero)
            .first()
        )

    def get_availability(self, barbero: Barbero, dia: date, duracion_min: int,
                         ahora: datetime | None = None):
        """Devuelve lista de datetime (inicios de slot) libres ese dia."""
        ahora = ahora or datetime.now()
        if dia.weekday() in barbero.dias_libres():
            return []

        dur = timedelta(minutes=duracion_min)

        existentes = (
            self.db.query(Cita)
            .filter(
                Cita.barbero_id == barbero.id,
                Cita.estado == "agendada",
                Cita.inicio >= datetime.combine(dia, dtime(0, 0)),
                Cita.inicio < datetime.combine(dia, dtime(0, 0)) + timedelta(days=1),
            )
            .all()
        )

        slots = []
        # Recorre cada bloque del horario (soporta horarios partidos: 10-14 y 16-20)
        for ini, fin in barbero.rangos():
            cur = datetime.combine(dia, _hhmm(ini))
            cierre = datetime.combine(dia, _hhmm(fin))
            while cur + dur <= cierre:
                slot_end = cur + dur
                if cur > ahora and not any(
                    _overlaps(cur, slot_end, c.inicio, c.fin) for c in existentes
                ):
                    slots.append(cur)
                cur += dur
        slots.sort()
        return slots

    def book(self, barbero: Barbero, inicio: datetime, duracion_min: int,
             cliente_nombre: str, cliente_telefono: str, servicio: str):
        """Agenda una cita. Lanza ValueError si el horario ya esta ocupado."""
        fin = inicio + timedelta(minutes=duracion_min)
        choque = (
            self.db.query(Cita)
            .filter(
                Cita.barbero_id == barbero.id,
                Cita.estado == "agendada",
                Cita.inicio < fin,
                Cita.fin > inicio,
            )
            .first()
        )
        if choque:
            raise ValueError("Ese horario ya esta ocupado.")

        cita = Cita(
            barberia_id=self.barberia_id,
            barbero_id=barbero.id,
            cliente_nombre=cliente_nombre,
            cliente_telefono=cliente_telefono,
            servicio=servicio,
            inicio=inicio,
            fin=fin,
            estado="agendada",
        )
        self.db.add(cita)
        self.db.commit()
        self.db.refresh(cita)
        return cita

    def cancel(self, cita_id: int):
        cita = self.db.get(Cita, cita_id)
        if cita and cita.barberia_id == self.barberia_id:
            cita.estado = "cancelada"
            self.db.commit()
            return True
        return False
