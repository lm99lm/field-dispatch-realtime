from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .infrai_realtime import InfraiRealtime


class DispatchStatus(StrEnum):
    ASSIGNED = "assigned"
    EN_ROUTE = "en_route"
    ON_SITE = "on_site"
    COMPLETED = "completed"


class WorkOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_id: str = Field(min_length=8, max_length=80)
    account_id: str = Field(min_length=1, max_length=80)
    work_order_id: str = Field(min_length=1, max_length=80)
    technician_id: str = Field(min_length=1, max_length=80)
    status: DispatchStatus
    photo_ids: list[str] = Field(default_factory=list, max_length=8)
    follow_up: str | None = Field(default=None, max_length=240)


class NotificationReceipt(BaseModel):
    notification_id: str
    channel: str
    event: str
    published: bool


def technician_channel(account_id: str, technician_id: str) -> str:
    return f"field:{account_id}:technician:{technician_id}"


def notification_payload(update: WorkOrderUpdate) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "notification_id": update.notification_id,
        "work_order_id": update.work_order_id,
        "status": update.status.value,
        "photo_ids": update.photo_ids,
        "requires_follow_up": bool(update.follow_up),
    }
    if update.follow_up:
        payload["follow_up"] = update.follow_up
    return payload


def notify_technician(update: WorkOrderUpdate, publisher: InfraiRealtime) -> NotificationReceipt:
    channel = technician_channel(update.account_id, update.technician_id)
    publisher.publish(
        channel=channel,
        event="work_order.updated",
        data=notification_payload(update),
        account_id=update.account_id,
        idempotency_key=update.notification_id,
    )
    return NotificationReceipt(
        notification_id=update.notification_id,
        channel=channel,
        event="work_order.updated",
        published=True,
    )
