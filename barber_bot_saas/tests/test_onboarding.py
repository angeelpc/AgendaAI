from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.onboarding import crear_negocio
from app.models import Barberia, Barbero, Servicio

client = TestClient(app)
ADMIN = {"X-Admin-Key": settings.PLATFORM_ADMIN_KEY}


def test_crear_negocio_dentista_con_preset(db):
    res = crear_negocio(db, {"nombre": "Clínica Sonríe", "giro": "dentista",
                             "recursos": [{"nombre": "Dra. López"}]})
    assert res["api_key"]
    neg = db.get(Barberia, res["id"])
    assert neg.termino_recurso == "doctor" and neg.emoji == "🦷"
    # preset sembró servicios del giro
    servs = db.query(Servicio).filter(Servicio.barberia_id == neg.id).all()
    assert any(s.nombre == "Limpieza" for s in servs)
    assert db.query(Barbero).filter(Barbero.barberia_id == neg.id).count() == 1


def test_login_con_api_key_generada(db):
    res = crear_negocio(db, {"nombre": "Vet Patitas", "giro": "veterinaria"})
    r = client.post("/api/login", json={"barberia_id": res["id"], "api_key": res["api_key"]})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Vet Patitas"


def test_aislamiento_entre_tenants(db):
    a = crear_negocio(db, {"nombre": "Negocio A", "giro": "barberia"})
    b = crear_negocio(db, {"nombre": "Negocio B", "giro": "estetica"})
    auth_a = {"X-Barberia-Id": str(a["id"]), "X-Api-Key": a["api_key"]}
    # la api_key de A no debe servir para entrar como B
    bad = {"X-Barberia-Id": str(b["id"]), "X-Api-Key": a["api_key"]}
    assert client.get("/api/dashboard", headers=auth_a).status_code == 200
    assert client.get("/api/dashboard", headers=bad).status_code == 401


def test_endpoint_alta_requiere_admin_key(db):
    payload = {"nombre": "Sin permiso", "giro": "barberia"}
    assert client.post("/api/negocios", json=payload, headers={"X-Admin-Key": "mala"}).status_code == 401
    r = client.post("/api/negocios", json=payload, headers=ADMIN)
    assert r.status_code == 200 and r.json()["ok"] is True


def test_alta_sin_nombre_falla(db):
    r = client.post("/api/negocios", json={"giro": "spa"}, headers=ADMIN)
    assert r.status_code == 400


def test_presets_y_paginas_se_sirven(db):
    assert "dentista" in client.get("/api/onboarding/presets").json()
    assert client.get("/alta").status_code == 200
