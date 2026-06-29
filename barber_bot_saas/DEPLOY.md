# Guía de despliegue — Railway + WhatsApp + Mercado Pago

Lleva el bot a producción 24/7. Sigue las etapas en orden. Lo que prepara el
código ya está listo (`Procfile`, `runtime.txt`, soporte PostgreSQL); aquí solo
creas cuentas y pegas valores.

> Convención: cada variable de entorno se escribe como `NOMBRE=valor`. En Railway
> se cargan en la pestaña **Variables** del servicio.

---

## Etapa 0 — Subir el código a GitHub

Desde la carpeta del proyecto:

```powershell
cd "D:\Development Protfolio\WhatsApp_Auto\barber_bot_saas"
git add .
git commit -m "Despliegue: Procfile, runtime, soporte PostgreSQL"
git push
```

Confirma en https://github.com/angeelpc/AgendaAI que aparezcan `Procfile`,
`runtime.txt` y la carpeta `app/`.

---

## Etapa 1 — Railway (servidor + base de datos)

1. Entra a https://railway.app e inicia sesión con GitHub.
2. **New Project → Deploy from GitHub repo →** elige `AgendaAI`.
3. **Importante (monorepo):** en el servicio, **Settings → Root Directory** pon
   `barber_bot_saas`. (El código vive en esa subcarpeta, no en la raíz del repo.)
4. **Agregar la base de datos:** en el proyecto, **New → Database → PostgreSQL**.
   Railway crea la variable `DATABASE_URL` y la comparte al servicio.
5. **Variables del servicio** (Settings → Variables). Agrega:

   | Variable | Valor | Para qué |
   | :--- | :--- | :--- |
   | `PLATFORM_ADMIN_KEY` | (inventa una clave secreta) | Alta de negocios en `/alta` |
   | `PUBLIC_BASE_URL` | (la pones en el paso 7) | back_url y webhooks |
   | `WHATSAPP_VERIFY_TOKEN` | (inventa un texto secreto) | Verificar webhook de Meta |
   | `WHATSAPP_TOKEN` | (Etapa 2) | Enviar mensajes |
   | `WHATSAPP_PHONE_NUMBER_ID` | (Etapa 2) | Número del bot |
   | `MERCADOPAGO_ACCESS_TOKEN` | (Etapa 3) | Cobro real |
   | `ANTHROPIC_API_KEY` | (opcional) | Cerebro con IA |

   `DATABASE_URL` ya la pone Railway sola; no la toques.
6. Railway construye y despliega. En **Deployments** verás el log; debe terminar en
   *Application startup complete*.
7. **URL pública:** Settings → Networking → **Generate Domain**. Te da algo como
   `https://agendaai-production.up.railway.app`. Copia esa URL y:
   - ponla en la variable `PUBLIC_BASE_URL`,
   - Railway redeploya solo.
8. **Prueba:** abre `https://TU-URL/health` → debe responder `{"ok": true, ...}`.
   Y `https://TU-URL/alta` para dar de alta tu primer negocio real.

> Nota: en PostgreSQL las tablas se crean solas al arrancar. No corras `seed`
> en producción (es data de demo); crea negocios reales desde `/alta`.

---

## Etapa 2 — WhatsApp Cloud API (Meta)

1. Entra a https://developers.facebook.com → **My Apps → Create App → Business**.
2. Agrega el producto **WhatsApp**. Esto te da un **número de prueba** y un
   **phone_number_id** (lo ves en *WhatsApp → API Setup*).
3. Copia a Railway:
   - `WHATSAPP_PHONE_NUMBER_ID` = el phone_number_id.
   - `WHATSAPP_TOKEN` = el token. El temporal dura 24h; para producción genera un
     **token permanente de sistema** (Business Settings → System Users → token con
     permisos `whatsapp_business_messaging` y `whatsapp_business_management`).
4. **Configurar el webhook:** en *WhatsApp → Configuration → Webhook*:
   - **Callback URL:** `https://TU-URL/webhook`
   - **Verify token:** el mismo valor que pusiste en `WHATSAPP_VERIFY_TOKEN`.
   - Da **Verify and Save** (Meta hace un GET; el código responde el challenge).
   - **Subscribe** al campo `messages`.
5. **Número real del negocio:** para cada barbería, agrega su número en
   *API Setup* (o usa **Coexistence** si ya tienen WhatsApp). Guarda su
   `phone_number_id` en el campo `whatsapp_phone_id` del negocio (desde `/alta` o
   el panel). Así el backend sabe a qué negocio pertenece cada mensaje entrante.
6. **Plantillas de recordatorio:** en *WhatsApp Manager → Message Templates*, crea
   una plantilla de categoría **Utility** para el recordatorio y espera su
   aprobación (suele ser rápido). Es obligatoria para mensajes proactivos.

**Prueba:** escribe por WhatsApp al número del bot "quiero una cita". El bot debe
responder según el giro y agendar.

---

## Etapa 3 — Mercado Pago (cobro real)

1. Entra a https://www.mercadopago.com.mx/developers → **Tus integraciones →
   Crear aplicación** (tipo: Suscripciones / pagos).
2. Copia el **Access Token de producción** a Railway:
   `MERCADOPAGO_ACCESS_TOKEN=APP_USR-...`
   (Para pruebas existe un token de **sandbox**; úsalo primero si quieres.)
3. **Webhook:** en la app de Mercado Pago, configura la **URL de notificaciones**:
   `https://TU-URL/webhook/mercadopago`
   y activa los tópicos: `subscription_preapproval`,
   `subscription_authorized_payment` y `payments`.
4. Listo: al poner el token, el panel deja de estar en modo simulado. En la
   pestaña **Plan**, *Suscribirme* generará un enlace real de Mercado Pago
   (`init_point`) donde el dueño autoriza el cobro mensual.

**Prueba:** suscríbete con una tarjeta de prueba de Mercado Pago; el webhook debe
poner la suscripción en *activa* con vigencia a un mes.

---

## Variables de entorno (resumen)

| Variable | Obligatoria | Notas |
| :--- | :--- | :--- |
| `DATABASE_URL` | sí | La pone Railway (PostgreSQL) |
| `PUBLIC_BASE_URL` | sí | URL pública de Railway |
| `PLATFORM_ADMIN_KEY` | sí | Clave de superadmin para `/alta` |
| `WHATSAPP_VERIFY_TOKEN` | sí (WhatsApp) | Texto secreto que tú eliges |
| `WHATSAPP_TOKEN` | sí (WhatsApp) | Token permanente de sistema |
| `WHATSAPP_PHONE_NUMBER_ID` | sí (WhatsApp) | Número emisor por defecto |
| `MERCADOPAGO_ACCESS_TOKEN` | sí (cobro real) | Vacío = modo simulado |
| `REMINDER_HOURS` | no | Default 24 |
| `ANTHROPIC_API_KEY` | no | Activa el cerebro con IA |
| `LLM_MODEL` | no | Default claude-sonnet-4-6 |

---

## Recordatorios automáticos en la nube

`python -m app.reminders` debe correr a diario. En Railway: **New → Cron** (o un
segundo servicio con *Cron Schedule*) con el comando:

```
python -m app.reminders
```

programado, por ejemplo, a las 9:00 (`0 9 * * *`). El campo `recordatorio_enviado`
evita duplicados.

---

## Checklist final

- [ ] `/health` responde OK en la URL pública.
- [ ] `/alta` crea negocios; `/panel` entra con el id + api_key.
- [ ] WhatsApp: webhook verificado y el bot responde a un mensaje real.
- [ ] Mercado Pago: suscripción de prueba queda *activa* vía webhook.
- [ ] Cron de recordatorios programado.
