"""Demo de extremo a extremo SIN WhatsApp ni IA (modo reglas offline).

Simula clientes que escriben por WhatsApp y muestra como el bot agenda,
escala a humano y guarda las citas. Ejecutar:  python run_demo.py
"""
import json
import re
from datetime import datetime

from app.database import SessionLocal
from app.models import Barberia, Conversacion, Cita, Barbero
from app.seed import seed
from app.service import handle_incoming, get_or_create_conv


def chat(db, barberia, telefono, texto, ahora):
    print(f"  Cliente: {texto}")
    reply = handle_incoming(db, barberia, telefono, texto, ahora=ahora, send=False)
    if reply.text:
        for linea in reply.text.split("\n"):
            print(f"  Bot:     {linea}")
    if reply.escalate:
        print("  [sistema] >> Conversacion escalada a un humano y avisado el dueno.")
    print()
    return reply


def offered_time(db, barberia_id, telefono):
    conv = (
        db.query(Conversacion)
        .filter(Conversacion.barberia_id == barberia_id,
                Conversacion.telefono == telefono).first()
    )
    ctx = json.loads(conv.contexto or "{}")
    off = ctx.get("offered") or []
    return datetime.fromisoformat(off[0]).strftime("%H:%M") if off else None


def main():
    bid = seed(reset=True)
    db = SessionLocal()
    barberia = db.get(Barberia, bid)
    ahora = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    print("=" * 60)
    print(f"  {barberia.nombre} — Bot de citas (modo reglas offline)")
    print("=" * 60)

    # ---------- Escenario 1: agendar una cita completa ----------
    print("\n--- Escenario 1: cliente agenda una cita ---\n")
    tel = "5219991112233"
    chat(db, barberia, tel, "Hola, quiero cortarme el pelo el sábado", ahora)
    chat(db, barberia, tel, "con el 2 en la tarde", ahora)
    hora = offered_time(db, barberia.id, tel)
    chat(db, barberia, tel, f"{hora} está bien", ahora)
    chat(db, barberia, tel, "Angel", ahora)
    chat(db, barberia, tel, "sí", ahora)

    # ---------- Escenario 2: escalacion a humano ----------
    print("--- Escenario 2: el bot detecta algo que no puede resolver ---\n")
    tel2 = "5219994445566"
    chat(db, barberia, tel2, "oigan el corte de ayer quedó mal, quiero un reembolso", ahora)

    # ---------- Escenario 3: otro cliente, mismo barbero ----------
    print("--- Escenario 3: segundo cliente agenda con el mismo barbero ---\n")
    tel3 = "5219997778899"
    chat(db, barberia, tel3, "buenas, me das cita el sábado con Memo", ahora)
    hora3 = offered_time(db, barberia.id, tel3)
    chat(db, barberia, tel3, f"a las {hora3}", ahora)
    chat(db, barberia, tel3, "me llamo Roberto", ahora)
    chat(db, barberia, tel3, "confirmar", ahora)

    # ---------- Resultado: citas en la base de datos ----------
    print("=" * 60)
    print("  CITAS AGENDADAS EN LA BASE DE DATOS")
    print("=" * 60)
    citas = db.query(Cita).filter(Cita.estado == "agendada").order_by(Cita.inicio).all()
    for c in citas:
        b = db.get(Barbero, c.barbero_id)
        print(f"  • {c.cliente_nombre:10s} | {b.nombre:7s} | "
              f"{c.inicio.strftime('%a %d/%m %H:%M')} | {c.servicio}")
    if not citas:
        print("  (ninguna)")
    print()
    db.close()


if __name__ == "__main__":
    main()
