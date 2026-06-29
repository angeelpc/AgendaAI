from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.models import Barberia, Barbero, Cita
from app import plans, billing
from app.onboarding import crear_negocio
from app.reminders import enviar_recordatorios

client = TestClient(app)
AUTH = {"X-Barberia-Id": "1", "X-Api-Key": "demo-key-filo"}


def _cita(db, barberia, when, tel="5210001111"):
    bar = db.query(Barbero).filter(Barbero.numero == 1).first()
    c = Cita(barberia_id=barberia.id, barbero_id=bar.id, cliente_nombre="Ana",
             cliente_telefono=tel, servicio="Corte",
             inicio=when, fin=when + timedelta(minutes=45), estado="agendada")
    db.add(c); db.commit()
    return c


# --------- planes / límites ---------

def test_suscripcion_activa_en_prueba_y_vencida(db):
    b = db.query(Barberia).first()
    ahora = datetime(2030, 1, 1, 9, 0)
    b.estado_suscripcion = "prueba"; b.suscripcion_hasta = None
    assert plans.suscripcion_activa(b, ahora) is True
    b.estado_suscripcion = "activa"; b.suscripcion_hasta = ahora - timedelta(days=1)
    assert plans.suscripcion_activa(b, ahora) is False


def test_limite_recursos_por_plan(db):
    b = db.query(Barberia).first()
    b.plan = "starter"  # max 2
    assert plans.limite_recursos(b) == 2


# --------- recordatorios respetan plan ---------

def test_recordatorios_no_envia_si_vencida(db):
    b = db.query(Barberia).first()
    ahora = datetime(2030, 6, 10, 9, 0)
    b.estado_suscripcion = "vencida"; b.suscripcion_hasta = ahora - timedelta(days=1)
    db.commit()
    _cita(db, b, ahora + timedelta(hours=10))
    assert enviar_recordatorios(db, b, ahora=ahora, ventana_horas=24, send=False) == 0


def test_recordatorios_respetan_cupo_mensual(db):
    b = db.query(Barberia).first()
    b.plan = "starter"; b.estado_suscripcion = "activa"
    b.suscripcion_hasta = None
    b.recordatorios_mes_ref = "2030-06"; b.recordatorios_mes_count = 200  # cupo starter agotado
    db.commit()
    ahora = datetime(2030, 6, 10, 9, 0)
    _cita(db, b, ahora + timedelta(hours=10))
    assert enviar_recordatorios(db, b, ahora=ahora, ventana_horas=24, send=False) == 0


def test_recordatorios_cuenta_uso(db):
    b = db.query(Barberia).first()
    b.plan = "pro"; b.estado_suscripcion = "activa"; b.suscripcion_hasta = None
    db.commit()
    ahora = datetime(2030, 6, 10, 9, 0)
    _cita(db, b, ahora + timedelta(hours=10))
    n = enviar_recordatorios(db, b, ahora=ahora, ventana_horas=24, send=False)
    assert n == 1
    db.refresh(b)
    assert b.recordatorios_mes_count == 1 and b.recordatorios_mes_ref == "2030-06"


# --------- suscribir / activar (simulado) ---------

def test_suscribir_simulado_devuelve_init_point(db):
    r = client.post("/api/billing/suscribir", headers=AUTH, json={"plan": "pro"})
    assert r.status_code == 200
    data = r.json()
    assert data["simulado"] is True and data["init_point"]


def test_simular_pago_activa_suscripcion(db):
    before = client.get("/api/billing/estado", headers=AUTH).json()
    assert before["estado"] == "prueba"
    client.post("/api/billing/suscribir", headers=AUTH, json={"plan": "premium"})
    r = client.post("/api/billing/simular_pago", headers=AUTH)
    assert r.status_code == 200
    after = client.get("/api/billing/estado", headers=AUTH).json()
    assert after["estado"] == "activa" and after["plan"] == "premium"
    assert after["vigente_hasta"] is not None


# --------- onboarding respeta límite de recursos ---------

def test_onboarding_rechaza_exceso_de_recursos(db):
    import pytest
    with pytest.raises(ValueError):
        crear_negocio(db, {"nombre": "Mega", "giro": "barberia", "plan": "starter",
                           "recursos": [{"nombre": f"P{i}"} for i in range(3)]})  # starter=2


def test_alta_recurso_respeta_limite(db):
    # barberia 1 sembrada con 4 barberos; en plan starter (2) ya excede
    b = db.query(Barberia).first()
    b.plan = "starter"; db.commit()
    r = client.post("/api/barberos", headers=AUTH, json={"nombre": "Extra"})
    assert r.status_code == 409
