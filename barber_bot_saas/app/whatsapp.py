"""Cliente de la WhatsApp Cloud API: texto y mensajes interactivos (botones/listas)."""
import httpx
from .config import settings


def _enviar(to: str, payload: dict, phone_number_id: str | None = None,
            descripcion: str = "mensaje") -> dict:
    """Envia un payload ya armado. Si no hay token, simula (pruebas locales)."""
    pid = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    if not settings.WHATSAPP_TOKEN or not pid:
        print(f"[whatsapp] SIMULADO ({descripcion}, falta token o phone_id) -> to={to} "
              f"token={'si' if settings.WHATSAPP_TOKEN else 'NO'} pid={pid!r}")
        return {"simulado": True, "to": to}
    payload = {"messaging_product": "whatsapp", "to": to, **payload}
    url = f"{settings.GRAPH_API_URL}/{pid}/messages"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
               "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=20) as c:
            r = c.post(url, headers=headers, json=payload)
            r.raise_for_status()
            print(f"[whatsapp] enviado ({descripcion}) a {to} (pid={pid})")
            return r.json()
    except httpx.HTTPStatusError as e:
        print(f"[whatsapp] ERROR {e.response.status_code} al enviar a {to}: "
              f"{e.response.text[:300]}")
        raise


def send_text(to: str, body: str, phone_number_id: str | None = None) -> dict:
    return _enviar(to, {"type": "text", "text": {"body": body}}, phone_number_id, "texto")


def send_buttons(to: str, body: str, opciones: list, phone_number_id: str | None = None) -> dict:
    """Botones de respuesta rapida (max 3). opciones: [{'id','title'}]."""
    botones = [{"type": "reply", "reply": {"id": str(o["id"])[:256], "title": o["title"][:20]}}
               for o in opciones[:3]]
    payload = {"type": "interactive", "interactive": {
        "type": "button", "body": {"text": body},
        "action": {"buttons": botones}}}
    return _enviar(to, payload, phone_number_id, "botones")


def send_document(to: str, link: str, filename: str, caption: str | None = None,
                  phone_number_id: str | None = None) -> dict:
    """Envia un documento por su URL publica (ej. un .ics de calendario)."""
    doc = {"link": link, "filename": filename}
    if caption:
        doc["caption"] = caption
    return _enviar(to, {"type": "document", "document": doc}, phone_number_id, "documento")


def send_list(to: str, body: str, boton: str, opciones: list,
              phone_number_id: str | None = None) -> dict:
    """Mensaje de lista (hasta 10 filas). opciones: [{'id','title'}]."""
    filas = [{"id": str(o["id"])[:200], "title": o["title"][:24]} for o in opciones[:10]]
    payload = {"type": "interactive", "interactive": {
        "type": "list", "body": {"text": body},
        "action": {"button": boton[:20],
                   "sections": [{"title": "Opciones", "rows": filas}]}}}
    return _enviar(to, payload, phone_number_id, "lista")
