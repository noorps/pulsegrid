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

Jenkins runs alongside the unchanged GitHub Actions workflow. The root `Jenkinsfile`
builds with Java 21/Maven, runs unit tests, starts Compose and checks API health,
runs the existing 10,000-event benchmark, applies the gate, and publishes artifacts.
Integration sends separate 10,000-event warmup batches for a fixed 120 seconds
(finishing the last batch) before the measured run. This settles JVM compilation
and Kafka initialization on the local machine. Warmup output is archived separately;
the gate checks only the subsequent fresh 10,000-event run. This is a steady-state
benchmark, and the warmup duration never depends on whether metrics pass. Earlier
cold and short-warmup runs missed the budgets and are retained in the evidence.
The historical GitHub Actions measurement used its original workflow.
Its `post { always { ... } }` block collects service logs and tears down Compose,
including volumes, after success or failure. Failed gates still archive their results.

The gate defaults at the top of `Jenkinsfile` require **750 events/sec minimum**,
**150 ms p95 maximum**, and **10,000/10,000 accepted**. Relative to the recorded
GitHub Actions baseline (1,003 events/sec, 106.6 ms p95), these allow about 25%
less throughput and 41% more p95 latency for local machine variation. These are
portfolio performance budgets, not production SLOs. Missing or malformed output
fails the gate. Parameters make thresholds adjustable without editing code.

Verified locally in Jenkins: build #8 finished **SUCCESS**, accepting 10,000/10,000
at **1,392 events/sec and 116.6 ms p95** after the fixed warmup. Build #9 used an
impossible throughput threshold and finished **FAILURE** at the Gate stage; its
measured performance was 1,350 events/sec and 117.0 ms p95. Both ran source
`a6d8c8699aaaf12f95eff36e83ec84015800bad3`.

For a local, single-user Jenkins instance, install Docker Desktop with a working
Linux engine and Docker Compose, and check out the implementation branch:

```bash
git switch codex/jenkins-pipeline
docker compose -f ops/jenkins/compose.yml up -d --build
docker compose -f ops/jenkins/compose.yml exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

Open [local Jenkins](http://localhost:8081), unlock with that password, and finish
the setup wizard, creating your admin account (for example, `noorps`). The image
preinstalls Pipeline, Git, and JUnit plugins, Maven, Python, and Docker Compose.
The `pulsegrid` job is created automatically and checks out **committed** files
from this local clone's `codex/jenkins-pipeline` branch. Commit changes before
running it. A different branch requires changing the job's SCM branch setting.

The controller uses the host Docker engine through `/var/run/docker.sock` and
checks API health at `http://docker:8080` through a host-gateway alias. Warmup and
measurement use a disposable `python:3.13-slim` container on the application's
Compose network at `http://app:8080`, avoiding Docker Desktop's published-port
route for measured traffic. The unchanged load-test script is streamed over stdin,
so the benchmark needs no host workspace bind mount. The app address is pinned
in the load container's hosts file to avoid repeated Docker DNS queries. The client
uses 64 workers on logical CPU 0 (`BENCHMARK_CPUSET`); both service JVMs see two
processors through `-XX:ActiveProcessorCount=2`. This local profile reduces scheduling
overhead; it is not a CPU quota on the services. The Jenkins-only
`ops/jenkins/stack.yml` override builds Prometheus with the same configuration baked
into its image, avoiding a bind mount from a workspace the host daemon cannot see.
The root Compose file and GitHub Actions workflow are unchanged. Leave host ports
8080 and 9090 free, and use one PulseGrid job at a time. Jenkins listens only on
host loopback at port 8081.

Docker socket access gives Jenkins broad control over the Docker host, including
the ability to mount host files. This setup runs trusted builds on the controller;
use it only for local, single-user development.

Keep the computer awake during builds: Windows Modern Standby interrupted one
verification run and broke its connection. On Windows, optionally run
`./ops/jenkins/keep-awake.ps1` in a separate PowerShell window. It temporarily prevents
idle sleep for 30 minutes (or `-Minutes 60`) and releases the request on exit.

Click **Build Now** for the first run; subsequent runs expose **Build with Parameters**.
For authentic evidence capture, generate an API token under your Jenkins account's
Security settings, set `JENKINS_USER` and `JENKINS_TOKEN` in your shell, and run:

```bash
python ops/jenkins/capture_run.py
python ops/jenkins/capture_run.py --force-gate-failure
```

The second command raises only that run's throughput minimum to an intentionally
impossible 1,000,000,000,000 events/sec. It does not alter benchmark measurements
or persist a broken threshold. It requires Jenkins `FAILURE` and an archived
throughput gate rejection; an earlier infrastructure failure does not qualify.
The next normal run again uses 750/150 defaults. The script saves unmodified
`consoleText` and Jenkins build metadata under `docs/jenkins/`. Jenkins also archives
benchmark text, gate JSON, revision, health response, service logs, and (on success)
the application JAR. Review evidence before committing it.
Use `--build-number N` to re-export a completed run without starting another build.

Stop local Jenkins after use (keeps its volume and leaves Docker Desktop running):

```bash
docker compose -f ops/jenkins/compose.yml down
```

Execution status and evidence are recorded in [docs/jenkins](docs/jenkins/README.md).

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
