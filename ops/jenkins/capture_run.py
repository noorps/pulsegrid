"""Trigger Jenkins and save its actual console and result metadata, including failures."""

import argparse
import base64
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8081')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--force-gate-failure', action='store_true', help='Exercise the artificial threshold test')
    modes.add_argument('--inject-cpu-regression', action='store_true', help='Throttle the service and check normal thresholds')
    parser.add_argument('--build-number', type=int, help='Export an existing build instead of starting a new one')
    parser.add_argument('--output-dir', type=Path, default=Path('docs/jenkins'))
    args = parser.parse_args()
    if args.build_number is not None and args.build_number < 1:
        parser.error('--build-number must be positive')
    auth = base64.b64encode(
        f'{os.environ["JENKINS_USER"]}:{os.environ["JENKINS_TOKEN"]}'.encode()).decode()

    def fetch(url, data=None):
        with urlopen(Request(url, data=data, headers={'Authorization': f'Basic {auth}'}), timeout=30) as response:
            return response.read(), response.headers

    def wait_json(url, predicate, deadline):
        while time.monotonic() < deadline:
            result = json.loads(fetch(url)[0])
            if result.get('cancelled'):
                raise RuntimeError('Jenkins queue item cancelled')
            if predicate(result):
                return result
            time.sleep(3)
        raise TimeoutError(f'Timed out waiting for {url}')

    job_url = args.url.rstrip('/') + '/job/pulsegrid/'
    deadline = time.monotonic() + 2400
    if args.build_number is None:
        body = urlencode({'MIN_EVENTS_PER_SEC': '750', 'MAX_P95_MS': '150',
                          'FORCE_GATE_FAILURE': str(args.force_gate_failure).lower(),
                          'INJECT_CPU_REGRESSION': str(args.inject_cpu_regression).lower()}).encode()
        _, headers = fetch(job_url + 'buildWithParameters', body)
        queued = wait_json(headers['Location'] + 'api/json', lambda item: 'executable' in item, deadline)
        build_url = queued['executable']['url']
    else:
        build_url = job_url + f'{args.build_number}/'
    # The result may be assigned before cleanup finishes.
    result = wait_json(build_url + 'api/json',
                       lambda item: item.get('result') is not None and not item.get('building', True), deadline)
    expected = 'FAILURE' if args.force_gate_failure or args.inject_cpu_regression else 'SUCCESS'
    mode = 'regression' if args.inject_cpu_regression else ('gate-failed' if args.force_gate_failure else 'green')
    label = mode if result['result'] == expected else 'attempt'
    prefix = args.output_dir / f'{label}-{result["number"]}-{result["result"].lower()}'
    prefix.parent.mkdir(parents=True, exist_ok=True)
    while time.monotonic() < deadline:
        console = fetch(build_url + 'consoleText')[0]
        if console.rstrip().endswith(f'Finished: {result["result"]}'.encode()):
            break
        time.sleep(1)
    else:
        raise TimeoutError('Completed Jenkins console did not include its final result')
    prefix.with_suffix('.log').write_bytes(console)
    prefix.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    for artifact in ('benchmark.txt', 'warmup.txt', 'gate.json', 'revision.txt', 'health.json', 'regression.json'):
        try:
            content = fetch(build_url + 'artifact/artifacts/' + artifact)[0]
        except HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        (args.output_dir / f'build-{result["number"]}-{artifact}').write_bytes(content)
    print(f'Build {result["number"]}: {result["result"]}; console: {prefix.with_suffix(".log")}')
    if result['result'] != expected:
        raise SystemExit(f'Expected {expected}, got {result["result"]}; inspect saved console')
    if args.force_gate_failure:
        gate = json.loads(fetch(build_url + 'artifact/artifacts/gate.json')[0])
        if gate['passed'] or not any('throughput' in item for item in gate['failures']):
            raise SystemExit('Jenkins failed, but throughput gate failure was not verified')
        print('Confirmed: throughput gate failed and Jenkins finished FAILURE.')
    if args.inject_cpu_regression:
        gate = json.loads(fetch(build_url + 'artifact/artifacts/gate.json')[0])
        limits = json.loads(fetch(build_url + 'artifact/artifacts/regression.json')[0])
        if (gate['passed'] or not gate['failures'] or gate['min_events_per_sec'] != 750
                or gate['max_p95_ms'] != 150
                or limits.get('NanoCpus') != 250000000):
            raise SystemExit('Real service regression at normal thresholds was not verified')
        if gate['accepted'] != 10000 or gate['total'] != 10000:
            raise SystemExit('Regression run did not accept all 10,000 readings')
        print('Confirmed: a CPU-limited service failed the normal 750/150 gate and Jenkins finished FAILURE.')


if __name__ == '__main__':
    main()
