from typing import Any

from field_notify.dispatch_service import WorkOrderUpdate, notification_payload, notify_technician


class RecordingPublisher:
    def __init__(self) -> None:
        self.call: dict[str, Any] = {}

    def publish(self, **kwargs: Any) -> dict[str, Any]:
        self.call = kwargs
        return {"published": True}


def test_completed_visit_routes_private_photo_references_and_follow_up() -> None:
    publisher = RecordingPublisher()
    update = WorkOrderUpdate(
        notification_id="notify-2048",
        account_id="clinic-west",
        work_order_id="wo-381",
        technician_id="tech-17",
        status="completed",
        photo_ids=["photo-before-7", "photo-after-8"],
        follow_up="Replace the intake-room seal on the next visit.",
    )

    receipt = notify_technician(update, publisher)

    assert receipt.channel == "field:clinic-west:technician:tech-17"
    assert receipt.published is True
    assert publisher.call["idempotency_key"] == "notify-2048"
    assert publisher.call["data"] == {
        "notification_id": "notify-2048",
        "work_order_id": "wo-381",
        "status": "completed",
        "photo_ids": ["photo-before-7", "photo-after-8"],
        "requires_follow_up": True,
        "follow_up": "Replace the intake-room seal on the next visit.",
    }


def test_empty_follow_up_is_not_sent_as_message_text() -> None:
    update = WorkOrderUpdate(
        notification_id="notify-2049",
        account_id="clinic-west",
        work_order_id="wo-382",
        technician_id="tech-17",
        status="en_route",
    )

    payload = notification_payload(update)

    assert payload["requires_follow_up"] is False
    assert "follow_up" not in payload

