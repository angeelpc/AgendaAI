"""Conexion a la base de datos (SQLAlchemy)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

# Railway/Heroku a veces entregan "postgres://"; SQLAlchemy 2.x exige "postgresql://".
DB_URL = settings.DATABASE_URL
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args, future=True)
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
    _migrate()


def _migrate():
    """Migracion ligera y multi-dialecto: agrega columnas que falten a tablas
    existentes (SQLite y PostgreSQL). create_all no altera tablas ya creadas."""
    from sqlalchemy import text, inspect
    es_sqlite = DB_URL.startswith("sqlite")
    bool_def = "BOOLEAN DEFAULT 0" if es_sqlite else "BOOLEAN DEFAULT FALSE"
    dt_type = "DATETIME" if es_sqlite else "TIMESTAMP"
    faltantes = {
        "citas": [
            ("recordatorio_enviado", bool_def),
        ],
        "barberos": [
            ("bloques", "VARCHAR DEFAULT ''"),
        ],
        "barberias": [
            ("giro", "VARCHAR DEFAULT 'barberia'"),
            ("logo_url", "VARCHAR DEFAULT ''"),
            ("zona_horaria", "VARCHAR DEFAULT 'America/Mexico_City'"),
            ("termino_recurso", "VARCHAR DEFAULT 'barbero'"),
            ("termino_negocio", "VARCHAR DEFAULT 'la barbería'"),
            ("emoji", "VARCHAR DEFAULT '💈'"),
            ("config_mensajes", "TEXT DEFAULT '{}'"),
            ("estado_suscripcion", "VARCHAR DEFAULT 'prueba'"),
            ("suscripcion_hasta", dt_type),
            ("mp_preapproval_id", "VARCHAR DEFAULT ''"),
            ("recordatorios_mes_ref", "VARCHAR DEFAULT ''"),
            ("recordatorios_mes_count", "INTEGER DEFAULT 0"),
            ("instrucciones_ia", "TEXT DEFAULT ''"),
        ],
    }
    insp = inspect(engine)
    tablas = set(insp.get_table_names())
    with engine.begin() as conn:
        for tabla, columnas in faltantes.items():
            if tabla not in tablas:
                continue
            existentes = {c["name"] for c in insp.get_columns(tabla)}
            for nombre, definicion in columnas:
                if nombre not in existentes:
                    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"))
