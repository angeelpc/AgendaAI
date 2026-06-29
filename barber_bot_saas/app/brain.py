"""Cerebro del bot.

Dos implementaciones que comparten el MISMO motor de agenda:
- RuleBrain: motor de reglas/slot-filling en espanol. Funciona offline, sin internet.
- LLMBrain: usa un modelo de lenguaje (Anthropic) con function-calling. Se activa
  solo si hay ANTHROPIC_API_KEY. Conversacion natural.

get_brain() elige automaticamente segun la configuracion.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, date

from .config import settings
from .agenda import AgendaService
from .models import Barberia, Barbero, Servicio, Cita
from .branding import Textos
from . import nlu


@dataclass
class Reply:
    text: str
    escalate: bool = False
    booked_cita_id: int | None = None
    meta: dict = field(default_factory=dict)


# ----------------------------- utilidades -----------------------------

def _barbero_nombres(db, barberia_id):
    rows = db.query(Barbero).filter(Barbero.barberia_id == barberia_id).all()
    return {nlu.norm(b.nombre): b.numero for b in rows}, rows


def _default_service(db, barberia_id) -> Servicio | None:
    return db.query(Servicio).filter(Servicio.barberia_id == barberia_id).first()


def _fmt_hora(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _fmt_fecha(d: date) -> str:
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return f"{dias[d.weekday()]} {d.day:02d}/{d.month:02d}"


# ----------------------------- motor de reglas -----------------------------

class RuleBrain:
    """Slot-filling: barbero -> dia -> hora -> nombre -> confirmar."""

    def respond(self, db, barberia: Barberia, conv, message: str,
                ahora: datetime | None = None) -> Reply:
        ahora = ahora or datetime.now()
        self.t = Textos(barberia)
        agenda = AgendaService(db, barberia.id)
        nombres, barberos = _barbero_nombres(db, barberia.id)
        servicio = _default_service(db, barberia.id)
        dur = servicio.duracion_min if servicio else 45
        ctx = json.loads(conv.contexto or "{}")

        # 1) Escalacion
        if nlu.has_any(message, nlu.ESCALATION_WORDS):
            conv.estado = "humano"
            conv.contexto = json.dumps(ctx)
            return Reply(text=self.t.escalacion(), escalate=True)

        # 2) Cancelar ultima cita
        if nlu.has_any(message, nlu.CANCEL_WORDS) and not ctx.get("inicio"):
            ult = (
                db.query(Cita)
                .filter(Cita.cliente_telefono == conv.telefono,
                        Cita.estado == "agendada")
                .order_by(Cita.inicio.desc())
                .first()
            )
            if ult:
                agenda.cancel(ult.id)
                conv.contexto = "{}"
                return Reply(text=self.t.cancelada())
            return Reply(text=self.t.sin_cita())

        # 3) Parseo incremental de entidades
        num = nlu.parse_barbero_numero(message, nombres)
        if num and any(b.numero == num for b in barberos):
            ctx["barbero_numero"] = num
            ctx.pop("offered", None)  # cambiar de barbero invalida slots ofrecidos

        dia = nlu.parse_dia(message, ahora.date())
        if dia:
            ctx["fecha"] = dia.isoformat()
            ctx.pop("offered", None)

        periodo = nlu.parse_periodo(message)
        if periodo:
            ctx["periodo"] = periodo
            ctx.pop("offered", None)

        # confirmacion
        confirming = nlu.norm(message) in {nlu.norm(w) for w in nlu.CONFIRM_WORDS} \
            or nlu.has_any(message, {"confirmar", "confirmo"})

        # 4) Si estamos esperando nombre
        if ctx.get("stage") == "need_name":
            nombre = nlu.parse_nombre(message)
            if nombre:
                ctx["cliente_nombre"] = nombre
                return self._confirm_step(ctx, conv, nombres, barberos)
            return self._save(conv, ctx, Reply(text=self.t.pedir_nombre_otra_vez()))

        # 5) Confirmacion final -> reservar
        if ctx.get("stage") == "need_confirm" and confirming:
            return self._do_booking(db, agenda, barberia, conv, ctx, barberos, dur,
                                    servicio.nombre if servicio else "Corte")

        # 6) Hora elegida
        hora = nlu.parse_hora(message)
        if hora and ctx.get("barbero_numero") and ctx.get("fecha"):
            slots = self._slots(agenda, ctx, barberos, dur, ahora)
            match = next((s for s in slots if s.time() == hora), None)
            if match:
                ctx["inicio"] = match.isoformat()
                ctx["stage"] = "need_name" if not ctx.get("cliente_nombre") else "need_confirm"
                if ctx.get("cliente_nombre"):
                    return self._confirm_step(ctx, conv, nombres, barberos)
                return self._save(conv, ctx, Reply(text=self.t.pedir_nombre()))
            elif slots:
                return self._offer(conv, ctx, slots, barberos)

        # 7) Pedir lo que falta
        if not ctx.get("barbero_numero"):
            ctx["stage"] = "need_barbero"
            listado = "  ".join(f"{b.numero}) {b.nombre}" for b in sorted(barberos, key=lambda x: x.numero))
            return self._save(conv, ctx, Reply(text=self.t.pedir_recurso(listado)))

        if not ctx.get("fecha"):
            ctx["stage"] = "need_day"
            return self._save(conv, ctx, Reply(text=self.t.pedir_dia()))

        # tenemos recurso + fecha -> ofrecer horarios
        slots = self._slots(agenda, ctx, barberos, dur, ahora)
        if not slots:
            b = self._barbero(barberos, ctx["barbero_numero"])
            ctx.pop("fecha", None)
            ctx.pop("periodo", None)
            return self._save(conv, ctx, Reply(text=self.t.sin_slots(b.nombre)))
        return self._offer(conv, ctx, slots, barberos)

    # ---- helpers internos ----
    def _barbero(self, barberos, numero):
        return next(b for b in barberos if b.numero == numero)

    def _slots(self, agenda, ctx, barberos, dur, ahora):
        b = self._barbero(barberos, ctx["barbero_numero"])
        dia = date.fromisoformat(ctx["fecha"])
        slots = agenda.get_availability(b, dia, dur, ahora)
        periodo = ctx.get("periodo")
        if periodo == "manana":
            slots = [s for s in slots if s.time().hour < 13]
        elif periodo == "tarde":
            slots = [s for s in slots if 13 <= s.time().hour < 19]
        elif periodo == "noche":
            slots = [s for s in slots if s.time().hour >= 19]
        return slots

    def _offer(self, conv, ctx, slots, barberos):
        ctx["stage"] = "need_time"
        ctx["offered"] = [s.isoformat() for s in slots]
        b = self._barbero(barberos, ctx["barbero_numero"])
        muestra = slots[:3]
        horas = ", ".join(_fmt_hora(s) for s in muestra)
        return self._save(conv, ctx, Reply(
            text=self.t.ofrecer(b.nombre, _fmt_fecha(slots[0].date()), horas)))

    def _confirm_step(self, ctx, conv, nombres, barberos):
        ctx["stage"] = "need_confirm"
        b = self._barbero(barberos, ctx["barbero_numero"])
        inicio = datetime.fromisoformat(ctx["inicio"])
        return self._save(conv, ctx, Reply(
            text=self.t.confirmar(ctx["cliente_nombre"], b.nombre,
                                  _fmt_fecha(inicio.date()), _fmt_hora(inicio))))

    def _do_booking(self, db, agenda, barberia, conv, ctx, barberos, dur, servicio_nombre):
        b = self._barbero(barberos, ctx["barbero_numero"])
        inicio = datetime.fromisoformat(ctx["inicio"])
        try:
            cita = agenda.book(b, inicio, dur, ctx["cliente_nombre"],
                               conv.telefono, servicio_nombre)
        except ValueError:
            ctx.pop("inicio", None)
            ctx["stage"] = "need_time"
            return self._save(conv, ctx, Reply(text=self.t.slot_ocupado()))
        conv.contexto = "{}"
        conv.estado = "bot"
        return Reply(
            text=self.t.agendada(cita.cliente_nombre, b.nombre,
                                 _fmt_fecha(inicio.date()), _fmt_hora(inicio)),
            booked_cita_id=cita.id,
        )

    def _save(self, conv, ctx, reply: Reply) -> Reply:
        conv.contexto = json.dumps(ctx)
        return reply


# ----------------------------- cerebro con IA (opcional) -----------------------------

class LLMBrain:
    """Usa Anthropic con function-calling. Requiere ANTHROPIC_API_KEY.
    Comparte el motor de agenda con RuleBrain mediante 'tools'."""

    TOOLS = [
        {
            "name": "consultar_disponibilidad",
            "description": "Devuelve horarios libres de un barbero (1-4) en una fecha (YYYY-MM-DD).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "barbero_numero": {"type": "integer"},
                    "fecha": {"type": "string"},
                },
                "required": ["barbero_numero", "fecha"],
            },
        },
        {
            "name": "agendar_cita",
            "description": "Agenda una cita. Usa una fecha/hora que haya devuelto consultar_disponibilidad.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "barbero_numero": {"type": "integer"},
                    "fecha": {"type": "string"},
                    "hora": {"type": "string"},
                    "cliente_nombre": {"type": "string"},
                },
                "required": ["barbero_numero", "fecha", "hora", "cliente_nombre"],
            },
        },
        {
            "name": "escalar_a_humano",
            "description": "Pasa la conversacion a una persona cuando el cliente pide algo fuera de agendar (quejas, pagos, reembolsos, casos confusos).",
            "input_schema": {
                "type": "object",
                "properties": {"motivo": {"type": "string"}},
                "required": ["motivo"],
            },
        },
    ]

    def respond(self, db, barberia, conv, message, ahora=None):
        import anthropic  # import perezoso
        from datetime import timedelta
        ahora = ahora or datetime.now()
        agenda = AgendaService(db, barberia.id)
        nombres, barberos = _barbero_nombres(db, barberia.id)
        servicio = _default_service(db, barberia.id)
        dur = servicio.duracion_min if servicio else 45

        def run_tool(name, args):
            if name == "consultar_disponibilidad":
                b = agenda.barbero_por_numero(args["barbero_numero"])
                if not b:
                    return {"error": "barbero no existe"}
                d = date.fromisoformat(args["fecha"])
                slots = agenda.get_availability(b, d, dur, ahora)
                return {"slots": [s.isoformat() for s in slots[:8]]}
            if name == "agendar_cita":
                b = agenda.barbero_por_numero(args["barbero_numero"])
                inicio = datetime.fromisoformat(f"{args['fecha']}T{args['hora']}")
                try:
                    cita = agenda.book(b, inicio, dur, args["cliente_nombre"],
                                       conv.telefono, servicio.nombre if servicio else "Corte")
                    return {"ok": True, "cita_id": cita.id}
                except ValueError as e:
                    return {"ok": False, "error": str(e)}
            if name == "escalar_a_humano":
                conv.estado = "humano"
                return {"escalado": True}
            return {"error": "tool desconocida"}

        t = Textos(barberia)
        recurso = t.recurso
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        sys = (
            f"Eres el asistente de WhatsApp de {barberia.nombre}. Agendas citas con "
            f"{'estos ' + recurso + 's' if not recurso.endswith('s') else 'estos ' + recurso}: "
            + ", ".join(f"{b.numero}={b.nombre}" for b in barberos) + ". "
            f"Hoy es {ahora.date().isoformat()}. Servicio: {servicio.nombre if servicio else 'Corte'} "
            f"({dur} min). Solo ofreces horarios que devuelva consultar_disponibilidad; "
            "nunca inventes horarios ni precios. Eres breve y amable. Si el cliente pide "
            "algo fuera de agendar/consultar/cancelar, usa escalar_a_humano."
        )
        history = json.loads(conv.contexto or "[]")
        if not isinstance(history, list):
            history = []
        history.append({"role": "user", "content": message})

        escalate = False
        booked = None
        for _ in range(6):
            resp = client.messages.create(
                model=settings.LLM_MODEL, max_tokens=500, system=sys,
                tools=self.TOOLS, messages=history,
            )
            history.append({"role": "assistant", "content": resp.content})
            tool_uses = [c for c in resp.content if getattr(c, "type", "") == "tool_use"]
            if not tool_uses:
                text = "".join(getattr(c, "text", "") for c in resp.content)
                conv.contexto = json.dumps(history)
                return Reply(text=text, escalate=escalate, booked_cita_id=booked)
            results = []
            for tu in tool_uses:
                out = run_tool(tu.name, tu.input)
                if tu.name == "escalar_a_humano":
                    escalate = True
                if tu.name == "agendar_cita" and out.get("ok"):
                    booked = out.get("cita_id")
                results.append({"type": "tool_result", "tool_use_id": tu.id,
                                "content": json.dumps(out)})
            history.append({"role": "user", "content": results})
        conv.contexto = json.dumps(history)
        return Reply(text="¿Podrías repetirme eso, por favor?", escalate=escalate)


def get_brain():
    return LLMBrain() if settings.use_llm else RuleBrain()
