"""Catalogo de planes del SaaS y limites por plan.

Los limites se aplican en el resto de la app (onboarding, recursos, recordatorios).
Precios en MXN/mes, alineados con el plan de negocio (seccion 13/17 del documento).
"""
from datetime import datetime

PLANES = {
    "starter": {
        "nombre": "Starter", "precio_mxn": 499,
        "max_recursos": 2, "max_usuarios": 1,
        "recordatorios_mes": 200, "ia": False,
    },
    "pro": {
        "nombre": "Pro", "precio_mxn": 899,
        "max_recursos": 6, "max_usuarios": 3,
        "recordatorios_mes": 800, "ia": True,
    },
    "premium": {
        "nombre": "Premium", "precio_mxn": 1499,
        "max_recursos": 15, "max_usuarios": 6,
        "recordatorios_mes": 2000, "ia": True,
    },
}

DEFAULT_PLAN = "pro"
# Estados de suscripcion en los que el negocio puede operar.
ESTADOS_ACTIVOS = {"prueba", "activa"}


def plan_de(negocio) -> dict:
    return PLANES.get((negocio.plan or "").lower(), PLANES[DEFAULT_PLAN])


def limite_recursos(negocio) -> int:
    return plan_de(negocio)["max_recursos"]


def limite_recordatorios(negocio) -> int:
    return plan_de(negocio)["recordatorios_mes"]


def limite_usuarios(negocio) -> int:
    return plan_de(negocio)["max_usuarios"]


def suscripcion_activa(negocio, ahora: datetime | None = None) -> bool:
    """True si el negocio puede operar (en prueba o pagada y vigente)."""
    ahora = ahora or datetime.now()
    if (negocio.estado_suscripcion or "prueba") not in ESTADOS_ACTIVOS:
        return False
    if negocio.suscripcion_hasta and negocio.suscripcion_hasta < ahora:
        return False
    return True


def dias_restantes(negocio, ahora: datetime | None = None) -> int | None:
    ahora = ahora or datetime.now()
    if not negocio.suscripcion_hasta:
        return None
    delta = negocio.suscripcion_hasta - ahora
    return max(0, delta.days)
