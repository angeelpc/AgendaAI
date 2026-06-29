"""Textos del bot por negocio (multi-giro).

Centraliza todos los mensajes que antes estaban fijos en el cerebro. Cada texto
se arma a partir de los terminos del negocio (termino_recurso, termino_negocio,
emoji) y puede sobreescribirse desde `config_mensajes` (JSON) sin tocar codigo.

Los valores por defecto reproducen exactamente el comportamiento de barberia,
asi que los negocios existentes no cambian.
"""
import json


class Textos:
    def __init__(self, barberia):
        try:
            self.cfg = json.loads(barberia.config_mensajes or "{}")
            if not isinstance(self.cfg, dict):
                self.cfg = {}
        except (ValueError, TypeError):
            self.cfg = {}
        self.recurso = getattr(barberia, "termino_recurso", None) or "barbero"
        self.negocio = getattr(barberia, "termino_negocio", None) or "la barbería"
        self.emoji = getattr(barberia, "emoji", None) or "💈"

    def _o(self, key, default):
        """Override desde config_mensajes si existe; si no, el default."""
        val = self.cfg.get(key)
        return val if isinstance(val, str) and val.strip() else default

    # --- saludo / pedir datos ---
    def pedir_recurso(self, listado: str) -> str:
        base = self._o("saludo", f"¡Hola! Con gusto te agendo 😊 ¿Con qué {self.recurso}?")
        return f"{base}\n{listado}"

    def pedir_dia(self) -> str:
        return self._o("pedir_dia", "¿Para qué día te gustaría? (hoy, mañana, sábado, etc.)")

    def pedir_nombre(self) -> str:
        return self._o("pedir_nombre", "¡Perfecto! ¿Me confirmas tu nombre? 🙂")

    def pedir_nombre_otra_vez(self) -> str:
        return "¿Me confirmas tu nombre, por favor?"

    # --- disponibilidad / confirmacion ---
    def ofrecer(self, recurso_nombre: str, fecha: str, horas: str) -> str:
        return f"{recurso_nombre} tiene libre el {fecha} a las {horas}. ¿Cuál te queda?"

    def confirmar(self, cliente: str, recurso_nombre: str, fecha: str, hora: str) -> str:
        return (f"Confirmo: {cliente}, con {recurso_nombre} el {fecha} a las {hora}. "
                f"¿Lo agendo? (responde SÍ)")

    def agendada(self, cliente: str, recurso_nombre: str, fecha: str, hora: str) -> str:
        return (f"¡Listo, {cliente}! ✅ Cita confirmada con {recurso_nombre} el "
                f"{fecha} a las {hora}. Te mandaré un recordatorio. {self.emoji}")

    def sin_slots(self, recurso_nombre: str) -> str:
        return f"{recurso_nombre} no tiene horarios libres ese día. ¿Probamos otro día?"

    def slot_ocupado(self) -> str:
        return "Uy, ese horario se acaba de ocupar. ¿Elegimos otro?"

    # --- cancelacion / escalacion ---
    def cancelada(self) -> str:
        return self._o("cancelada", "Listo, cancelé tu cita. ¿Quieres agendar otra?")

    def sin_cita(self) -> str:
        return "No encuentro una cita activa a tu nombre. ¿Deseas agendar una?"

    def escalacion(self) -> str:
        return self._o(
            "escalacion",
            f"Entiendo. Te paso con el equipo de {self.negocio} para atenderte "
            f"personalmente; en un momento te contactan. 🙏",
        )

    def no_entendi(self) -> str:
        return "¿Podrías repetirme eso, por favor?"

    # --- recordatorio ---
    def recordatorio(self, nombre: str, dia: str, hora: str, recurso_nombre: str) -> str:
        tpl = self._o(
            "recordatorio",
            "Hola {nombre} 👋 Te recordamos tu cita el {dia} a las {hora} con "
            "{recurso} en {negocio}. Responde CONFIRMAR o CANCELAR. {emoji}",
        )
        try:
            return tpl.format(nombre=nombre, dia=dia, hora=hora,
                              recurso=recurso_nombre, negocio=self.negocio, emoji=self.emoji)
        except (KeyError, IndexError):
            # si el override trae placeholders raros, no fallar
            return (f"Hola {nombre}, te recordamos tu cita el {dia} a las {hora} "
                    f"con {recurso_nombre}. Responde CONFIRMAR o CANCELAR.")


def textos(barberia) -> Textos:
    return Textos(barberia)
