from datetime import datetime, date, timedelta

from app.models import Barberia, Barbero, Cita, MetricaIA
from app.metrics import registrar_llamada_ia
from app.report import resumen_dia, enviar_email


def test_registrar_llamada_ia(db):
    registrar_llamada_ia(db)
    registrar_llamada_ia(db)
    m = db.get(MetricaIA, date.today().isoformat())
    assert m.llamadas == 2


def test_resumen_dia_cuenta_citas(db):
    registrar_llamada_ia(db, 3)
    barberia = db.query(Barberia).first()
    bar = db.query(Barbero).filter(Barbero.numero == 1).first()
    c = Cita(barberia_id=barberia.id, barbero_id=bar.id, cliente_nombre="X",
             cliente_telefono="5", servicio="Corte",
             inicio=datetime.now() + timedelta(hours=2),
             fin=datetime.now() + timedelta(hours=3), creada=datetime.now())
    db.add(c); db.commit()
    r = resumen_dia(db)
    assert r["gemini_llamadas"] == 3
    assert any(n["citas"] >= 1 for n in r["negocios"])


def test_email_simulado(db):
    assert enviar_email("hola", "cuerpo").get("simulado") is True
