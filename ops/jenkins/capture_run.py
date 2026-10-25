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
    parser.add_argument('--force-gate-failure', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=Path('docs/jenkins'))
    args = parser.parse_args()
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
    # API token authentication is exempt from Jenkins CSRF crumbs.
    body = urlencode({'MIN_EVENTS_PER_SEC': '750', 'MAX_P95_MS': '150',
                      'FORCE_GATE_FAILURE': str(args.force_gate_failure).lower()}).encode()
    _, headers = fetch(job_url + 'buildWithParameters', body)
    deadline = time.monotonic() + 2400
    queued = wait_json(headers['Location'] + 'api/json', lambda item: 'executable' in item, deadline)
    build_url = queued['executable']['url']
    result = wait_json(build_url + 'api/json', lambda item: item.get('result') is not None, deadline)
    expected = 'FAILURE' if args.force_gate_failure else 'SUCCESS'
    label = ('gate-failed' if args.force_gate_failure else 'green') if result['result'] == expected else 'attempt'
    prefix = args.output_dir / f'{label}-{result["number"]}-{result["result"].lower()}'
    prefix.parent.mkdir(parents=True, exist_ok=True)
    console = fetch(build_url + 'consoleText')[0]
    prefix.with_suffix('.log').write_bytes(console)
    prefix.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    for artifact in ('benchmark.txt', 'warmup.txt', 'gate.json', 'revision.txt', 'health.json'):
        try:
            content = fetch(build_url + 'artifact/artifacts/' + artifact)[0]
        except HTTPError as exc:
            if exc.code == 404:
                continue  # Earlier failures may not produce every artifact.
            raise
        (args.output_dir / f'build-{result["number"]}-{artifact}').write_bytes(content)
    print(f'Build {result["number"]}: {result["result"]}; console: {prefix.with_suffix(".log")}')
    if result['result'] != expected:
        raise SystemExit(f'Expected {expected}, got {result["result"]}; inspect saved console')
    if args.force_gate_failure:
        # A FAILURE elsewhere is not evidence of a gate failure.
        gate = json.loads(fetch(build_url + 'artifact/artifacts/gate.json')[0])
        if gate['passed'] or not any('throughput' in item for item in gate['failures']):
            raise SystemExit('Jenkins failed, but throughput gate failure was not verified')
        print('Confirmed: throughput gate failed and Jenkins finished FAILURE.')


if __name__ == '__main__':
    main()
