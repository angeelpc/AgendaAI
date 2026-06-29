"""Modelos multi-tenant. Cada registro pertenece a una barberia (barberia_id)."""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, Date, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship

from .database import Base


class Barberia(Base):
    """Negocio (tenant). Internamente la tabla se llama 'barberias' por
    compatibilidad, pero representa cualquier giro basado en citas."""
    __tablename__ = "barberias"
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    whatsapp_phone_id = Column(String, unique=True)   # phone_number_id de Cloud API
    admin_phone = Column(String)                       # a quien se le escalan los chats
    plan = Column(String, default="pro")
    activo = Column(Boolean, default=True)
    api_key = Column(String, default="")               # acceso al panel web

    # --- Personalizacion multi-giro ---
    giro = Column(String, default="barberia")          # barberia | dentista | veterinaria | ...
    logo_url = Column(String, default="")
    zona_horaria = Column(String, default="America/Mexico_City")
    termino_recurso = Column(String, default="barbero")   # como llamar al profesional
    termino_negocio = Column(String, default="la barbería")
    emoji = Column(String, default="💈")
    config_mensajes = Column(Text, default="{}")       # overrides de textos (JSON)

    barberos = relationship("Barbero", back_populates="barberia")
    servicios = relationship("Servicio", back_populates="barberia")


class Barbero(Base):
    __tablename__ = "barberos"
    id = Column(Integer, primary_key=True)
    barberia_id = Column(Integer, ForeignKey("barberias.id"))
    numero = Column(Integer)            # 1..4
    nombre = Column(String, nullable=False)
    work_start = Column(String, default="10:00")   # "HH:MM"
    work_end = Column(String, default="20:00")
    days_off = Column(String, default="0")          # weekday ints csv (0=lunes)

    barberia = relationship("Barberia", back_populates="barberos")

    def dias_libres(self):
        return {int(x) for x in self.days_off.split(",") if x.strip() != ""}


class Servicio(Base):
    __tablename__ = "servicios"
    id = Column(Integer, primary_key=True)
    barberia_id = Column(Integer, ForeignKey("barberias.id"))
    nombre = Column(String, nullable=False)
    duracion_min = Column(Integer, default=45)
    precio = Column(Integer, default=0)

    barberia = relationship("Barberia", back_populates="servicios")


class Cita(Base):
    __tablename__ = "citas"
    id = Column(Integer, primary_key=True)
    barberia_id = Column(Integer, ForeignKey("barberias.id"))
    barbero_id = Column(Integer, ForeignKey("barberos.id"))
    cliente_nombre = Column(String)
    cliente_telefono = Column(String)
    servicio = Column(String)
    inicio = Column(DateTime, nullable=False)
    fin = Column(DateTime, nullable=False)
    estado = Column(String, default="agendada")   # agendada | cancelada | completada | no_show
    creada = Column(DateTime, default=datetime.utcnow)
    recordatorio_enviado = Column(Boolean, default=False)   # evita reenviar el recordatorio


class Conversacion(Base):
    __tablename__ = "conversaciones"
    id = Column(Integer, primary_key=True)
    barberia_id = Column(Integer, ForeignKey("barberias.id"))
    telefono = Column(String, index=True)
    estado = Column(String, default="bot")        # bot | humano
    contexto = Column(Text, default="{}")          # JSON de slots en progreso
    actualizada = Column(DateTime, default=datetime.utcnow)
