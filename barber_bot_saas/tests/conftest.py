import os
import tempfile
import pytest

# Base de datos temporal por sesion de test (antes de importar la app)
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["ANTHROPIC_API_KEY"] = ""  # forzar motor de reglas

from app.database import SessionLocal, init_db  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture()
def db():
    init_db()
    seed(reset=True)
    s = SessionLocal()
    yield s
    s.close()
