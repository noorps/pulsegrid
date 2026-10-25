# tern

tern takes device readings over HTTP, publishes them to Kafka, and keeps the latest
reading available for queries. I built it to work through ordering and replay
problems that show up when lots of clients send telemetry at once.

The hard part was preserving per-device ordering under concurrent clients without
letting a replay or an old reading corrupt the latest value. Events use
`tenantId:deviceId` as the Kafka key. The materializer ignores duplicate event ids
and won't replace a newer reading with a stale one. Producers wait for Kafka's
acknowledgment before the API returns 202. The latest-reading store is in memory.

## measurements

The original [Actions run](https://github.com/noorps/tern/actions/runs/34680597374)
accepted **10,000/10,000 readings at 1,003 events/sec**, with **56.3 ms p50 and
106.6 ms p95**. That used 64 clients, Java 21 and one Kafka 3.9.0 broker on a
GitHub-hosted Ubuntu 24.04 runner (standard public-runner class: 4 vCPU, 16 GB RAM).

A local Jenkins run accepted the same count at **1,392 events/sec**, with
**34.7 ms p50 and 116.6 ms p95**. That was an i7-1355U laptop with 16 GB RAM;
Docker had 12 logical CPUs and about 7.6 GiB RAM. It used a 120-second warmup,
64 clients pinned to logical CPU 0, and two-processor JVM awareness. These are
different environments, not a before/after speedup. A later unrestricted run
missed the p95 budget; the [raw evidence and configuration](docs/jenkins/README.md)
include both passes and misses.

## running locally

You need Docker Compose and Python 3 for the load client.

```bash
docker compose up -d --build --wait --wait-timeout 180
curl --retry 30 --retry-connrefused --retry-delay 2 -fsS http://localhost:8080/actuator/health
python tools/load_test.py --events 10000 --workers 64
```

The API is on port 8080 and Prometheus is on 9090. The load client uses the local
`demo` tenant and `demo-local-key`. You can read a materialized value with:

```bash
curl -H "X-API-Key: demo-local-key" "http://localhost:8080/v1/tenants/demo/devices/vehicle-7/latest?metric=battery_pct"
docker compose down
```

For host-side unit tests, use Java 21 and Maven: `mvn test`.

## jenkins

Stop the regular stack first so ports 8080 and 9090 are free, then start the local
controller:

```bash
docker compose -f ops/jenkins/compose.yml up -d --build
docker compose -f ops/jenkins/compose.yml exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

Open [Jenkins](http://localhost:8081), finish setup, and run the `tern` job. It reads
committed files from the local clone's `main` branch. Set `TERN_BRANCH` before
creating the job to use a different branch. The controller mounts the Docker
socket, so use this setup for trusted local builds.

The pipeline builds, tests, starts the stack, warms it for 120 seconds, then
measures a fresh 10,000 readings. The gate requires **at least 750 events/sec,
at most 150 ms p95, and 10,000/10,000 accepted**. Those values leave about 25%
throughput and 41% p95 headroom from the original hosted result. Cleanup runs
after a pass or failure, and both outcomes keep their artifacts.

After the first build, set `JENKINS_USER` and `JENKINS_TOKEN` to your local account
and API token to run and export a build:

```bash
python ops/jenkins/capture_run.py
python ops/jenkins/capture_run.py --inject-cpu-regression
```

The second command limits the warmed service to 0.25 CPU while keeping the normal
gate thresholds. The recorded regression accepted every reading but measured
**154 events/sec and 693.3 ms p95**, and Jenkins finished FAILURE. See
[the original consoles](docs/jenkins/README.md) for the complete record.

On Windows, `tools/local-dev/keep-awake.ps1` prevents idle sleep during local builds.
Stop the controller with `docker compose -f ops/jenkins/compose.yml down`.

For event-time aggregates and historical files from the same stream, see
[event-time-pipeline](https://github.com/noorps/event-time-pipeline).
