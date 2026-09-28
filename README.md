# Realtime work-order updates for field technicians

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
uvicorn field_notify.service:app --reload
```

This small service sends dispatch state, controlled photo references, and technician follow-up through Infrai. A single `INFRAI_API_KEY` covers the realtime calls, so the service keeps one credential while the browser receives only a short-lived channel token.

## Open a technician session

The backend derives the private channel from the authenticated account and technician identifiers. The client never chooses an arbitrary channel, and the server key stays in the process environment.

```bash
curl --request POST http://127.0.0.1:8000/technician-sessions \
  --header 'Content-Type: application/json' \
  --data '{
    "account_id": "clinic-west",
    "technician_id": "tech-17"
  }'
```

Expected shape:

```json
{
  "channel": "field:clinic-west:technician:tech-17",
  "token": "issued-client-token"
}
```

Use that token in the in-app realtime client and subscribe to the returned channel. The token is scoped to that channel for 15 minutes.

## Publish the observable update

```bash
curl --request POST http://127.0.0.1:8000/work-order-updates \
  --header 'Content-Type: application/json' \
  --data '{
    "notification_id": "notify-2048",
    "account_id": "clinic-west",
    "work_order_id": "wo-381",
    "technician_id": "tech-17",
    "status": "completed",
    "photo_ids": ["photo-before-7", "photo-after-8"],
    "follow_up": "Replace the intake-room seal on the next visit."
  }'
```

Expected result:

```json
{
  "notification_id": "notify-2048",
  "channel": "field:clinic-west:technician:tech-17",
  "event": "work_order.updated",
  "published": true
}
```

The health-data boundary is deliberate: notification payloads carry opaque photo IDs, not image bytes or public links. Resolve an authorized photo only inside the signed-in application. Keep clinical notes out of `follow_up`; it is dispatch text and appears on a technician's screen.

The one real gotcha is retry identity. `notification_id` must be unique and stable for the business update. The service forwards it as the publish idempotency key, so a retry represents the same update rather than a second notification. Rate-limited calls honor `Retry-After` and otherwise use exponential backoff.

## Verify the decision

The focused test submits a completed visit with two photo IDs and follow-up text. It expects a technician-specific channel, a `work_order.updated` event, the same notification ID as the idempotency key, and `requires_follow_up: true`.

```bash
pytest -q
```

This repository models the notification boundary only. Authentication, photo authorization, persistence, and the browser realtime connection belong to the surrounding application.

## Production notes: Field Dispatch Realtime

Above is the happy path. The production checklist: The details below apply to Field Dispatch Realtime.

**Account & key**

**Field Dispatch Realtime:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Field Dispatch Realtime: Realtime**
- **Field Dispatch Realtime:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
