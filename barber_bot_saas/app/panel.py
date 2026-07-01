"""Panel web de la barberia: API REST + servir la pagina.

Autenticacion simple por barberia: se envia X-Barberia-Id y X-Api-Key en cada
peticion. Cada barberia solo ve y edita lo suyo (multi-tenant).
"""
import json
from datetime import datetime, date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .database import get_db
from .models import Barberia, Barbero, Cita, Conversacion, Servicio, Cliente, Mensaje
from .agenda import AgendaService
from .service import registrar_cliente
from .reminders import citas_por_recordar, enviar_recordatorios
from .config import settings
from .onboarding import crear_negocio, PRESETS
from . import plans, billing

router = APIRouter()
STATIC = Path(__file__).resolve().parent.parent / "static"


# --------------------------- autenticacion ---------------------------

def current_barberia(
    db: Session = Depends(get_db),
    x_barberia_id: int = Header(None),
    x_api_key: str = Header(None),
) -> Barberia:
    b = db.get(Barberia, x_barberia_id) if x_barberia_id else None
    if not b or not b.api_key or b.api_key != x_api_key:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    return b


# --------------------------- pagina ---------------------------

@router.get("/panel", response_class=HTMLResponse)
def panel_page():
    f = STATIC / "panel.html"
    if not f.exists():
        return HTMLResponse("<h1>panel.html no encontrado</h1>", status_code=404)
    return HTMLResponse(f.read_text(encoding="utf-8"))


@router.get("/alta", response_class=HTMLResponse)
def alta_page():
    f = STATIC / "alta.html"
    if not f.exists():
        return HTMLResponse("<h1>alta.html no encontrado</h1>", status_code=404)
    return HTMLResponse(f.read_text(encoding="utf-8"))


# --------------------------- onboarding (superadmin) ---------------------------

@router.get("/api/onboarding/presets")
def onboarding_presets():
    """Presets por giro para el wizard (términos, emoji, servicios sugeridos)."""
    return {giro: {k: v for k, v in p.items()} for giro, p in PRESETS.items()}


@router.post("/api/negocios")
def alta_negocio(datos: dict, x_admin_key: str = Header(None),
                 db: Session = Depends(get_db)):
    """Crea un negocio nuevo. Requiere la clave de superadmin de la plataforma."""
    if not settings.PLATFORM_ADMIN_KEY or x_admin_key != settings.PLATFORM_ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Clave de administrador inválida")
    try:
        res = crear_negocio(db, datos)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409,
                            detail="Ese phone_number_id ya está registrado en otro negocio")
    return {"ok": True, **res}


# --------------------------- login ---------------------------

class LoginIn(BaseModel):
    barberia_id: int
    api_key: str


@router.post("/api/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    b = db.get(Barberia, data.barberia_id)
    if not b or b.api_key != data.api_key:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    return {"id": b.id, "nombre": b.nombre, "plan": b.plan}


# --------------------------- dashboard ---------------------------

@router.get("/api/dashboard")
def dashboard(b: Barberia = Depends(current_barberia), db: Session = Depends(get_db)):
    hoy = date.today()
    inicio_hoy = datetime.combine(hoy, datetime.min.time())
    fin_hoy = inicio_hoy + timedelta(days=1)
    fin_semana = inicio_hoy + timedelta(days=7)

    base = db.query(Cita).filter(Cita.barberia_id == b.id, Cita.estado == "agendada")
    citas_hoy = base.filter(Cita.inicio >= inicio_hoy, Cita.inicio < fin_hoy).count()
    citas_semana = base.filter(Cita.inicio >= inicio_hoy, Cita.inicio < fin_semana).count()
    escalados = (
        db.query(Conversacion)
        .filter(Conversacion.barberia_id == b.id, Conversacion.estado == "humano")
        .count()
    )
    # No-shows de los ultimos 30 dias (indicador clave para barberias)
    hace_30 = inicio_hoy - timedelta(days=30)
    no_shows = (
        db.query(Cita)
        .filter(Cita.barberia_id == b.id, Cita.estado == "no_show",
                Cita.inicio >= hace_30)
        .count()
    )
    recordatorios_pendientes = len(
        citas_por_recordar(db, b.id, datetime.now(), settings.REMINDER_HOURS)
    )
    return {
        "citas_hoy": citas_hoy,
        "citas_semana": citas_semana,
        "chats_escalados": escalados,
        "barberos": db.query(Barbero).filter(Barbero.barberia_id == b.id).count(),
        "no_shows_30d": no_shows,
        "recordatorios_pendientes": recordatorios_pendientes,
    }


@router.post("/api/recordatorios/enviar")
def enviar_recordatorios_ahora(b: Barberia = Depends(current_barberia),
                               db: Session = Depends(get_db)):
    """Envia ahora los recordatorios pendientes de esta barberia."""
    n = enviar_recordatorios(db, b)
    return {"ok": True, "enviados": n}


# --------------------------- citas ---------------------------

@router.get("/api/citas")
def citas(b: Barberia = Depends(current_barberia), db: Session = Depends(get_db),
          desde: str = None):
    q = db.query(Cita).filter(Cita.barberia_id == b.id, Cita.estado == "agendada")
    if desde:
        q = q.filter(Cita.inicio >= datetime.fromisoformat(desde))
    citas = q.order_by(Cita.inicio).all()
    barberos = {x.id: x.nombre for x in db.query(Barbero).filter(Barbero.barberia_id == b.id)}
    return [
        {"id": c.id, "cliente": c.cliente_nombre, "telefono": c.cliente_telefono,
         "barbero": barberos.get(c.barbero_id, "?"), "inicio": c.inicio.isoformat(),
         "servicio": c.servicio}
        for c in citas
    ]


@router.post("/api/citas/{cita_id}/cancelar")
def cancelar_cita(cita_id: int, b: Barberia = Depends(current_barberia),
                  db: Session = Depends(get_db)):
    c = db.get(Cita, cita_id)
    if not c or c.barberia_id != b.id:
        raise HTTPException(404, "No encontrada")
    c.estado = "cancelada"
    db.commit()
    return {"ok": True}


@router.post("/api/citas/{cita_id}/completar")
def completar_cita(cita_id: int, b: Barberia = Depends(current_barberia),
                   db: Session = Depends(get_db)):
    c = db.get(Cita, cita_id)
    if not c or c.barberia_id != b.id:
        raise HTTPException(404, "No encontrada")
    c.estado = "completada"
    db.commit()
    return {"ok": True}


@router.post("/api/citas/{cita_id}/no_show")
def marcar_no_show(cita_id: int, b: Barberia = Depends(current_barberia),
                   db: Session = Depends(get_db)):
    c = db.get(Cita, cita_id)
    if not c or c.barberia_id != b.id:
        raise HTTPException(404, "No encontrada")
    c.estado = "no_show"
    db.commit()
    return {"ok": True}


class CitaIn(BaseModel):
    barbero_id: int
    inicio: str               # ISO "2026-06-30T16:45"
    cliente_nombre: str
    cliente_telefono: str = ""
    servicio: str | None = None


@router.post("/api/citas")
def crear_cita(data: CitaIn, b: Barberia = Depends(current_barberia),
               db: Session = Depends(get_db)):
    """Alta manual de cita (walk-in / llamada). Respeta no doble reserva."""
    barbero = db.get(Barbero, data.barbero_id)
    if not barbero or barbero.barberia_id != b.id:
        raise HTTPException(404, "Barbero no encontrado")

    # duracion segun el servicio elegido (o el primero de la barberia)
    serv = None
    if data.servicio:
        serv = (db.query(Servicio)
                .filter(Servicio.barberia_id == b.id, Servicio.nombre == data.servicio)
                .first())
    if not serv:
        serv = db.query(Servicio).filter(Servicio.barberia_id == b.id).first()
    duracion = serv.duracion_min if serv else 45
    nombre_serv = serv.nombre if serv else (data.servicio or "Corte")

    try:
        inicio = datetime.fromisoformat(data.inicio)
    except ValueError:
        raise HTTPException(400, "Fecha/hora invalida")

    ag = AgendaService(db, b.id)
    try:
        cita = ag.book(barbero, inicio, duracion, data.cliente_nombre,
                       data.cliente_telefono, nombre_serv)
    except ValueError as e:
        raise HTTPException(409, str(e))
    registrar_cliente(db, b.id, data.cliente_telefono, data.cliente_nombre)
    return {"ok": True, "id": cita.id}


# --------------------------- barberos ---------------------------

@router.get("/api/barberos")
def barberos(b: Barberia = Depends(current_barberia), db: Session = Depends(get_db)):
    rows = (db.query(Barbero).filter(Barbero.barberia_id == b.id)
            .order_by(Barbero.numero).all())
    return [
        {"id": r.id, "numero": r.numero, "nombre": r.nombre,
         "work_start": r.work_start, "work_end": r.work_end, "days_off": r.days_off,
         "bloques": r.bloques or ""}
        for r in rows
    ]


class BarberoIn(BaseModel):
    nombre: str | None = None
    work_start: str | None = None
    work_end: str | None = None
    days_off: str | None = None
    bloques: str | None = None


@router.put("/api/barberos/{barbero_id}")
def editar_barbero(barbero_id: int, data: BarberoIn,
                   b: Barberia = Depends(current_barberia),
                   db: Session = Depends(get_db)):
    r = db.get(Barbero, barbero_id)
    if not r or r.barberia_id != b.id:
        raise HTTPException(404, "No encontrado")
    for campo, valor in data.model_dump(exclude_none=True).items():
        setattr(r, campo, valor)
    db.commit()
    return {"ok": True}


@router.post("/api/barberos")
def crear_barbero(data: BarberoIn, b: Barberia = Depends(current_barberia),
                  db: Session = Depends(get_db)):
    """Da de alta un profesional, respetando el limite del plan."""
    actuales = db.query(Barbero).filter(Barbero.barberia_id == b.id).count()
    if actuales >= plans.limite_recursos(b):
        raise HTTPException(
            409, f"Tu plan {b.plan} permite hasta {plans.limite_recursos(b)} "
                 f"profesionales. Sube de plan para agregar más.")
    siguiente = (db.query(Barbero).filter(Barbero.barberia_id == b.id).count()) + 1
    r = Barbero(
        barberia_id=b.id, numero=siguiente,
        nombre=data.nombre or f"{plans.plan_de(b)['nombre']} {siguiente}",
        work_start=data.work_start or "10:00",
        work_end=data.work_end or "20:00",
        days_off=data.days_off or "0",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"ok": True, "id": r.id}


# --------------------------- conversaciones escaladas ---------------------------

@router.get("/api/conversaciones")
def conversaciones(b: Barberia = Depends(current_barberia),
                   db: Session = Depends(get_db), estado: str = "humano"):
    rows = (db.query(Conversacion)
            .filter(Conversacion.barberia_id == b.id, Conversacion.estado == estado)
            .order_by(Conversacion.actualizada.desc()).all())
    return [{"id": r.id, "telefono": r.telefono, "estado": r.estado,
             "actualizada": (r.actualizada or datetime.utcnow()).isoformat()} for r in rows]


@router.post("/api/conversaciones/{conv_id}/devolver_bot")
def devolver_bot(conv_id: int, b: Barberia = Depends(current_barberia),
                 db: Session = Depends(get_db)):
    c = db.get(Conversacion, conv_id)
    if not c or c.barberia_id != b.id:
        raise HTTPException(404, "No encontrada")
    c.estado = "bot"
    c.contexto = "{}"
    db.commit()
    return {"ok": True}


# --------------------------- servicios ---------------------------

@router.get("/api/servicios")
def servicios(b: Barberia = Depends(current_barberia), db: Session = Depends(get_db)):
    rows = (db.query(Servicio).filter(Servicio.barberia_id == b.id)
            .order_by(Servicio.id).all())
    return [{"id": s.id, "nombre": s.nombre, "duracion_min": s.duracion_min,
             "precio": s.precio} for s in rows]


class ServicioIn(BaseModel):
    nombre: str
    duracion_min: int = 45
    precio: int = 0


@router.post("/api/servicios")
def crear_servicio(data: ServicioIn, b: Barberia = Depends(current_barberia),
                   db: Session = Depends(get_db)):
    s = Servicio(barberia_id=b.id, nombre=data.nombre,
                 duracion_min=data.duracion_min, precio=data.precio)
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"ok": True, "id": s.id}


class ServicioPatch(BaseModel):
    nombre: str | None = None
    duracion_min: int | None = None
    precio: int | None = None


@router.put("/api/servicios/{servicio_id}")
def editar_servicio(servicio_id: int, data: ServicioPatch,
                    b: Barberia = Depends(current_barberia),
                    db: Session = Depends(get_db)):
    s = db.get(Servicio, servicio_id)
    if not s or s.barberia_id != b.id:
        raise HTTPException(404, "No encontrado")
    for campo, valor in data.model_dump(exclude_none=True).items():
        setattr(s, campo, valor)
    db.commit()
    return {"ok": True}


@router.delete("/api/servicios/{servicio_id}")
def borrar_servicio(servicio_id: int, b: Barberia = Depends(current_barberia),
                    db: Session = Depends(get_db)):
    s = db.get(Servicio, servicio_id)
    if not s or s.barberia_id != b.id:
        raise HTTPException(404, "No encontrado")
    db.delete(s)
    db.commit()
    return {"ok": True}


# --------------------------- configuracion del negocio ---------------------------

@router.get("/api/config")
def get_config(b: Barberia = Depends(current_barberia)):
    try:
        mensajes = json.loads(b.config_mensajes or "{}")
        if not isinstance(mensajes, dict):
            mensajes = {}
    except (ValueError, TypeError):
        mensajes = {}
    return {
        "nombre": b.nombre,
        "giro": b.giro,
        "termino_recurso": b.termino_recurso,
        "termino_negocio": b.termino_negocio,
        "emoji": b.emoji,
        "logo_url": b.logo_url,
        "zona_horaria": b.zona_horaria,
        "whatsapp_phone_id": b.whatsapp_phone_id or "",
        "admin_phone": b.admin_phone or "",
        "instrucciones_ia": b.instrucciones_ia or "",
        "mensajes": mensajes,
    }


class ConfigIn(BaseModel):
    nombre: str | None = None
    whatsapp_phone_id: str | None = None
    admin_phone: str | None = None
    instrucciones_ia: str | None = None
    termino_recurso: str | None = None
    termino_negocio: str | None = None
    emoji: str | None = None
    logo_url: str | None = None
    zona_horaria: str | None = None
    mensajes: dict | None = None


@router.put("/api/config")
def update_config(data: ConfigIn, b: Barberia = Depends(current_barberia),
                  db: Session = Depends(get_db)):
    campos = data.model_dump(exclude_none=True)
    mensajes = campos.pop("mensajes", None)
    for campo, valor in campos.items():
        setattr(b, campo, valor)
    if mensajes is not None:
        # limpia textos vacios para que el bot use sus defaults
        limpio = {k: v for k, v in mensajes.items() if isinstance(v, str) and v.strip()}
        b.config_mensajes = json.dumps(limpio, ensure_ascii=False)
    db.commit()
    return {"ok": True}


# --------------------------- clientes / pacientes ---------------------------

@router.get("/api/clientes")
def clientes(b: Barberia = Depends(current_barberia), db: Session = Depends(get_db),
             q: str = None):
    rows = (db.query(Cliente).filter(Cliente.barberia_id == b.id)
            .order_by(Cliente.actualizado.desc()).all())
    out = []
    for c in rows:
        if q:
            ql = q.lower()
            if ql not in (c.nombre or "").lower() and ql not in (c.telefono or ""):
                continue
        total = (db.query(Cita)
                 .filter(Cita.barberia_id == b.id, Cita.cliente_telefono == c.telefono)
                 .count())
        ultima = (db.query(Cita)
                  .filter(Cita.barberia_id == b.id, Cita.cliente_telefono == c.telefono)
                  .order_by(Cita.inicio.desc()).first())
        out.append({"telefono": c.telefono, "nombre": c.nombre, "notas": c.notas or "",
                    "citas": total,
                    "ultima": ultima.inicio.isoformat() if ultima else None})
    return out


@router.get("/api/clientes/{telefono}")
def cliente_detalle(telefono: str, b: Barberia = Depends(current_barberia),
                    db: Session = Depends(get_db)):
    c = (db.query(Cliente)
         .filter(Cliente.barberia_id == b.id, Cliente.telefono == telefono).first())
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    barberos = {x.id: x.nombre for x in db.query(Barbero).filter(Barbero.barberia_id == b.id)}
    citas = (db.query(Cita)
             .filter(Cita.barberia_id == b.id, Cita.cliente_telefono == telefono)
             .order_by(Cita.inicio.desc()).all())
    mensajes = (db.query(Mensaje)
                .filter(Mensaje.barberia_id == b.id, Mensaje.telefono == telefono)
                .order_by(Mensaje.creado).all())
    return {
        "telefono": c.telefono, "nombre": c.nombre, "notas": c.notas or "",
        "citas": [{"inicio": x.inicio.isoformat(), "barbero": barberos.get(x.barbero_id, "?"),
                   "servicio": x.servicio, "estado": x.estado} for x in citas],
        "mensajes": [{"direccion": m.direccion, "texto": m.texto,
                      "creado": m.creado.isoformat()} for m in mensajes],
    }


class ClientePatch(BaseModel):
    nombre: str | None = None
    notas: str | None = None


@router.put("/api/clientes/{telefono}")
def editar_cliente(telefono: str, data: ClientePatch,
                   b: Barberia = Depends(current_barberia),
                   db: Session = Depends(get_db)):
    c = (db.query(Cliente)
         .filter(Cliente.barberia_id == b.id, Cliente.telefono == telefono).first())
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    for campo, valor in data.model_dump(exclude_none=True).items():
        setattr(c, campo, valor)
    db.commit()
    return {"ok": True}


# --------------------------- suscripcion / cobro ---------------------------

@router.get("/api/billing/estado")
def billing_estado(b: Barberia = Depends(current_barberia), db: Session = Depends(get_db)):
    plan = plans.plan_de(b)
    recursos = db.query(Barbero).filter(Barbero.barberia_id == b.id).count()
    mes = datetime.now().strftime("%Y-%m")
    usados = b.recordatorios_mes_count if b.recordatorios_mes_ref == mes else 0
    return {
        "plan": b.plan,
        "plan_nombre": plan["nombre"],
        "precio_mxn": plan["precio_mxn"],
        "estado": b.estado_suscripcion,
        "activa": plans.suscripcion_activa(b),
        "dias_restantes": plans.dias_restantes(b),
        "vigente_hasta": b.suscripcion_hasta.isoformat() if b.suscripcion_hasta else None,
        "limites": {"recursos": plan["max_recursos"], "usuarios": plan["max_usuarios"],
                    "recordatorios_mes": plan["recordatorios_mes"]},
        "uso": {"recursos": recursos, "recordatorios_mes": usados},
        "planes": plans.PLANES,
    }


class SuscribirIn(BaseModel):
    plan: str
    email: str = ""


@router.post("/api/billing/suscribir")
def billing_suscribir(data: SuscribirIn, b: Barberia = Depends(current_barberia),
                      db: Session = Depends(get_db)):
    try:
        res = billing.crear_suscripcion(b, data.plan, data.email)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # guardamos el plan elegido y el id de la suscripcion (pendiente hasta que MP confirme)
    b.plan = data.plan.lower()
    b.mp_preapproval_id = res.get("preapproval_id", "") or b.mp_preapproval_id
    db.commit()
    return res


@router.post("/api/billing/simular_pago")
def billing_simular_pago(b: Barberia = Depends(current_barberia),
                         db: Session = Depends(get_db)):
    """Solo para pruebas locales (sin Mercado Pago real): activa la suscripcion."""
    if settings.use_mercadopago:
        raise HTTPException(400, "Mercado Pago real está configurado; usa el flujo real")
    billing.activar_suscripcion(db, b, plan_key=b.plan)
    return {"ok": True, "estado": b.estado_suscripcion}


@router.post("/webhook/mercadopago")
async def webhook_mercadopago(request: Request, db: Session = Depends(get_db)):
    """Recibe notificaciones de Mercado Pago (suscripciones y pagos)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    tipo = body.get("type") or body.get("topic") or request.query_params.get("type") or ""
    data_id = (body.get("data", {}) or {}).get("id") or request.query_params.get("id") or ""
    try:
        billing.procesar_notificacion(db, tipo, str(data_id))
    except Exception as e:  # nunca devolver error a MP para evitar reintentos en loop
        print("Error webhook MP:", e)
    return {"status": "received"}
