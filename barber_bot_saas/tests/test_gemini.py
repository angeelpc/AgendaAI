from app.brain import RuleBrain, GeminiBrain, LLMBrain, get_brain
from app.config import settings


def test_get_brain_reglas_por_defecto(db):
    assert isinstance(get_brain(), RuleBrain)


def test_get_brain_elige_gemini(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AIza-test")
    assert isinstance(get_brain(), GeminiBrain)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")


def test_tools_compartidas():
    nombres = {t["name"] for t in LLMBrain.TOOLS}
    assert {"consultar_disponibilidad", "agendar_cita",
            "cancelar_cita", "escalar_a_humano"} <= nombres
