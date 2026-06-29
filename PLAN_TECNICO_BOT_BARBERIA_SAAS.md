# Plan Técnico — Bot de Citas para Barberías (SaaS con IA)

**Producto:** Asistente de WhatsApp que atiende a los clientes 24/7, agenda citas con el barbero deseado (1–4) de forma automática y escala a una persona solo cuando hace falta.
**Modelo de negocio:** SaaS multi-cliente (varias barberías), suscripción mensual.
**Operación:** 100% en la nube. No depende de ninguna laptop encendida.
**Fecha:** Junio 2026

---

## 1. Visión del producto

Cuando un cliente le escribe a la barbería por WhatsApp, un bot con inteligencia artificial:

1. Saluda y entiende lo que el cliente quiere en lenguaje natural ("quiero corte el sábado en la tarde con el 2").
2. Consulta la agenda real de los 4 barberos y ofrece solo horarios libres.
3. Confirma la cita, la guarda y manda recordatorio el día anterior.
4. Si el cliente pide algo que el bot no puede resolver (queja, servicio especial, pago, etc.), avisa a la barbería y pasa la conversación a una persona.

Cada barbería que contrata el SaaS tiene su propio número, sus barberos, sus horarios y su agenda, todo aislado del resto.

---

## 2. Arquitectura general

```
Cliente (WhatsApp)
        │  mensaje entrante
        ▼
WhatsApp Cloud API (Meta / BSP)      ← número oficial de cada barbería
        │  webhook (HTTPS)
        ▼
┌─────────────────────────────────────────────┐
│   BACKEND (servidor en la nube, 24/7)        │
│                                              │
│  1. Receptor de mensajes (webhook)           │
│  2. Identifica a qué barbería pertenece      │
│  3. Cerebro IA (LLM + herramientas)          │
│  4. Motor de agenda (disponibilidad/citas)   │
│  5. Lógica de escalación a humano            │
│  6. Programador de recordatorios             │
└─────────────────────────────────────────────┘
        │                      │
        ▼                      ▼
  Base de datos          Panel web de administración
 (barberías, barberos,   (la barbería ve/edita su
  citas, conversaciones)  agenda, horarios, chats)
```

Pieza clave: el cliente nunca habla con la laptop de nadie. Habla con un servidor que siempre está encendido.

---

## 3. Stack tecnológico recomendado

| Capa | Herramienta recomendada | Por qué |
| :--- | :--- | :--- |
| Canal de WhatsApp | **WhatsApp Cloud API** vía **360dialog** o Meta directo | Oficial, en la nube, sin riesgo de baneo por automatización. 360dialog es BSP económico y popular en LatAm. |
| Backend | **Python (FastAPI)** o **Node.js (NestJS)** | FastAPI permite reusar tu experiencia previa en Python. Webhooks rápidos y simples. |
| Base de datos | **PostgreSQL** | Robusta, gratis, ideal para multi-cliente. |
| Cerebro IA | **API de un LLM** (Claude / GPT) con *function calling* | Entiende lenguaje natural y llama a tus funciones de agenda. Centavos por conversación. |
| Agenda | Tabla propia en PostgreSQL (+ opción de sync con Google Calendar) | Control total de slots por barbero. |
| Panel admin | **React** o un panel sencillo server-side | Para que cada barbería gestione lo suyo. |
| Hosting | **Railway / Render / VPS (Hetzner, DigitalOcean)** | Despliegue fácil, encendido 24/7, escalable. |
| Pagos del SaaS | **Stripe** o **Mercado Pago** | Cobro de suscripciones a las barberías. |

---

## 4. El cerebro de IA (cómo "piensa" el bot)

El bot **no** es un árbol de menús. Usa un modelo de lenguaje con *function calling*: el LLM entiende el mensaje y decide qué herramienta usar. Tú le defines herramientas como:

- `consultar_disponibilidad(barbero, fecha)` → devuelve huecos libres.
- `agendar_cita(cliente, barbero, fecha, hora, servicio)` → guarda la cita.
- `cancelar_o_reprogramar(cita_id, nueva_fecha)`.
- `escalar_a_humano(motivo)` → avisa a la barbería y pausa el bot en ese chat.

**Prompt del sistema (resumen de lo que se le instruye al modelo):**

> Eres el asistente de [Nombre Barbería]. Agendas citas con los barberos 1 a 4. Solo ofreces horarios que devuelva la herramienta de disponibilidad. Eres breve y amable. Si el cliente pide algo fuera de agendar/cancelar/consultar (quejas, pagos, servicios no listados, casos confusos), usa `escalar_a_humano`. Nunca inventes horarios ni precios.

Esto da conversación natural pero **con barreras**: el modelo no puede inventar citas porque los horarios salen de tu base de datos real, no de su imaginación.

**Costo de IA:** ~$0.10–$0.50 MXN por conversación completa. Despreciable frente al valor de una cita.

---

## 5. Flujo conversacional (ejemplo real)

```
Cliente:  Hola, quiero cortarme el pelo el sábado
Bot:      ¡Hola! Claro 😊 ¿Con qué barbero te gustaría? Tenemos a
          1) Carlos  2) Memo  3) Luis  4) Ana
Cliente:  con el 2 en la tarde
Bot:      Memo tiene libre el sábado a las 16:00, 16:45 y 18:00.
          ¿Cuál te queda?
Cliente:  4:45 está bien
Bot:      Listo ✅ Te agendé con Memo el sábado a las 16:45.
          ¿Me confirmas tu nombre?
Cliente:  Angel
Bot:      ¡Gracias, Angel! Cita confirmada. Te mando recordatorio
          el viernes. 💈

--- Caso de escalación ---
Cliente:  oigan el corte de ayer quedó mal, quiero un reembolso
Bot:      Lamento eso, Angel. Te paso con el equipo para resolverlo
          personalmente, en un momento te contactan. 🙏
          [→ notifica al dueño y pausa el bot en este chat]
```

---

## 6. Modelo de datos (tablas principales)

- **barberias** — id, nombre, número de WhatsApp, horario general, plan contratado, estado de pago.
- **barberos** — id, barberia_id, nombre, número (1–4), horario laboral, días libres.
- **servicios** — id, barberia_id, nombre, duración, precio (para mostrar, no cobrar dentro del bot).
- **citas** — id, barberia_id, barbero_id, cliente_nombre, cliente_telefono, fecha, hora, servicio, estado (agendada / completada / cancelada).
- **conversaciones** — id, barberia_id, telefono_cliente, estado (bot / escalado a humano), historial.
- **usuarios_panel** — dueños/recepción que acceden al panel de su barbería.

El campo `barberia_id` en todas las tablas es lo que mantiene a cada cliente del SaaS aislado (multi-tenant).

---

## 7. Lógica de agenda y disponibilidad

1. Cada barbero tiene horario laboral (ej. mar–sáb 10:00–20:00) y citas ya ocupadas.
2. Al pedir disponibilidad, el sistema calcula los huecos según la **duración del servicio** (un corte de 45 min no cabe en un hueco de 30).
3. Se evita doble reserva con bloqueo a nivel base de datos (que dos clientes no tomen el mismo slot a la vez).
4. Opcional: sincronizar con el Google Calendar de cada barbero (reaprovechando tu `calendar_manager.py`), para que bloqueos personales también cuenten.

---

## 8. Escalación a humano

- El bot marca la conversación como "escalada" y **deja de responder** en ese chat.
- Notifica al dueño/recepción por: mensaje de WhatsApp, correo y/o alerta en el panel.
- Desde el panel, la persona retoma el chat manualmente.
- Un botón "devolver al bot" reactiva la automatización cuando se resuelve.

Disparadores de escalación: el LLM lo decide (quejas, temas de dinero, ambigüedad), o reglas fijas (cliente escribe "humano", "persona", "reclamo").

---

## 9. Recordatorios y mensajes proactivos

- El día anterior a la cita, el sistema envía un recordatorio (mensaje **plantilla** aprobado por Meta, ~$0.55 MXN c/u).
- Plantilla: "Hola {Nombre}, te recordamos tu cita mañana a las {hora} con {barbero}. Responde CONFIRMAR o CANCELAR."
- La respuesta del cliente vuelve a abrir la ventana gratis de 24h.
- Esto reduce el "no-show", que es el principal dolor de las barberías.

---

## 10. Multi-tenant (clave del SaaS)

- Un solo backend atiende a todas las barberías.
- Cada barbería = un `barberia_id` + su número de WhatsApp conectado al Cloud API.
- Alta de una barbería nueva = crear su registro, conectar su número, cargar barberos/horarios. Sin tocar código.
- El panel de superadministrador (tú) ve todas; cada barbería solo ve la suya.

---

## 11. Fases de construcción

**Fase 1 — MVP (1 barbería piloto):**
- Cloud API conectado a un número.
- Webhook + cerebro IA + agendar/consultar/cancelar.
- Base de datos con 4 barberos y horarios.
- Escalación básica (aviso al dueño por WhatsApp).
- Objetivo: que agende citas reales de extremo a extremo.

**Fase 2 — Operación completa:**
- Recordatorios automáticos.
- Panel web para que la barbería edite horarios y vea citas.
- Sync con Google Calendar (opcional).

**Fase 3 — SaaS multi-cliente:**
- Multi-tenant + alta de barberías sin código.
- Cobro de suscripciones (Stripe/Mercado Pago).
- Panel de superadmin y métricas.

**Fase 4 — Escala y ventas:**
- Onboarding autoservicio.
- Reportes de valor (citas generadas, no-shows evitados) para vender y retener.

---

## 12. Costos

**Arranque (una vez):**
- Desarrollo del MVP con IA: tu tiempo, o ~$30,000–$90,000 MXN si lo contratas.
- Alta y verificación en Meta Business: gratis (requiere RFC/negocio).

**Mensual fijo (arrancando, pocas barberías):**
- Servidor + base de datos: ~$400–$1,500 MXN.
- BSP (360dialog) si aplica: $0–$1,000 MXN.
- IA (LLM): ~$200–$1,000 MXN según volumen.
- Total fijo aproximado: **$600–$2,500 MXN/mes**.

**Variable (por mensajes):**
- Conversaciones entrantes (ventana 24h): **gratis**.
- Recordatorios proactivos: ~$0.55 MXN c/u (ej. 300 citas/mes ≈ $165 MXN).

---

## 13. Precios y rentabilidad (SaaS)

- Precio sugerido por barbería: **$499–$1,200 MXN/mes** según plan (n.º de barberos, recordatorios incluidos, panel).
- Referencias de mercado MX: plataformas comparables cobran $2,000–$8,000 MXN/mes; tú entras por debajo para pyme.
- **Punto de equilibrio:** con costo fijo ~$2,500 MXN/mes, cubres gastos con **4–5 barberías**.
- A 30 barberías × ~$800 MXN ≈ $24,000 MXN/mes, con costo fijo casi plano → **margen bruto >80%**.
- El costo por barbería extra es mínimo (un poco de IA y recordatorios), por eso escala bien.

---

## 14. Riesgos y cumplimiento

- **Términos de WhatsApp:** usar Cloud API oficial elimina el riesgo de baneo que tenía el proyecto anterior (Selenium). Mantener buena calidad de mensajes y opt-in.
- **Privacidad (LFPDPPP México):** guardas teléfonos y nombres; ten aviso de privacidad y consentimiento. Manda recordatorios solo a quien agendó.
- **Aprobación de plantillas:** los mensajes proactivos deben ser aprobados por Meta (trámite simple pero existe).
- **Dependencia de un proveedor IA:** diseña el cerebro para poder cambiar de modelo si sube de precio.
- **Caída del servidor:** usa hosting con buena disponibilidad y monitoreo; es lo que sustituye a la laptop, así que debe ser confiable.

---

## 15. Próximos pasos sugeridos

1. Conseguir **una barbería piloto** real (idealmente conocida) para validar.
2. Dar de alta el número en **Cloud API** (Meta o 360dialog).
3. Construir el **MVP de la Fase 1** y medir cuántas citas agenda solo.
4. Con esos números, salir a vender a otras barberías.

---

## 16. Plataforma multi-giro (negocios basados en citas)

El producto no se limita a barberías. El mismo backend, agenda y cerebro sirven
para **cualquier negocio que opere por citas**, cambiando solo la configuración
(terminología, servicios, duración y mensajes), no el código:

- Barberías y estéticas / salones de belleza
- Dentistas y clínicas dentales
- Veterinarias
- Spas, uñas, depilación, tatuajes
- Consultorios (nutrición, psicología, fisioterapia)
- Talleres mecánicos, lavado de autos
- Cualquier servicio con "recurso + horario + cliente"

Para lograrlo, los conceptos del modelo de datos se generalizan (la lógica ya es
la misma, solo cambian los nombres visibles):

| Hoy (barbería) | Generalizado (multi-giro) |
| :--- | :--- |
| Barbería | **Negocio** (`negocio_id` = tenant) |
| Barbero (1–4) | **Recurso / Profesional** (estilista, doctor, veterinario, sillón, box) |
| Corte | **Servicio** (con duración y precio propios) |
| Cita | Cita (igual) |

Cada negocio define su propio vocabulario en el onboarding (ver sección 20): un
dentista verá "Doctores" y "Consultas"; una veterinaria, "Veterinarios" y
"Consultas/Vacunación". El motor de disponibilidad y no-doble-reserva es idéntico.

---

## 17. Modelo de cobro por uso (con límites por plan)

El SaaS cobra **suscripción mensual** y cada plan delimita el uso para controlar
costos y crear escalones de precio. Variables que se limitan por plan:

- **Conversaciones / mensajes salientes** al mes (recordatorios y plantillas, que sí cuestan a Meta).
- **Registros activos** (citas y clientes almacenados).
- **Recursos / profesionales** dados de alta.
- **Usuarios del panel** (dueño, recepción).
- **Funciones**: recordatorios, sync con Google Calendar, reportes, varios números, marca propia.

Ejemplo de escalera de planes (ajustable; precios sugeridos en USD/mes):

| Plan | Precio | Recursos | Usuarios panel | Recordatorios/mes incluidos | Cerebro IA | Extras |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Starter** | $29 | hasta 2 | 1 | 200 | Reglas | 1 número |
| **Pro** | $59 | hasta 6 | 3 | 800 | IA (LLM) | Recordatorios + reportes |
| **Premium** | $99 | hasta 15 | 6 | 2,000 | IA (LLM) | + Google Calendar, marca propia |
| **Excedente** | — | — | — | ~$0.02–0.05 por mensaje extra | — | Se cobra el uso por encima del plan |

Notas de diseño del cobro:

- El límite que más impacta el costo es el de **mensajes proactivos** (plantillas), porque cada uno se paga a Meta. Las respuestas dentro de la ventana de 24h **son gratis** (ver sección 18), así que el chat normal de agendar casi no cuesta.
- Conviene medir consumo por `negocio_id` (mensajes enviados, citas creadas) para facturar excedentes y para los reportes de valor.
- Modelo alternativo tipo "agencia": **setup fee único** ($300–$1,000 USD) + mensualidad menor de mantenimiento, para clientes que quieren todo configurado por ti.

---

## 18. Costos validados (junio 2026)

### 18.1 Costo variable — WhatsApp Cloud API (México)

Desde **julio 2025** Meta cobra **por mensaje entregado** (ya no por conversación de 24h). Categorías relevantes:

| Tipo de mensaje | Cuándo aplica | Costo aprox. México |
| :--- | :--- | :--- |
| **Servicio** (el cliente escribe primero, respondes dentro de 24h) | Todo el flujo de agendar/consultar | **Gratis** |
| **Utility / Utilidad** (plantilla: recordatorio, confirmación) | Recordatorios proactivos | **~$0.0082 USD** c/u |
| **Marketing** (plantilla promocional) | Promos, reactivación | **~$0.0305 USD** c/u |

Implicación clave: el bot que solo **responde** y agenda es casi gratis en mensajería; lo que cuesta son los **recordatorios** (utility) y las **promos** (marketing). Ej.: 1,000 recordatorios/mes ≈ **$8 USD**.

### 18.2 Costo fijo — Hosting y base de datos (precios 2026)

| Opción | Costo aprox. | Cuándo conviene |
| :--- | :--- | :--- |
| **Hetzner VPS** (CAX11, 2 vCPU, 4 GB) + Coolify | **~€4–5/mes** (~$5 USD) | **Mejor para multi-tenant**: un solo VPS aloja muchos negocios. Más barato por cliente al escalar. Requiere administrar el servidor. |
| **Railway** | ~$5 base, real $10–20/mes con tráfico | MVP rápido, despliegue sencillo, sin administrar servidor. Costo sube con uso. |
| **Render** | ~$7 web + ~$6 Postgres = ~$13/mes | Equilibrado, Postgres administrado incluido. |
| **Fly.io** | ~$8–25/mes según tráfico/egress | Buena latencia, pero el costo real sube por egress. |

**Recomendación por etapa:**

- **Piloto / pocas barberías:** Railway o Render (despliegue en minutos, sin DevOps). ~$10–15/mes todo incluido.
- **Escala (decenas de negocios):** Hetzner + Coolify + PostgreSQL administrado. Un VPS de ~$5–10/mes soporta muchos tenants; el costo marginal por negocio extra tiende a cero.

### 18.3 Otros costos fijos / únicos

- **Cerebro IA (LLM):** centavos por conversación; ~$0.10–0.50 MXN por conversación completa. Solo en planes con IA.
- **Dominio:** ~$10–15 USD/año (para el panel y el webhook con HTTPS).
- **BSP (opcional, ej. 360dialog):** algunos cobran cuota fija o markup por mensaje; con **Meta Cloud API directo** te ahorras el BSP pero gestionas tú la verificación.
- **Verificación de negocio en Meta:** gratis (requiere datos fiscales del negocio).

**Costo fijo total estimado arrancando (1–10 negocios): ~$15–30 USD/mes** + variable de recordatorios. Punto de equilibrio muy bajo: con 1–2 suscripciones Pro ya se cubre la infraestructura.

---

## 19. Requisitos de infraestructura y cuentas

Para desplegar y operar la plataforma necesitas:

**Infraestructura técnica:**

- **Host / servidor 24/7** (VPS o PaaS de la sección 18.2) — sustituye a la laptop, debe estar siempre encendido.
- **Base de datos PostgreSQL** (administrada o en el mismo VPS).
- **Dominio + HTTPS** (certificado SSL, gratis con Let's Encrypt) para el webhook de Meta y el panel.
- **Servidor del webhook** expuesto públicamente (en producción; en pruebas se puede usar `ngrok`).

**Cuentas y accesos de WhatsApp (por negocio cliente):**

- **Meta Business Account** verificada (con datos fiscales del negocio).
- **WhatsApp Business Platform (Cloud API)** habilitada → de ahí sale el `phone_number_id` que se guarda por tenant.
- **Número de teléfono dedicado** para cada negocio, **no registrado antes en la app normal de WhatsApp** (puede ser un número virtual/VoIP o una línea física nueva). Un número = un negocio.
- **Plantillas de mensaje aprobadas por Meta** (recordatorio, confirmación) — trámite simple pero necesario para los proactivos.
- **Token de acceso** (permanente, de sistema) para enviar mensajes.

**Cuentas de la plataforma (tú, el proveedor del SaaS):**

- Cuenta del proveedor de hosting.
- Clave de API del LLM (Anthropic/OpenAI) si ofreces el cerebro con IA.
- Pasarela de cobro (Stripe o Mercado Pago) para las suscripciones de los negocios.
- Opcional: cuenta de BSP si no usas Meta directo.

**Legal / cumplimiento (México, LFPDPPP):** aviso de privacidad, consentimiento (opt-in) de los clientes para recordatorios, y resguardo de teléfonos/nombres.

---

## 20. Módulo de onboarding self-service

Objetivo: que un negocio nuevo se dé de alta y configure su bot **sin tocar
código**, desde la plataforma. Se construye como un asistente (wizard) guiado,
respaldado por un script de Python que crea y valida el tenant.

**Datos que pide el asistente, por pasos:**

1. **Datos del negocio:** nombre, giro (barbería, dentista, veterinaria…), dirección, zona horaria, **logo** (carga de imagen).
2. **Terminología:** cómo llamar a sus recursos (Barberos / Doctores / Veterinarios) y a sus citas (Cita / Consulta).
3. **Recursos / profesionales:** nombre, horario laboral, días libres de cada uno.
4. **Servicios:** nombre, duración y precio (alimentan la disponibilidad y los precios mostrados).
5. **Mensajes personalizables:** saludo, mensaje de escalación a humano, plantilla de recordatorio, mensaje de cierre. Con variables tipo `{nombre}`, `{hora}`, `{profesional}`.
6. **Promociones (opcional):** texto y vigencia, para mensajes de marketing.
7. **Conexión de WhatsApp:** `phone_number_id`, token y `admin_phone` (a quién se escalan los chats).
8. **Plan contratado:** selección de plan y alta de cobro (Stripe/Mercado Pago).

**Cómo encaja en el código actual:**

- Reutiliza los modelos existentes (`Barberia`→Negocio, `Barbero`→Recurso, `Servicio`), añadiendo campos: `giro`, `logo_url`, `zona_horaria`, y una tabla `mensajes` (o un JSON `config_mensajes`) por negocio.
- El script de alta (`onboarding.py`) crea el registro del tenant, su `api_key` del panel, siembra recursos/servicios y guarda los textos personalizados — la versión "para muchos" de lo que hoy hace `seed.py`.
- El cerebro (`brain.py`) ya recibe la `barberia`/negocio; solo hay que hacer que lea los **mensajes y la terminología** de la config del tenant en vez de tenerlos fijos.

**Entregable sugerido (siguiente iteración):** un endpoint `POST /api/negocios` + pantallas del wizard en el panel, o una primera versión por CLI (`python -m app.onboarding`) que pida los datos y deje el negocio listo para operar.

---

*Documento de planificación técnica. Los costos son estimaciones de junio 2026 y deben confirmarse al contratar cada proveedor. Las tarifas de WhatsApp Cloud API (México) y de hosting fueron validadas con fuentes públicas en junio 2026.*
