import argparse
import json
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.request import Request, urlopen


def send(url, api_key, device_number):
    payload = json.dumps({
        "tenantId": "demo",
        "deviceId": f"vehicle-{device_number % 1000}",
        "eventId": str(uuid.uuid4()),
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "metric": "battery_pct",
        "value": 20 + device_number % 80,
    }).encode()
    request = Request(url, payload, {"Content-Type": "application/json", "X-API-Key": api_key})
    started = time.perf_counter()
    with urlopen(request, timeout=10) as response:
        response.read()
        return response.status, (time.perf_counter() - started) * 1000


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=64)
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()
    url = f"{args.base_url}/v1/tenants/demo/telemetry"

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(send, url, "demo-local-key", index) for index in range(args.events)]
        results = [future.result() for future in as_completed(futures)]
    elapsed = time.perf_counter() - started
    latencies = sorted(latency for _, latency in results)
    p95 = latencies[int(len(latencies) * 0.95) - 1]

    print(f"accepted: {sum(status == 202 for status, _ in results)}/{args.events}")
    print(f"throughput: {args.events / elapsed:.0f} events/sec")
    print(f"p50 latency: {statistics.median(latencies):.1f} ms")
    print(f"p95 latency: {p95:.1f} ms")


if __name__ == "__main__":
    main()
