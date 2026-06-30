from datetime import datetime

from app.models import Barberia, Barbero
from app.brain import _persona_prompt, LLMBrain
from app.branding import Textos


def test_persona_clinica(db):
    barberia = db.query(Barberia).first()
    barberia.giro = "dentista"
    barberia.termino_recurso = "doctor"
    barberos = db.query(Barbero).filter(Barbero.barberia_id == barberia.id).all()
    p = _persona_prompt(barberia, barberos, None, 30,
                        datetime(2030, 1, 1, 9, 0), Textos(barberia))
    assert "recepcionista" in p.lower()
    assert "paciente" in p.lower()
    assert "911" in p


def test_persona_no_clinica(db):
    barberia = db.query(Barberia).first()  # giro barberia por defecto
    barberos = db.query(Barbero).filter(Barbero.barberia_id == barberia.id).all()
    p = _persona_prompt(barberia, barberos, None, 45,
                        datetime(2030, 1, 1, 9, 0), Textos(barberia))
    assert "cliente" in p.lower()
    assert "911" not in p


def test_cancelar_cita_en_tools():
    assert any(tool["name"] == "cancelar_cita" for tool in LLMBrain.TOOLS)
