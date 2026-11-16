from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from backend.auth import CurrentUser, current_user
from backend.models.schemas import Plan, PlanChoice, PlanChooseRequest
from backend.services import billing

router = APIRouter()


@router.get("/plans", response_model=list[Plan])
def list_plans(_: CurrentUser = Depends(current_user)):
    return billing.list_plans()


@router.get("/plans/current", response_model=Optional[Plan])
def current_plan(user: CurrentUser = Depends(current_user)):
    return billing.current_plan(user.id)


# Simulated checkout: the plan is recorded, no payment is taken (`charged` is always false).
@router.post("/plans/choose", response_model=PlanChoice)
def choose_plan(body: PlanChooseRequest, user: CurrentUser = Depends(current_user)):
    return PlanChoice(plan=billing.choose_plan(user.id, body.slug), charged=False)
