# Jenkins verification status

Implementation prepared on October 24, 2026 (America/Chicago).

**No green Jenkins run or failed-gate Jenkins run has been obtained yet.**
No Jenkins console logs are included because Jenkins could not be started.
The local Docker CLI is installed, but its Linux engine's named pipe
`//./pipe/dockerDesktopLinuxEngine` is unavailable, including when checked outside
the execution sandbox. Starting Docker Desktop did not make the engine reachable.
This is an environment blocker, not evidence that the pipeline works or fails.

Verified locally:

- Four Python unit tests pass, covering the historical baseline, exact threshold
  boundaries, throughput and latency regressions, incomplete acceptance counts,
  the forced threshold, and missing/duplicate/non-finite metrics. Inputs are
  synthetic fixtures, not new benchmark results.
- `docker compose -f ops/jenkins/compose.yml config --quiet` succeeds.
- `.github/workflows/verify.yml` is unchanged from the cloned base commit.

Not verified: Jenkins Declarative compilation, Java build/tests, container image
builds, live Compose health, benchmark performance, Jenkins failure propagation,
and cleanup during a real build.

Once Docker is available, follow the root README and run both capture commands.
Commit the real `green-<number>-success.log` and `gate-failed-<number>-failure.log`
plus corresponding JSON metadata, and update this status with build numbers,
tested source revision, measured metrics, and confirmation that the Gate stage
caused Jenkins to finish `FAILURE`. Do not substitute parser tests or Docker
startup errors for Jenkins evidence.
