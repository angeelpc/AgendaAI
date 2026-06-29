"""Cobro de suscripciones con Mercado Pago (preapproval).

Flujo:
1. El negocio elige un plan -> crear_suscripcion() devuelve un `init_point`
   (URL de Mercado Pago donde el dueno autoriza el cobro recurrente).
2. Mercado Pago avisa por webhook (topicos subscription_preapproval /
   subscription_authorized_payment / payments).
3. procesar_notificacion() consulta el estado y activa/renueva o vence la
   suscripcion del negocio.

Sin `MERCADOPAGO_ACCESS_TOKEN` corre en modo simulado: no llama a la API real,
devuelve un init_point local y permite probar todo el flujo de estados.
"""
from datetime import datetime, timedelta

import httpx

from .config import settings
from .plans import PLANES, plan_de


def _add_month(d: datetime) -> datetime:
    """Suma ~1 mes (30 dias, suficiente para vigencia de suscripcion)."""
    return d + timedelta(days=30)


# ----------------------------- crear suscripcion -----------------------------

def crear_suscripcion(negocio, plan_key: str, email: str) -> dict:
    """Crea una suscripcion (preapproval) en Mercado Pago para el negocio.

    Devuelve {init_point, preapproval_id, simulado}. En simulado no cobra:
    solo entrega un enlace local para confirmar el alta manualmente.
    """
    plan_key = (plan_key or "").lower()
    if plan_key not in PLANES:
        raise ValueError("Plan invalido")
    plan = PLANES[plan_key]

    if not settings.use_mercadopago:
        pid = f"SIMULADO-{negocio.id}-{plan_key}"
        return {
            "simulado": True,
            "preapproval_id": pid,
            "init_point": f"{settings.PUBLIC_BASE_URL}/billing/simulado?negocio={negocio.id}&plan={plan_key}",
        }

    payload = {
        "reason": f"Suscripcion {plan['nombre']} - {negocio.nombre}",
        "external_reference": f"negocio:{negocio.id}|plan:{plan_key}",
        "payer_email": email,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(plan["precio_mxn"]),
            "currency_id": "MXN",
        },
        "back_url": f"{settings.PUBLIC_BASE_URL}/panel",
        "status": "pending",
    }
    headers = {"Authorization": f"Bearer {settings.MERCADOPAGO_ACCESS_TOKEN}",
               "Content-Type": "application/json"}
    with httpx.Client(timeout=20) as c:
        r = c.post(f"{settings.MERCADOPAGO_BASE_URL}/preapproval",
                   headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    return {
        "simulado": False,
        "preapproval_id": data.get("id", ""),
        "init_point": data.get("init_point") or data.get("sandbox_init_point", ""),
    }


# ----------------------------- cambios de estado -----------------------------

def activar_suscripcion(db, negocio, plan_key: str | None = None,
                        preapproval_id: str | None = None,
                        ahora: datetime | None = None) -> None:
    """Marca la suscripcion como activa y extiende la vigencia un mes."""
    ahora = ahora or datetime.now()
    if plan_key:
        negocio.plan = plan_key
    if preapproval_id:
        negocio.mp_preapproval_id = preapproval_id
    base = negocio.suscripcion_hasta if (negocio.suscripcion_hasta and
                                         negocio.suscripcion_hasta > ahora) else ahora
    negocio.estado_suscripcion = "activa"
    negocio.suscripcion_hasta = _add_month(base)
    db.commit()


def vencer_suscripcion(db, negocio) -> None:
    negocio.estado_suscripcion = "vencida"
    db.commit()


def cancelar_suscripcion(db, negocio) -> None:
    negocio.estado_suscripcion = "cancelada"
    db.commit()


# ----------------------------- webhook -----------------------------

def _consultar_preapproval(preapproval_id: str) -> dict:
    if not settings.use_mercadopago:
        return {}
    headers = {"Authorization": f"Bearer {settings.MERCADOPAGO_ACCESS_TOKEN}"}
    with httpx.Client(timeout=20) as c:
        r = c.get(f"{settings.MERCADOPAGO_BASE_URL}/preapproval/{preapproval_id}",
                  headers=headers)
        r.raise_for_status()
        return r.json()


def _negocio_por_preapproval(db, preapproval_id: str):
    from .models import Barberia
    return (db.query(Barberia)
            .filter(Barberia.mp_preapproval_id == preapproval_id).first())


def procesar_notificacion(db, tipo: str, data_id: str) -> dict:
    """Procesa una notificacion de Mercado Pago y actualiza el negocio.

    `tipo` es el topico (subscription_preapproval, subscription_authorized_payment,
    payment...). `data_id` es el id del recurso. Mapea el estado de MP a nuestro
    estado de suscripcion.
    """
    if tipo in ("subscription_preapproval", "preapproval"):
        info = _consultar_preapproval(data_id)
        estado_mp = (info.get("status") or "").lower()
        negocio = _negocio_por_preapproval(db, data_id)
        if not negocio:
            return {"ok": False, "motivo": "negocio no encontrado"}
        if estado_mp == "authorized":
            activar_suscripcion(db, negocio, preapproval_id=data_id)
            return {"ok": True, "estado": "activa"}
        if estado_mp in ("cancelled", "paused"):
            cancelar_suscripcion(db, negocio)
            return {"ok": True, "estado": "cancelada"}
        return {"ok": True, "estado": negocio.estado_suscripcion}

    if tipo in ("subscription_authorized_payment", "payment"):
        # Un pago recurrente se acredito: renovamos un mes.
        # En produccion se consulta el pago para obtener el preapproval asociado.
        negocio = _negocio_por_preapproval(db, data_id)
        if negocio:
            activar_suscripcion(db, negocio)
            return {"ok": True, "estado": "activa"}
        return {"ok": False, "motivo": "sin preapproval asociado"}

    return {"ok": False, "motivo": f"topico no manejado: {tipo}"}
