"""Orquestador: recibe un mensaje entrante y produce/envia la respuesta.
Comparte la logica entre el webhook real y el demo offline."""
import json
from datetime import datetime

from .models import Barberia, Conversacion
from .brain import get_brain, Reply
from . import whatsapp


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

    # Si ya esta en manos de un humano, el bot no responde.
    if conv.estado == "humano":
        conv.actualizada = datetime.utcnow()
        db.commit()
        return Reply(text="", meta={"silenciado": "chat en manos de un humano"})

    brain = get_brain()
    reply = brain.respond(db, barberia, conv, message, ahora=ahora)
    conv.actualizada = datetime.utcnow()
    db.commit()

    if reply.text and send:
        whatsapp.send_text(telefono, reply.text, barberia.whatsapp_phone_id)

    # Notificar al admin si se escalo
    if reply.escalate and barberia.admin_phone and send:
        whatsapp.send_text(
            barberia.admin_phone,
            f"⚠️ Cliente {telefono} necesita atencion humana. Mensaje: \"{message}\"",
            barberia.whatsapp_phone_id,
        )
    return reply
