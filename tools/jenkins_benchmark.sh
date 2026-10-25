#!/bin/sh
set -eu

# Resolve the service once to keep Docker DNS latency out of the HTTP sample.
app_id="$(docker compose ps -q app)"
app_ip="$(docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$app_id")"
test -n "$app_ip"

exec docker run --rm -i --name "$COMPOSE_PROJECT_NAME-benchmark" \
    --cpuset-cpus "$BENCHMARK_CPUSET" \
    --network "${COMPOSE_PROJECT_NAME}_default" --add-host "app:$app_ip" \
    "$BENCHMARK_IMAGE" python - --events "$1" --workers 64 --base-url http://app:8080 \
    < tools/load_test.py
