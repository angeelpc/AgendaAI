"""Conexion a la base de datos (SQLAlchemy)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def _migrate_sqlite():
    """Migracion ligera: agrega columnas nuevas a tablas existentes.

    create_all no altera tablas ya creadas, asi que aqui anadimos columnas
    que pudieran faltar en una BD antigua (sin perder datos).
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import text
    faltantes = {
        "citas": [
            ("recordatorio_enviado", "BOOLEAN DEFAULT 0"),
        ],
        "barberias": [
            ("giro", "VARCHAR DEFAULT 'barberia'"),
            ("logo_url", "VARCHAR DEFAULT ''"),
            ("zona_horaria", "VARCHAR DEFAULT 'America/Mexico_City'"),
            ("termino_recurso", "VARCHAR DEFAULT 'barbero'"),
            ("termino_negocio", "VARCHAR DEFAULT 'la barbería'"),
            ("emoji", "VARCHAR DEFAULT '💈'"),
            ("config_mensajes", "TEXT DEFAULT '{}'"),
        ],
    }
    with engine.begin() as conn:
        for tabla, columnas in faltantes.items():
            existentes = {row[1] for row in conn.execute(text(f"PRAGMA table_info({tabla})"))}
            for nombre, definicion in columnas:
                if nombre not in existentes:
                    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"))
