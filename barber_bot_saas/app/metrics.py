"""Contador de uso del cerebro IA (para el informe diario)."""
from datetime import date

from .models import MetricaIA


def registrar_llamada_ia(db, n: int = 1):
    """Suma n llamadas al contador del día de hoy."""
    hoy = date.today().isoformat()
    m = db.get(MetricaIA, hoy)
    if not m:
        m = MetricaIA(fecha=hoy, llamadas=0)
        db.add(m)
    m.llamadas = (m.llamadas or 0) + n
    db.commit()
