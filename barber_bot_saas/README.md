# Barber Bot SaaS — Bot de citas para barberías por WhatsApp

Asistente que atiende a los clientes por WhatsApp 24/7, agenda con el barbero
deseado (1–4) de forma automática y escala a una persona cuando hace falta.
Corre **en la nube** (no depende de ninguna laptop) y es **multi-cliente**
(varias barberías sobre el mismo backend).

## Arquitectura

```
Cliente WhatsApp → WhatsApp Cloud API → Webhook (FastAPI) → Cerebro → Motor de agenda → BD
                                                              ↘ Escalación a humano
```

- **app/main.py** — API FastAPI: webhook de WhatsApp + endpoints del panel.
- **app/service.py** — orquestador: recibe mensaje, responde, escala, notifica.
- **app/brain.py** — el cerebro. `RuleBrain` (offline, reglas) y `LLMBrain` (IA).
- **app/agenda.py** — disponibilidad, reserva y cancelación (sin doble reserva).
- **app/nlu.py** — extracción de fecha/hora/barbero/intención en español.
- **app/models.py** — base de datos multi-tenant (barberías, barberos, citas…).
- **app/whatsapp.py** — cliente para enviar mensajes por Cloud API.
- **app/seed.py** — datos de ejemplo (1 barbería, 4 barberos).
- **run_demo.py** — conversación simulada de extremo a extremo (sin WhatsApp).

## El cerebro: dos modos

| Modo | Cuándo se usa | Costo |
| :--- | :--- | :--- |
| **Reglas** (`RuleBrain`) | Si no hay `ANTHROPIC_API_KEY`. Funciona offline. | $0 |
| **IA** (`LLMBrain`) | Si defines `ANTHROPIC_API_KEY`. Lenguaje natural. | centavos/conversación |

Ambos comparten el mismo motor de agenda, así que las reglas de negocio
(disponibilidad real, no doble reserva) son idénticas en los dos modos.

## Probar en local (sin WhatsApp ni IA)

```bash
pip install -r requirements.txt
python run_demo.py        # conversación simulada
pytest -q                 # pruebas
```

## Conectar WhatsApp real

1. Copia `.env.example` a `.env` y llena las variables de Cloud API.
2. Levanta el servidor:  `uvicorn app.main:app --host 0.0.0.0 --port 8000`
3. Expónlo con HTTPS (ngrok o un dominio) y registra la URL `…/webhook` en Meta
   usando tu `WHATSAPP_VERIFY_TOKEN`.
4. En `barberias.whatsapp_phone_id` guarda el `phone_number_id` de cada barbería.

## Activar el cerebro con IA

Pon tu clave en `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-6
```

No hay que cambiar nada de código: `get_brain()` detecta la clave y usa IA.

## Multi-giro (cualquier negocio de citas)

El mismo bot sirve para barberías, estéticas, dentistas, veterinarias, spas,
consultorios, etc. Cada negocio (tenant) personaliza su vocabulario y mensajes
**sin tocar código**, vía campos en su registro:

- `giro`, `logo_url`, `zona_horaria`
- `termino_recurso` (ej. "barbero", "doctor", "veterinario")
- `termino_negocio` (ej. "la barbería", "la clínica")
- `emoji` y `config_mensajes` (overrides de cualquier texto, en JSON)

Todos los textos del bot viven en `app/branding.py` y se arman desde esos
campos. Los valores por defecto reproducen el comportamiento de barbería, así
que los negocios existentes no cambian. Internamente las tablas siguen llamándose
`barberias`/`barberos` por compatibilidad, pero representan Negocio/Recurso.

## Alta de negocios (onboarding self-service)

Un negocio nuevo se da de alta sin tocar código, con `app/onboarding.py`:

- **Web:** página `/alta` (wizard). Pide la clave de superadmin (`PLATFORM_ADMIN_KEY`), elige giro (autollena términos y servicios sugeridos), captura profesionales/servicios/mensajes y crea el negocio. Devuelve su `id` y `api_key` para entrar al panel.
- **API:** `POST /api/negocios` (header `X-Admin-Key`).
- **CLI:** `python -m app.onboarding` (alta guiada por consola).

Cada giro trae un preset (barbería, estética, dentista, veterinaria, spa) con
terminología, emoji y servicios típicos. El alta genera la `api_key`, siembra
recursos y servicios, y guarda los mensajes personalizados.

## Recordatorios automáticos

Para reducir no-shows, el sistema avisa a cada cliente antes de su cita
(por defecto 24h antes; ajustable con `REMINDER_HOURS`).

- Manual: botón **"Enviar ahora"** en el Resumen del panel.
- Automático: corre `python -m app.reminders` en una tarea programada
  (Programador de tareas de Windows, cron o el scheduler del hosting).
  El campo `recordatorio_enviado` evita reenvíos aunque corra varias veces al día.

## Estado

Fases 1 y 2 (parcial): agenda, escalación y multi-tenant; panel web con gestión
de servicios, alta manual de citas, no-shows y recordatorios. Todo probado con
`pytest` (incluye `test_panel.py` y `test_reminders.py`). Falta para producción:
sync con Google Calendar (opcional) y cobro de suscripciones (Fase 3).
