"""Orquestador: recibe un mensaje entrante y produce/envia la respuesta.
Comparte la logica entre el webhook real y el demo offline."""
import json
from datetime import datetime

from .models import Barberia, Conversacion, Cliente, Mensaje, Cita, Barbero
from .brain import get_brain, Reply
from .config import settings
from . import whatsapp


def registrar_cliente(db, barberia_id: int, telefono: str, nombre: str | None):
    """Crea o actualiza el registro del cliente/paciente del negocio."""
    if not telefono:
        return
    c = (db.query(Cliente)
         .filter(Cliente.barberia_id == barberia_id, Cliente.telefono == telefono)
         .first())
    if not c:
        c = Cliente(barberia_id=barberia_id, telefono=telefono, nombre=nombre or "")
        db.add(c)
    else:
        if nombre:
            c.nombre = nombre
        c.actualizado = datetime.utcnow()
    db.commit()


def log_mensaje(db, barberia_id: int, telefono: str, direccion: str, texto: str):
    """Guarda un mensaje del historial (direccion: 'in' cliente, 'out' bot)."""
    if not texto:
        return
    db.add(Mensaje(barberia_id=barberia_id, telefono=telefono,
                   direccion=direccion, texto=texto))
    db.commit()


def get_or_create_conv(db, barberia_id, telefono) -> Conversacion:
    conv = (
        db.query(Conversacion)
        .filter(Conversacion.barberia_id == barberia_id,
                Conversacion.telefono == telefono)
        .first()
    )
    if not conv:
        conv = Conversacion(barberia_id=barberia_id, telefono=telefono,
                            estado="bot", contexto="{}")
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def handle_incoming(db, barberia: Barberia, telefono: str, message: str,
                    ahora: datetime | None = None, send: bool = True) -> Reply:
    conv = get_or_create_conv(db, barberia.id, telefono)
    log_mensaje(db, barberia.id, telefono, "in", message)

    # Si ya esta en manos de un humano, el bot no responde.
    if conv.estado == "humano":
        conv.actualizada = datetime.utcnow()
        db.commit()
        return Reply(text="", meta={"silenciado": "chat en manos de un humano"})

    brain = get_brain()
    reply = brain.respond(db, barberia, conv, message, ahora=ahora)
    conv.actualizada = datetime.utcnow()
    db.commit()

    # Guardar respuesta del bot en el historial
    if reply.text:
        log_mensaje(db, barberia.id, telefono, "out", reply.text)

    # Si se agendo, registrar/actualizar al cliente y mandar invitacion de calendario
    if reply.booked_cita_id:
        cita = db.get(Cita, reply.booked_cita_id)
        if cita:
            registrar_cliente(db, barberia.id, telefono, cita.cliente_nombre)
            if send:
                try:
                    link = f"{settings.PUBLIC_BASE_URL}/ics/{cita.id}"
                    whatsapp.send_document(telefono, link, "cita.ics",
                                           "📅 Agrega tu cita al calendario",
                                           barberia.whatsapp_phone_id)
                except Exception as e:
                    print("[ics] no se pudo enviar:", e)

    if reply.text and send:
        if reply.opciones:
            if len(reply.opciones) <= 3:
                whatsapp.send_buttons(telefono, reply.text, reply.opciones,
                                      barberia.whatsapp_phone_id)
            else:
                whatsapp.send_list(telefono, reply.text, "Ver opciones",
                                   reply.opciones, barberia.whatsapp_phone_id)
        else:
            whatsapp.send_text(telefono, reply.text, barberia.whatsapp_phone_id)

    # Notificar al admin si se escalo
    if reply.escalate and barberia.admin_phone and send:
        whatsapp.send_text(
            barberia.admin_phone,
            f"⚠️ Cliente {telefono} necesita atencion humana. Mensaje: \"{message}\"",
            barberia.whatsapp_phone_id,
        )
    return reply
