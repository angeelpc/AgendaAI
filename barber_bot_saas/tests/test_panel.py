from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.models import Barberia, Cita, Barbero
from app.service import handle_incoming
from app.database import SessionLocal

client = TestClient(app)
AUTH = {"X-Barberia-Id": "1", "X-Api-Key": "demo-key-filo"}


def _ahora():
    return datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)


def test_login_ok_y_falla(db):
    assert client.post("/api/login", json={"barberia_id": 1, "api_key": "demo-key-filo"}).status_code == 200
    assert client.post("/api/login", json={"barberia_id": 1, "api_key": "mala"}).status_code == 401


def test_panel_requiere_auth(db):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers=AUTH).status_code == 200


def test_dashboard_y_citas(db):
    barberia = db.query(Barberia).first()
    # generar una cita real via conversacion
    tel = "5214445556677"
    ahora = _ahora()
    handle_incoming(db, barberia, tel, "cita el sábado con el 2", ahora=ahora, send=False)
    # leer slot ofrecido
    import json
    from app.models import Conversacion
    conv = db.query(Conversacion).filter(Conversacion.telefono == tel).first()
    hora = datetime.fromisoformat(json.loads(conv.contexto)["offered"][0]).strftime("%H:%M")
    handle_incoming(db, barberia, tel, hora, ahora=ahora, send=False)
    handle_incoming(db, barberia, tel, "Pedro", ahora=ahora, send=False)
    handle_incoming(db, barberia, tel, "sí", ahora=ahora, send=False)

    d = client.get("/api/dashboard", headers=AUTH).json()
    assert d["barberos"] == 4
    citas = client.get("/api/citas", headers=AUTH).json()
    assert any(c["cliente"] == "Pedro" for c in citas)


def test_cancelar_cita(db):
    barberia = db.query(Barberia).first()
    ag = db.query(Barbero).filter(Barbero.numero == 1).first()
    cita = Cita(barberia_id=barberia.id, barbero_id=ag.id, cliente_nombre="X",
                cliente_telefono="521", servicio="Corte",
                inicio=datetime(2030, 1, 1, 10), fin=datetime(2030, 1, 1, 10, 45))
    db.add(cita); db.commit(); db.refresh(cita)
    r = client.post(f"/api/citas/{cita.id}/cancelar", headers=AUTH)
    assert r.status_code == 200
    db.refresh(cita)
    assert cita.estado == "cancelada"


def test_editar_barbero(db):
    barberos = client.get("/api/barberos", headers=AUTH).json()
    bid = barberos[0]["id"]
    r = client.put(f"/api/barberos/{bid}", headers=AUTH,
                   json={"work_start": "08:00", "work_end": "21:00"})
    assert r.status_code == 200
    again = client.get("/api/barberos", headers=AUTH).json()
    assert again[0]["work_start"] == "08:00"


def test_devolver_chat_al_bot(db):
    barberia = db.query(Barberia).first()
    tel = "5218889990000"
    handle_incoming(db, barberia, tel, "quiero un reembolso", ahora=_ahora(), send=False)
    convs = client.get("/api/conversaciones?estado=humano", headers=AUTH).json()
    assert len(convs) >= 1
    cid = convs[0]["id"]
    assert client.post(f"/api/conversaciones/{cid}/devolver_bot", headers=AUTH).status_code == 200
    assert client.get("/api/conversaciones?estado=humano", headers=AUTH).json() == \
        [c for c in client.get("/api/conversaciones?estado=humano", headers=AUTH).json()]


def test_pagina_panel_se_sirve(db):
    r = client.get("/panel")
    assert r.status_code == 200
    assert "Barber" in r.text and "Clave de acceso" in r.text


def test_servicios_crud(db):
    # parte de 1 servicio sembrado (Corte)
    base = client.get("/api/servicios", headers=AUTH).json()
    assert any(s["nombre"] == "Corte" for s in base)

    # crear
    r = client.post("/api/servicios", headers=AUTH,
                    json={"nombre": "Barba", "duracion_min": 30, "precio": 100})
    assert r.status_code == 200
    sid = r.json()["id"]

    # editar
    r = client.put(f"/api/servicios/{sid}", headers=AUTH, json={"precio": 120})
    assert r.status_code == 200
    assert next(s for s in client.get("/api/servicios", headers=AUTH).json()
                if s["id"] == sid)["precio"] == 120

    # borrar
    assert client.delete(f"/api/servicios/{sid}", headers=AUTH).status_code == 200
    assert all(s["id"] != sid for s in client.get("/api/servicios", headers=AUTH).json())


def test_crear_cita_manual(db):
    bar = client.get("/api/barberos", headers=AUTH).json()[0]
    inicio = datetime(2030, 6, 1, 11, 0).isoformat()
    r = client.post("/api/citas", headers=AUTH, json={
        "barbero_id": bar["id"], "inicio": inicio,
        "cliente_nombre": "Walk In", "cliente_telefono": "5210000",
        "servicio": "Corte"})
    assert r.status_code == 200
    citas = client.get("/api/citas", headers=AUTH).json()
    assert any(c["cliente"] == "Walk In" for c in citas)

    # no doble reserva en el mismo slot
    r2 = client.post("/api/citas", headers=AUTH, json={
        "barbero_id": bar["id"], "inicio": inicio,
        "cliente_nombre": "Otro", "servicio": "Corte"})
    assert r2.status_code == 409


def test_config_get_y_update(db):
    base = client.get("/api/config", headers=AUTH).json()
    assert base["termino_recurso"] == "barbero"
    r = client.put("/api/config", headers=AUTH, json={
        "termino_recurso": "doctor", "termino_negocio": "la clínica",
        "mensajes": {"saludo": "¡Bienvenido a la clínica!"}})
    assert r.status_code == 200
    after = client.get("/api/config", headers=AUTH).json()
    assert after["termino_recurso"] == "doctor"
    assert after["mensajes"]["saludo"] == "¡Bienvenido a la clínica!"


def test_config_mensaje_vacio_se_limpia(db):
    client.put("/api/config", headers=AUTH, json={"mensajes": {"saludo": "hola"}})
    client.put("/api/config", headers=AUTH, json={"mensajes": {"saludo": "   "}})
    after = client.get("/api/config", headers=AUTH).json()
    assert "saludo" not in after["mensajes"]


def test_marcar_no_show(db):
    barberia = db.query(Barberia).first()
    ag = db.query(Barbero).filter(Barbero.numero == 1).first()
    cita = Cita(barberia_id=barberia.id, barbero_id=ag.id, cliente_nombre="NS",
                cliente_telefono="521", servicio="Corte",
                inicio=datetime.now().replace(microsecond=0),
                fin=datetime.now().replace(microsecond=0))
    db.add(cita); db.commit(); db.refresh(cita)
    assert client.post(f"/api/citas/{cita.id}/no_show", headers=AUTH).status_code == 200
    db.refresh(cita)
    assert cita.estado == "no_show"
    assert client.get("/api/dashboard", headers=AUTH).json()["no_shows_30d"] >= 1
