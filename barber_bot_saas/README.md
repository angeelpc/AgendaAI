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

## Planes y cobro de suscripciones (Mercado Pago)

Cada negocio tiene un plan (`starter` / `pro` / `premium`) con límites que la app
hace cumplir: máximo de profesionales, recordatorios por mes y usuarios. El
catálogo vive en `app/plans.py`.

- **Estado y uso:** pestaña **Plan** del panel (`GET /api/billing/estado`).
- **Suscribirse:** `POST /api/billing/suscribir` crea una suscripción (preapproval)
  en Mercado Pago y devuelve el `init_point` para autorizar el cobro recurrente.
- **Webhook:** `POST /webhook/mercadopago` recibe las notificaciones (suscripción y
  pagos) y activa/renueva o vence la suscripción.
- **Modo simulado:** sin `MERCADOPAGO_ACCESS_TOKEN`, el cobro no es real; el botón
  *Simular pago* del panel (`POST /api/billing/simular_pago`) activa la suscripción
  para probar todo el flujo en local.

Los límites se aplican en: alta de negocio y de profesionales (máx. recursos) y en
el envío de recordatorios (solo si la suscripción está activa y dentro del cupo
mensual del plan).

## Estado

Fases 1, 2 y 3 operativas: agenda, escalación y multi-tenant; panel con servicios,
citas manuales, no-shows, recordatorios y configuración; bot multi-giro; onboarding
self-service; y planes con cobro por Mercado Pago (límites aplicados). Todo probado
con `pytest` (41 pruebas, incluye `test_billing.py`). Pendiente para producción:
desplegar en la nube, conectar WhatsApp Cloud API real y sync con Google Calendar
(opcional).
