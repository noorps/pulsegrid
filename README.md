# pulsegrid

[![verify](https://github.com/noorps/pulsegrid/actions/workflows/verify.yml/badge.svg)](https://github.com/noorps/pulsegrid/actions/workflows/verify.yml)

pulsegrid is a small multi-tenant telemetry platform built around the kinds of problems that show up when thousands of devices are sending data at the same time. it accepts vehicle-style telemetry over an API, partitions events by tenant and device in kafka, retries transient failures, sends poisoned records to a dead-letter topic, and materializes the latest reading for low-latency queries.

## measured run

[github actions run #2](https://github.com/noorps/pulsegrid/actions/runs/34680597374/job/103518415961#step:5:1) accepted 10,000/10,000 simulated readings at 1,003 events/sec with 56.3 ms p50 and 106.6 ms p95 request latency. the run used 64 concurrent clients against the full docker compose stack with one kafka broker.

this is a repeatable portfolio benchmark on a github-hosted linux runner, not a production-scale claim. the workflow builds the stack from the repository before every run.

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

the load test prints accepted events, throughput, and p50/p95 request latency. the measured result above is tied to the public github actions run so the environment and output can be checked directly.

## jenkins locally

The root `Jenkinsfile` builds with Java 21/Maven, runs unit tests, starts the
Compose stack and waits for health, benchmarks 10,000 readings, checks the gate,
and publishes results. Its always block saves service logs and removes the stack
after success or failure. GitHub Actions continues to run its existing workflow.

The gate requires **at least 750 events/sec**, **p95 at most 150 ms**, and
**10,000/10,000 accepted**. Compared with the original Actions measurement of
1,003 events/sec and 106.6 ms p95, that allows about 25% less throughput and 41%
more tail latency for machine variation. These are portfolio performance budgets.
The thresholds are parameters at the top of `Jenkinsfile`.

With Docker Desktop's Linux engine and Compose running, start Jenkins from main:

```bash
git switch main
docker compose -f ops/jenkins/compose.yml up -d --build
docker compose -f ops/jenkins/compose.yml exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

Open [local Jenkins](http://localhost:8081), unlock it and finish the setup wizard.
The image includes Pipeline, Git and JUnit plugins and the build tools. The
automatically created `pulsegrid` job reads committed files from the local clone's
`main` branch. For another branch, set `PULSEGRID_BRANCH` before creating the job
or change an existing job's SCM branch. Leave host ports 8080 and 9090 free.
The controller uses the Docker socket, so this setup is for trusted local builds.

Click **Build Now** initially, then **Build with Parameters** for later runs.
The steady-state protocol uses a fixed 120-second warmup before a fresh measured
10,000-event sample, 64 clients on logical CPU 0, and two-processor JVM awareness.
See [benchmark environments and evidence](docs/jenkins/README.md) for configuration
and why the Jenkins and older Actions numbers differ.

To capture evidence, create a Jenkins API token, set `JENKINS_USER` and
`JENKINS_TOKEN` in your shell, then run:

```bash
python ops/jenkins/capture_run.py
python ops/jenkins/capture_run.py --inject-cpu-regression
```

The second run limits the warmed application to **0.25 CPU**, measures the same
10,000 readings, and checks the normal **750/150** thresholds. It saves the actual
Docker CPU configuration, measurements, gate decision and final Jenkins console.
Cleanup removes the limited container; the next normal run starts unrestricted.
`FORCE_GATE_FAILURE` remains available as a threshold-wiring test; the CPU-limited
run is the regression evidence. Use `--build-number N` to export a completed run.

Windows only: `tools/local-dev/keep-awake.ps1` temporarily prevents idle sleep while local builds run.

Stop Jenkins without deleting its history:

```bash
docker compose -f ops/jenkins/compose.yml down
```

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
