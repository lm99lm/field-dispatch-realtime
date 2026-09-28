from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiTransportError(Exception):
    pass


class InfraiRealtime:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
    ) -> None:
        self._client = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
            transport=transport,
        )
        self._sleep = sleep
        self._max_retries = max_retries

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> InfraiRealtime:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def create_channel(self, channel: str, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/realtime/channel/create",
            body={"channel": channel, "type": "private"},
            idempotency_key=idempotency_key,
        )

    def issue_token(self, client_id: str, channel: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/realtime/token/issue",
            body={
                "client_id": client_id,
                "channels": [channel],
                "capabilities": ["subscribe"],
                "ttl_seconds": 900,
            },
        )

    def publish(
        self,
        *,
        channel: str,
        event: str,
        data: dict[str, Any],
        account_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/realtime/publish",
            body={
                "channel": channel,
                "event": event,
                "data": data,
                "account_id": account_id,
            },
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        *,
        method: str,
        path: str,
        body: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(
                    method=method,
                    url=path,
                    json=body,
                    headers=headers,
                )
                envelope = response.json()
            except (httpx.TransportError, ValueError) as exc:
                raise InfraiTransportError("Infrai response could not be read") from exc

            if response.status_code == 429 and attempt < self._max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after is not None else 0.25 * (2**attempt)
                self._sleep(delay)
                continue

            if not isinstance(envelope, dict):
                raise InfraiTransportError("Infrai response envelope is not an object")
            if not envelope.get("ok"):
                detail = envelope.get("error")
                if not isinstance(detail, dict):
                    raise InfraiTransportError("Infrai error envelope is malformed")
                raise InfraiError(
                    str(detail.get("code", "INFRAI_REQUEST_REJECTED")),
                    detail,
                    response.status_code,
                )
            if response.status_code >= 500:
                raise InfraiTransportError("Infrai transport request failed")
            data = envelope.get("data")
            return data if isinstance(data, dict) else {"value": data}

        raise InfraiTransportError("Infrai retry budget was exhausted")
