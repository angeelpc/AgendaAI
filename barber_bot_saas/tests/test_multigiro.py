"""El mismo bot, configurado como otro giro, responde con su propio vocabulario."""
from datetime import datetime, timedelta

from app.models import Barberia, Cita, Barbero
from app.service import handle_incoming
from app.reminders import enviar_recordatorios
from app.branding import Textos


def _config_dentista(db):
    b = db.query(Barberia).first()
    b.giro = "dentista"
    b.termino_recurso = "doctor"
    b.termino_negocio = "la clínica"
    b.emoji = "🦷"
    db.commit()
    return b


def test_saludo_usa_termino_del_giro(db):
    _config_dentista(db)
    barberia = db.query(Barberia).first()
    r = handle_incoming(db, barberia, "5210001112", "quiero una cita",
                        ahora=datetime(2030, 6, 10, 9, 0), send=False)
    assert "doctor" in r.text.lower()
    assert "barbero" not in r.text.lower()


def test_escalacion_usa_nombre_del_negocio(db):
    _config_dentista(db)
    barberia = db.query(Barberia).first()
    r = handle_incoming(db, barberia, "5210002223", "quiero un reembolso",
                        ahora=datetime(2030, 6, 10, 9, 0), send=False)
    assert r.escalate
    assert "la clínica" in r.text


def test_recordatorio_usa_emoji_y_negocio(db):
    barberia = _config_dentista(db)
    bar = db.query(Barbero).filter(Barbero.numero == 1).first()
    ahora = datetime(2030, 6, 10, 9, 0)
    cita = Cita(barberia_id=barberia.id, barbero_id=bar.id, cliente_nombre="Ana",
                cliente_telefono="5219998887", servicio="Consulta",
                inicio=ahora + timedelta(hours=10), fin=ahora + timedelta(hours=11),
                estado="agendada")
    db.add(cita); db.commit()
    # capturar el texto sin enviar de verdad
    t = Textos(barberia)
    msg = t.recordatorio("Ana", "lunes", "19:00", bar.nombre)
    assert "la clínica" in msg and "🦷" in msg


def test_default_sigue_siendo_barberia(db):
    """Sin configurar nada, un negocio mantiene el vocabulario de barbería."""
    barberia = db.query(Barberia).first()
    r = handle_incoming(db, barberia, "5210003334", "quiero una cita",
                        ahora=datetime(2030, 6, 10, 9, 0), send=False)
    assert "barbero" in r.text.lower()
