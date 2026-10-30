"""The planning products drafted for the next operational period (CR-02 C3): the ICS-215
operational planning worksheet and the IAP objectives, stored and served as these models."""

from typing import Literal

from pydantic import BaseModel

from muster.llm.schemas import IapObjective

PlanningStatus = Literal["DRAFT", "released"]


class Ics215Row(BaseModel):
    """One work assignment of the ICS-215: an approved field task and the resource it needs."""

    item_id: int  # the approved package item
    clause_id: str
    location_id: str
    location: str
    work_assignment: str
    resource_kind: str
    required: int
    have: int
    need: int  # required minus have
    reporting_location_id: str | None  # the nearest usable staging area; None if none is usable
    reporting_location: str | None
    requested_arrival_hours: int  # scenario time, hours to landfall: the next period's start
    stop_work: list[str]  # prohibitions in force at the site now (P-4.7)


class PlanningProducts(BaseModel):
    """What the planning draft holds, with how the objective wording was produced."""

    period_start_hours: int  # the next operational period, in hours to landfall
    period_end_hours: int
    ics215: list[Ics215Row]
    objectives: list[IapObjective]
    provider: str  # the provider that worded the objectives, or "template (fallback)"
    fallback: bool
    model: str | None
    prompt_version: str | None  # None for the template wording
    fallback_reason: str | None
