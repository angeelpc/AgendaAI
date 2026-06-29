"""Configuracion central. Lee variables de entorno (.env)."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


class Settings:
    # WhatsApp Cloud API
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
    GRAPH_API_URL = "https://graph.facebook.com/v20.0"

    # Cerebro IA
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

    # Base de datos
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///barber_bot.db")

    # Recordatorios: cuantas horas antes de la cita se avisa (default 24h = dia antes)
    REMINDER_HOURS = int(os.getenv("REMINDER_HOURS", "24"))

    # Clave de superadmin de la plataforma (para dar de alta negocios nuevos).
    # CAMBIALA en produccion via variable de entorno.
    PLATFORM_ADMIN_KEY = os.getenv("PLATFORM_ADMIN_KEY", "cambia-esta-clave-admin")

    # --- Cobro de suscripciones (Mercado Pago) ---
    MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
    MERCADOPAGO_BASE_URL = "https://api.mercadopago.com"
    # URL publica del backend (para back_url y notificaciones del webhook).
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

    @property
    def use_mercadopago(self) -> bool:
        return bool(self.MERCADOPAGO_ACCESS_TOKEN)

    @property
    def use_llm(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)


settings = Settings()
