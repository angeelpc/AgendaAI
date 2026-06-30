import json
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models import Barberia, Conversacion, Mensaje
from app.service import handle_incoming

client = TestClient(app)
AUTH = {"X-Barberia-Id": "1", "X-Api-Key": "demo-key-filo"}


def test_mensajes_se_guardan(db):
    barberia = db.query(Barberia).first()
    handle_incoming(db, barberia, "5210001", "hola", send=False)
    ins = db.query(Mensaje).filter(Mensaje.telefono == "5210001",
                                   Mensaje.direccion == "in").count()
    outs = db.query(Mensaje).filter(Mensaje.telefono == "5210001",
                                    Mensaje.direccion == "out").count()
    assert ins >= 1 and outs >= 1


def test_cliente_se_registra_al_agendar(db):
    barberia = db.query(Barberia).first()
    tel = "5214445556677"
    ahora = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    handle_incoming(db, barberia, tel, "cita el sábado con el 1", ahora=ahora, send=False)
    conv = db.query(Conversacion).filter(Conversacion.telefono == tel).first()
    hora = datetime.fromisoformat(json.loads(conv.contexto)["offered"][0]).strftime("%H:%M")
    handle_incoming(db, barberia, tel, hora, ahora=ahora, send=False)
    handle_incoming(db, barberia, tel, "Pedro", ahora=ahora, send=False)
    handle_incoming(db, barberia, tel, "sí", ahora=ahora, send=False)
    cl = client.get("/api/clientes", headers=AUTH).json()
    assert any(c["telefono"] == tel and c["nombre"] == "Pedro" for c in cl)


def test_cliente_detalle_y_notas(db):
    bar = client.get("/api/barberos", headers=AUTH).json()[0]
    inicio = datetime(2030, 7, 1, 11, 0).isoformat()
    client.post("/api/citas", headers=AUTH, json={
        "barbero_id": bar["id"], "inicio": inicio,
        "cliente_nombre": "Ana", "cliente_telefono": "5219998887", "servicio": "Corte"})
    d = client.get("/api/clientes/5219998887", headers=AUTH).json()
    assert d["nombre"] == "Ana" and len(d["citas"]) >= 1
    r = client.put("/api/clientes/5219998887", headers=AUTH, json={"notas": "alergica"})
    assert r.status_code == 200
    assert client.get("/api/clientes/5219998887", headers=AUTH).json()["notas"] == "alergica"
