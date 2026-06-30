import os
import tempfile
import pytest

# Base de datos temporal por sesion de test (antes de importar la app)
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["ANTHROPIC_API_KEY"] = ""  # forzar motor de reglas
os.environ["SCHEDULER_ENABLED"] = "0"  # no arrancar el cron durante pruebas

from app.database import SessionLocal, init_db  # noqa: E402
from app.seed import seed  # noqa: E402
from app.models import Cita, Conversacion, Cliente, Mensaje, MetricaIA  # noqa: E402


@pytest.fixture()
def db():
    init_db()
    seed(reset=True)
    s = SessionLocal()
    # aislamiento: seed no limpia citas ni conversaciones y el id de barberia
    # vuelve a 1 en cada reseed, asi que las vaciamos para no arrastrar estado.
    s.query(Cita).delete()
    s.query(Conversacion).delete()
    s.query(Cliente).delete()
    s.query(Mensaje).delete()
    s.query(MetricaIA).delete()
    s.commit()
    yield s
    s.close()
