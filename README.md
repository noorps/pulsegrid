# pulsegrid

pulsegrid is a small multi-tenant telemetry platform built around the kinds of problems that show up when thousands of devices are sending data at the same time. it accepts vehicle-style telemetry over an API, partitions events by tenant and device in kafka, retries transient failures, sends poisoned records to a dead-letter topic, and materializes the latest reading for low-latency queries.

## why i built it

i wanted to understand what makes a telemetry service reliable beyond just getting a `200` back from an endpoint. duplicate events, late readings, noisy tenants, broker failures, and visibility into the system all matter once data is arriving continuously. this project gave me a focused way to work through those tradeoffs in java instead of hiding them behind a managed service.

## architecture

```text
device clients
     |
     v
ingest api  ->  kafka: telemetry.events.v1  ->  materializer  ->  latest-reading api
  |                         |
  |                         +-> retries -> dead-letter topic
  +-> tenant auth
  +-> prometheus metrics
```

events use `tenantId:deviceId` as the kafka key, so readings for one device stay ordered while partitions can be consumed concurrently. producers use `acks=all` and idempotent delivery. consumers keep manual record-level offsets, reject duplicates by event id, and refuse to let a late reading overwrite a newer one.

## run it

you need docker compose.

```bash
docker compose up --build
```

send an event:

```bash
curl -X POST http://localhost:8080/v1/tenants/demo/telemetry \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-local-key" \
  -d '{"tenantId":"demo","deviceId":"vehicle-7","eventId":"550e8400-e29b-41d4-a716-446655440000","recordedAt":"2026-09-11T12:00:00Z","metric":"battery_pct","value":81.4}'
```

query the latest reading:

```bash
curl "http://localhost:8080/v1/tenants/demo/devices/vehicle-7/latest?metric=battery_pct" \
  -H "X-API-Key: demo-local-key"
```

prometheus is available at `http://localhost:9090`. application health is at `http://localhost:8080/actuator/health`.

## test it

```bash
mvn test
python tools/load_test.py --events 10000 --workers 64
```

the load test prints accepted events, throughput, and p50/p95 request latency. results depend on the machine, so i keep measured numbers out of the readme unless they are reproducible on the hardware being discussed.

## failure handling

- kafka publish failures return an error instead of pretending the event was accepted
- consumer failures use exponential backoff before moving the record to the dead-letter topic
- event ids make materialization idempotent
- tenant credentials are compared in constant time and every query is scoped to a tenant
- prometheus counters separate accepted, failed, stored, and duplicate events

## next steps

- replace the in-memory latest-reading view with a replicated store
- add schema compatibility checks for event-version migrations
- run kafka with three brokers and validate behavior during broker loss
