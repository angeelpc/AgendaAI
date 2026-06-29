"""Alta self-service de negocios (onboarding).

Crea un tenant nuevo y lo deja listo para operar, sin tocar codigo:
- Genera su `api_key` para el panel.
- Da de alta sus recursos (profesionales) y servicios.
- Guarda terminologia y mensajes personalizados.

Se puede usar de tres formas:
- Programatica:  crear_negocio(db, datos)         (la usa el endpoint y el wizard web)
- CLI guiada:    python -m app.onboarding
- API/web:       POST /api/negocios  (ver app/panel.py)

Cada giro trae un *preset* con terminologia, emoji y servicios sugeridos, para
que el alta sea de pocos clics; todo es sobreescribible.
"""
import json
import secrets

from .database import SessionLocal, init_db
from .models import Barberia, Barbero, Servicio


# ----------------------------- presets por giro -----------------------------

PRESETS = {
    "barberia": {
        "termino_recurso": "barbero", "termino_negocio": "la barbería", "emoji": "💈",
        "servicios": [{"nombre": "Corte", "duracion_min": 45, "precio": 150}],
    },
    "estetica": {
        "termino_recurso": "estilista", "termino_negocio": "la estética", "emoji": "💇",
        "servicios": [
            {"nombre": "Corte", "duracion_min": 45, "precio": 200},
            {"nombre": "Tinte", "duracion_min": 90, "precio": 600},
        ],
    },
    "dentista": {
        "termino_recurso": "doctor", "termino_negocio": "la clínica", "emoji": "🦷",
        "servicios": [
            {"nombre": "Consulta", "duracion_min": 30, "precio": 500},
            {"nombre": "Limpieza", "duracion_min": 45, "precio": 800},
        ],
    },
    "veterinaria": {
        "termino_recurso": "veterinario", "termino_negocio": "la veterinaria", "emoji": "🐾",
        "servicios": [
            {"nombre": "Consulta", "duracion_min": 30, "precio": 400},
            {"nombre": "Vacunación", "duracion_min": 20, "precio": 350},
        ],
    },
    "spa": {
        "termino_recurso": "terapeuta", "termino_negocio": "el spa", "emoji": "💆",
        "servicios": [{"nombre": "Masaje", "duracion_min": 60, "precio": 700}],
    },
    "default": {
        "termino_recurso": "profesional", "termino_negocio": "el negocio", "emoji": "📅",
        "servicios": [{"nombre": "Servicio", "duracion_min": 45, "precio": 0}],
    },
}


def preset_de(giro: str) -> dict:
    return PRESETS.get((giro or "").lower(), PRESETS["default"])


# ----------------------------- alta de negocio -----------------------------

def crear_negocio(db, datos: dict) -> dict:
    """Crea un negocio (tenant) completo. Devuelve id, nombre y api_key.

    `datos` admite:
      nombre (req), giro, zona_horaria, logo_url,
      termino_recurso, termino_negocio, emoji,
      admin_phone, whatsapp_phone_id, plan, api_key,
      recursos: [{nombre, work_start, work_end, days_off}],
      servicios: [{nombre, duracion_min, precio}],
      mensajes: {saludo, escalacion, recordatorio, ...}
    """
    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        raise ValueError("El nombre del negocio es obligatorio.")

    giro = (datos.get("giro") or "barberia").lower()
    p = preset_de(giro)

    api_key = datos.get("api_key") or secrets.token_hex(8)
    mensajes = datos.get("mensajes") or {}

    negocio = Barberia(
        nombre=nombre,
        giro=giro,
        zona_horaria=datos.get("zona_horaria") or "America/Mexico_City",
        logo_url=datos.get("logo_url") or "",
        termino_recurso=datos.get("termino_recurso") or p["termino_recurso"],
        termino_negocio=datos.get("termino_negocio") or p["termino_negocio"],
        emoji=datos.get("emoji") or p["emoji"],
        config_mensajes=json.dumps(mensajes, ensure_ascii=False),
        admin_phone=datos.get("admin_phone") or "",
        whatsapp_phone_id=datos.get("whatsapp_phone_id") or None,
        plan=datos.get("plan") or "pro",
        activo=True,
        api_key=api_key,
    )
    db.add(negocio)
    db.flush()  # obtener id sin cerrar la transaccion

    # recursos (profesionales). Si no mandan, crea uno generico.
    recursos = datos.get("recursos") or [{"nombre": f"{p['termino_recurso'].capitalize()} 1"}]
    for i, r in enumerate(recursos, start=1):
        db.add(Barbero(
            barberia_id=negocio.id, numero=i,
            nombre=(r.get("nombre") or f"{p['termino_recurso'].capitalize()} {i}"),
            work_start=r.get("work_start") or "10:00",
            work_end=r.get("work_end") or "20:00",
            days_off=r.get("days_off") or "0",
        ))

    # servicios. Si no mandan, usa los sugeridos del giro.
    servicios = datos.get("servicios") or p["servicios"]
    for s in servicios:
        db.add(Servicio(
            barberia_id=negocio.id,
            nombre=s.get("nombre") or "Servicio",
            duracion_min=int(s.get("duracion_min") or 45),
            precio=int(s.get("precio") or 0),
        ))

    db.commit()
    db.refresh(negocio)
    return {"id": negocio.id, "nombre": negocio.nombre, "giro": negocio.giro,
            "api_key": negocio.api_key}


# ----------------------------- CLI guiada -----------------------------

def _cli():
    init_db()
    db = SessionLocal()
    try:
        print("\n=== Alta de negocio nuevo ===\n")
        nombre = input("Nombre del negocio: ").strip()
        print("Giros: " + ", ".join(k for k in PRESETS if k != "default"))
        giro = input("Giro [barberia]: ").strip() or "barberia"
        p = preset_de(giro)
        print(f"  -> término por defecto: '{p['termino_recurso']}'  emoji: {p['emoji']}")
        termino = input(f"¿Cómo llamar al profesional? [{p['termino_recurso']}]: ").strip()
        admin = input("WhatsApp del dueño (para escalaciones): ").strip()
        phone_id = input("phone_number_id de WhatsApp Cloud API (opcional): ").strip()

        try:
            n_rec = int(input("¿Cuántos profesionales? [1]: ").strip() or "1")
        except ValueError:
            n_rec = 1
        recursos = []
        for i in range(1, n_rec + 1):
            nom = input(f"  Nombre del profesional {i}: ").strip() or f"{p['termino_recurso'].capitalize()} {i}"
            recursos.append({"nombre": nom})

        datos = {
            "nombre": nombre, "giro": giro,
            "termino_recurso": termino or None,
            "admin_phone": admin, "whatsapp_phone_id": phone_id or None,
            "recursos": recursos,
        }
        res = crear_negocio(db, datos)
        print("\n✅ Negocio creado:")
        print(f"   id       = {res['id']}")
        print(f"   nombre   = {res['nombre']}")
        print(f"   api_key  = {res['api_key']}   (para entrar al panel)")
        print(f"\nAbre el panel e ingresa con id={res['id']} y esa clave.\n")
    finally:
        db.close()


if __name__ == "__main__":
    _cli()
