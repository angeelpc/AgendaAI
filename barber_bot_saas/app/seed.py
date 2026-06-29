"""Crea datos de ejemplo: una barberia con 4 barberos y un servicio."""
from .database import SessionLocal, init_db
from .models import Barberia, Barbero, Servicio


def seed(reset: bool = True) -> int:
    init_db()
    db = SessionLocal()
    try:
        if reset:
            db.query(Barbero).delete()
            db.query(Servicio).delete()
            db.query(Barberia).delete()
            db.commit()

        b = Barberia(nombre="Barbería El Filo", whatsapp_phone_id="DEMO_PHONE_ID",
                     admin_phone="5215555555555", plan="pro",
                     api_key="demo-key-filo")
        db.add(b)
        db.commit()
        db.refresh(b)

        barberos = [
            Barbero(barberia_id=b.id, numero=1, nombre="Carlos", work_start="10:00", work_end="20:00", days_off="0"),
            Barbero(barberia_id=b.id, numero=2, nombre="Memo",   work_start="10:00", work_end="20:00", days_off="0"),
            Barbero(barberia_id=b.id, numero=3, nombre="Luis",   work_start="11:00", work_end="19:00", days_off="0,6"),
            Barbero(barberia_id=b.id, numero=4, nombre="Ana",    work_start="09:00", work_end="18:00", days_off="0"),
        ]
        db.add_all(barberos)
        db.add(Servicio(barberia_id=b.id, nombre="Corte", duracion_min=45, precio=150))
        db.commit()
        return b.id
    finally:
        db.close()


if __name__ == "__main__":
    new_id = seed()
    print(f"Seed listo. Barberia id={new_id}")
