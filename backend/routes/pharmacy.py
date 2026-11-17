from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.models.schemas import PharmacyOrder, PharmacyOrderCreateRequest
from backend.store import Store, get_store

router = APIRouter()


@router.get("/pharmacy/orders", response_model=list[PharmacyOrder])
def list_orders(store: Store = Depends(get_store)):
    return store.list_orders()


@router.post("/pharmacy/orders", response_model=list[PharmacyOrder], status_code=201)
def create_orders(body: PharmacyOrderCreateRequest, store: Store = Depends(get_store)):
    return store.create_orders(body.items)


@router.post("/pharmacy/orders/{order_id}/cancel", response_model=PharmacyOrder)
def cancel_order(order_id: str, store: Store = Depends(get_store)):
    return store.cancel_order(order_id)
