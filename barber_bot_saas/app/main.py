"""API FastAPI: webhook de WhatsApp Cloud API + endpoints de administracion."""
from fastapi import FastAPI, Request, Response, Query, Depends
from sqlalchemy.orm import Session

from .config import settings
from .database import init_db, get_db, engine
from .models import Barberia, Cita, Barbero
from .service import handle_incoming
from .panel import router as panel_router
from .calendar_ics import ics_de_cita

app = FastAPI(title="Barber Bot SaaS", version="0.1.0")
app.include_router(panel_router)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/ics/{cita_id}")
def cita_ics(cita_id: int, db: Session = Depends(get_db)):
    """Devuelve el archivo .ics de una cita para agregarla al calendario."""
    cita = db.get(Cita, cita_id)
    if not cita:
        return Response(content="no encontrada", status_code=404)
    barberia = db.get(Barberia, cita.barberia_id)
    barbero = db.get(Barbero, cita.barbero_id)
    ics = ics_de_cita(cita, barberia.nombre if barberia else "AgendaAI",
                      barbero.nombre if barbero else "")
    return Response(content=ics, media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="cita-{cita_id}.ics"'})


@app.get("/health")
def health(db: Session = Depends(get_db)):
    from .brain import nombre_cerebro
    backend = engine.url.get_backend_name()   # "sqlite" o "postgresql"
    negocios = db.query(Barberia).count()
    cerebro = nombre_cerebro()
    return {
        "ok": True,
        "cerebro": cerebro,                    # gemini | claude | reglas
        "modo_ia": cerebro != "reglas",
        "db": backend,
        "persistente": backend != "sqlite",   # sqlite en Railway = se borra en cada deploy
        "negocios": negocios,
    }


# --- Verificacion del webhook (Meta hace un GET al configurarlo) ---
@app.get("/webhook")
def verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=hub_challenge or "", media_type="text/plain")
    return Response(content="forbidden", status_code=403)


# --- Recepcion de mensajes entrantes ---
@app.post("/webhook")
async def incoming(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                phone_id = value.get("metadata", {}).get("phone_number_id")
                barberia = (
                    db.query(Barberia)
                    .filter(Barberia.whatsapp_phone_id == phone_id).first()
                )
                if not barberia:
                    ids = [x[0] for x in db.query(Barberia.whatsapp_phone_id).all()]
                    print(f"[webhook] SIN NEGOCIO para phone_id={phone_id!r}. "
                          f"phone_ids registrados={ids}")
                    continue
                print(f"[webhook] match negocio id={barberia.id} '{barberia.nombre}' "
                      f"para phone_id={phone_id}")
                for msg in value.get("messages", []):
                    tipo = msg.get("type")
                    if tipo == "text":
                        texto = msg["text"]["body"]
                    elif tipo == "interactive":
                        inter = msg.get("interactive", {})
                        if inter.get("type") == "button_reply":
                            texto = inter["button_reply"]["id"]
                        elif inter.get("type") == "list_reply":
                            texto = inter["list_reply"]["id"]
                        else:
                            continue
                    else:
                        continue
                    telefono = msg["from"]
                    reply = handle_incoming(db, barberia, telefono, texto)
                    print(f"[webhook] respuesta='{(reply.text or '')[:60]}' "
                          f"escalado={reply.escalate}")
    except Exception as e:  # nunca devolver error a Meta para evitar reintentos en loop
        print("Error procesando webhook:", e)
    return {"status": "received"}


# --- Endpoints simples para el panel de la barberia ---
@app.get("/barberias/{barberia_id}/citas")
def listar_citas(barberia_id: int, db: Session = Depends(get_db)):
    citas = (
        db.query(Cita)
        .filter(Cita.barberia_id == barberia_id, Cita.estado == "agendada")
        .order_by(Cita.inicio).all()
    )
    barberos = {x.id: x.nombre for x in db.query(Barbero).filter(Barbero.barberia_id == barberia_id)}
    return [
        {
            "id": c.id, "cliente": c.cliente_nombre, "telefono": c.cliente_telefono,
            "barbero": barberos.get(c.barbero_id, "?"), "inicio": c.inicio.isoformat(),
            "servicio": c.servicio,
        }
        for c in citas
    ]
