# Verified local Jenkins runs

Executed October 25, 2026 on Docker Desktop's Linux engine. Both primary runs
checked out source `a6d8c8699aaaf12f95eff36e83ec84015800bad3`.

| Build | Accepted | Throughput | p50 | p95 | Effective gate | Jenkins result |
| --- | --- | --- | --- | --- | --- | --- |
| [8](green-8-success.log) | 10,000/10,000 | 1,392 events/sec | 34.7 ms | 116.6 ms | >=750 events/sec, <=150 ms p95 | **SUCCESS** |
| [9](gate-failed-9-failure.log) | 10,000/10,000 | 1,350 events/sec | 36.1 ms | 117.0 ms | >=1,000,000,000,000 events/sec, <=150 ms p95 | **FAILURE** |

Build 9 set `FORCE_GATE_FAILURE=true` for that build only. Its only rejected
condition was throughput below the intentionally impossible test threshold.
The console records `ERROR: script returned exit code 1` and `Finished: FAILURE`.
Publish was skipped; the always block archived results and removed the stack.
The normal gate remains **750 events/sec minimum, 150 ms p95 maximum, and exactly
10,000/10,000 accepted**. [job-defaults.json](job-defaults.json) confirms defaults
remain 750/150 and `FORCE_GATE_FAILURE=false`; no broken source change needs reverting.

## Evidence and integrity

- [Successful full console](green-8-success.log) and [Jenkins metadata](green-8-success.json).
- [Deliberately failed full console](gate-failed-9-failure.log) and [Jenkins metadata](gate-failed-9-failure.json).
- [Successful gate JSON](build-8-gate.json) and [failed gate JSON](build-9-gate.json).
- Raw benchmark, warmup, health and source-revision artifacts are named `build-8-*` and `build-9-*`.
- [verification.json](verification.json) records terminal results, the same tested
  revision, gate decisions, unchanged defaults, and byte-for-byte console matches
  against completed Jenkins `consoleText` responses.
- [SHA256SUMS](SHA256SUMS) contains console checksums. Console files are unedited
  exports, including cleanup and the final Jenkins status line.
- [cleanup-after-runs.json](cleanup-after-runs.json) records zero remaining
  application-project containers and zero benchmark containers after both runs.
- [docker-host.json](docker-host.json), [docker-version.json](docker-version.json),
  and [runtime-images.json](runtime-images.json) record the actual environment.

The exporter waits for `building=false` and the final `Finished:` line before
saving evidence. An intermediate Jenkins result can be assigned while cleanup is
still running. Existing completed runs can be exported again without running them:

```bash
python ops/jenkins/capture_run.py --build-number 8
python ops/jenkins/capture_run.py --build-number 9 --force-gate-failure
```

## Why the two published measurements differ

| | Original Actions run #2 | Local Jenkins build #8 |
| --- | --- | --- |
| Result | 1,003 events/sec; 56.3 ms p50; 106.6 ms p95 | 1,392 events/sec; 34.7 ms p50; 116.6 ms p95 |
| Hardware | GitHub-hosted x64 public Linux runner; documented standard class: 4 vCPU, 16 GB RAM. The job did not record a CPU model or live hardware inventory. | Intel Core i7-1355U laptop, 10 physical cores / 12 logical processors, 16 GB host RAM; Docker VM exposes 12 logical CPUs and about 7.6 GiB RAM. |
| OS | Ubuntu 24.04.5; runner image `20260907.300.1`, recorded in the original job log | Windows 11 with Docker Desktop / WSL2 Linux `6.18.33.2-microsoft-standard-WSL2` |
| Request path | Host Python to `localhost:8080` through the Compose published port | `python:3.13-slim` container directly to the app's Compose network; address pinned in its hosts file; client pinned to logical CPU 0 |
| Warmup and runtime | Starts the stack, waits for health, then measures; no explicit warmup or JVM processor override | Fixed 120-second warmup, then a fresh measured sample; app and broker JVMs use `-XX:ActiveProcessorCount=2` |
| Shared workload | 10,000 readings, 64 workers, one Kafka 3.9.0 broker, Java 21 / Spring Boot application | Same load-test script, event count, worker count, broker version and application |

The original [job log](https://github.com/noorps/pulsegrid/actions/runs/34680597374/job/103518415961)
records the runner image, while GitHub documents the [standard public-runner hardware class](https://docs.github.com/en/actions/reference/runners/github-hosted-runners#standard-github-hosted-runners-for-public-repositories).
These are different hardware and measurement configurations, so they describe two
environments rather than a controlled before/after improvement. Higher throughput
and lower median latency can coexist with a higher p95 because the tail measures
the slower requests. The original job did not capture enough hardware detail to
attribute the differences to a specific CPU model.

## Measurement protocol

This is a **steady-state local benchmark**. Each build starts a fresh Compose
stack, waits for Kafka and API health, and sends separate 10,000-event warmup
batches for a fixed 120 seconds, finishing the last batch. Warmup does not end
early because a result passes, and its measurements do not enter the gate.
The subsequent fresh 10,000-event run alone determines acceptance, throughput,
and latency for the gate. All warmup batches are retained in separate artifacts.

The unchanged `tools/load_test.py` runs with 64 workers in `python:3.13-slim`,
on the application's Compose network. Its script is streamed over stdin; the
current app IP is pinned in the benchmark container's hosts file. This avoids
measuring Docker Desktop's published-port routing and repeated Docker DNS lookups.
The client is pinned to logical CPU 0. App and Kafka JVMs use
`-XX:ActiveProcessorCount=2`, which controls JVM processor awareness rather than
imposing a service CPU quota. The host reports 12 logical CPUs and about 7.6 GiB
of memory available to Docker.

Compare these numbers with runs using the same warmup, client and runtime profile.
The historical GitHub Actions benchmark uses its original protocol; its result is
documented separately in the root README. These local results are portfolio
verification on one laptop, with one Kafka broker.

## Checks completed

- Jenkins itself validated the Declarative Jenkinsfile.
- Java 21/Maven packaging passed, all three Java unit tests passed, and all four
  gate-parser tests passed inside both primary Jenkins runs.
- Live Docker Compose integration, API health, the actual load test, normal Gate,
  successful Publish/JAR fingerprinting, forced Gate failure, failure-artifact
  publishing and always-cleanup ran in Jenkins.
- The successful run reached `Finished: SUCCESS`; the deliberate gate rejection
  reached `Finished: FAILURE`.
- The original root Dockerfile, Compose file, POM, load test and
  `.github/workflows/verify.yml` are byte-for-byte unchanged from base `08f7303`.
- The unchanged [GitHub Actions verification on the tested revision](https://github.com/noorps/pulsegrid/actions/runs/40166118864)
  also passed.

## Earlier retained attempts

| Build | Result | Observation |
| --- | --- | --- |
| [3](attempt-3-failure.log) | FAILURE | Earlier nested-daemon configuration: 224 events/sec, 392.7 ms p95; normal gate rejected both. |
| [4](attempt-4-aborted.log) | ABORTED | Published-port benchmark stalled; stopped during networking diagnosis. |
| [5](attempt-5-failure.log) | FAILURE | Short-warmup direct-network run: 613 events/sec, 181.2 ms p95. |
| [6](attempt-6-failure.log) | FAILURE | Short-warmup run: 515 events/sec, 219.4 ms p95. |
| [7](attempt-7-failure.log) | FAILURE | Modern Standby interrupted Windows for about 40 minutes; a warmup connection broke before Benchmark/Gate. This is infrastructure failure, not deliberate gate evidence. |

Initial local checkout and first-build parameter handling issues were fixed before
the primary runs. Cold and short-warmup misses are retained so the steady-state
measurement's limits are explicit. Docker's startup failure was repaired by
recoverably relocating stale runtime socket directories, preserving images and
volumes. Keep the computer awake while reproducing the tests; the optional
`tools/local-dev/keep-awake.ps1` requests temporary idle-sleep prevention without changing
the power plan. See the root README for setup, authentication and shutdown commands.
