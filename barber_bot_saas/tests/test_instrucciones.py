from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models import Barberia, Barbero
from app.brain import _persona_prompt
from app.branding import Textos

client = TestClient(app)
AUTH = {"X-Barberia-Id": "1", "X-Api-Key": "demo-key-filo"}


def test_instrucciones_en_prompt(db):
    barberia = db.query(Barberia).first()
    barberia.instrucciones_ia = "Ofrece primero horarios de la mañana."
    barberos = db.query(Barbero).filter(Barbero.barberia_id == barberia.id).all()
    p = _persona_prompt(barberia, barberos, None, 45,
                        datetime(2030, 1, 1, 9, 0), Textos(barberia))
    assert "Ofrece primero horarios de la mañana" in p


def test_config_guarda_instrucciones(db):
    client.put("/api/config", headers=AUTH, json={"instrucciones_ia": "No agendar menores solos."})
    c = client.get("/api/config", headers=AUTH).json()
    assert c["instrucciones_ia"] == "No agendar menores solos."
