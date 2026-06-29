"""Cliente minimo de la WhatsApp Cloud API para enviar mensajes."""
import httpx
from .config import settings


def send_text(to: str, body: str, phone_number_id: str | None = None) -> dict:
    """Envia un mensaje de texto. Si no hay token configurado, no falla:
    devuelve un dict simulado (util para pruebas locales)."""
    pid = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    if not settings.WHATSAPP_TOKEN or not pid:
        return {"simulado": True, "to": to, "body": body}

    url = f"{settings.GRAPH_API_URL}/{pid}/messages"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
               "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to,
               "type": "text", "text": {"body": body}}
    with httpx.Client(timeout=20) as c:
        r = c.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()
