from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .dispatch_service import NotificationReceipt, WorkOrderUpdate, notify_technician, technician_channel
from .infrai_realtime import InfraiError, InfraiRealtime, InfraiTransportError

app = FastAPI(title="Field dispatch realtime")


class TechnicianSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=80)
    technician_id: str = Field(min_length=1, max_length=80)


class SessionGrant(BaseModel):
    channel: str
    token: str


def realtime_client() -> InfraiRealtime:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("INFRAI_API_KEY is required")
    with InfraiRealtime(api_key) as client:
        yield client


Realtime = Annotated[InfraiRealtime, Depends(realtime_client)]


def client_error(exc: InfraiError) -> HTTPException:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})


@app.post("/technician-sessions", response_model=SessionGrant)
def create_technician_session(request: TechnicianSession, realtime: Realtime) -> SessionGrant:
    channel = technician_channel(request.account_id, request.technician_id)
    try:
        realtime.create_channel(channel, f"channel:{channel}")
        grant = realtime.issue_token(request.technician_id, channel)
    except InfraiError as exc:
        raise client_error(exc) from exc
    except InfraiTransportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SessionGrant(channel=channel, token=str(grant["token"]))


@app.post("/work-order-updates", response_model=NotificationReceipt)
def publish_work_order_update(update: WorkOrderUpdate, realtime: Realtime) -> NotificationReceipt:
    try:
        return notify_technician(update, realtime)
    except InfraiError as exc:
        raise client_error(exc) from exc
    except InfraiTransportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

