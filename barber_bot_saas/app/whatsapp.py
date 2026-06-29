"""Cliente minimo de la WhatsApp Cloud API para enviar mensajes."""
import httpx
from .config import settings


def send_text(to: str, body: str, phone_number_id: str | None = None) -> dict:
    """Envia un mensaje de texto. Si no hay token configurado, no falla:
    devuelve un dict simulado (util para pruebas locales)."""
    pid = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    if not settings.WHATSAPP_TOKEN or not pid:
        print(f"[whatsapp] SIMULADO (falta token o phone_id) -> to={to} "
              f"token={'si' if settings.WHATSAPP_TOKEN else 'NO'} pid={pid!r}")
        return {"simulado": True, "to": to, "body": body}

    url = f"{settings.GRAPH_API_URL}/{pid}/messages"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
               "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to,
               "type": "text", "text": {"body": body}}
    try:
        with httpx.Client(timeout=20) as c:
            r = c.post(url, headers=headers, json=payload)
            r.raise_for_status()
            print(f"[whatsapp] enviado a {to} (pid={pid})")
            return r.json()
    except httpx.HTTPStatusError as e:
        print(f"[whatsapp] ERROR {e.response.status_code} al enviar a {to}: "
              f"{e.response.text[:300]}")
        raise
