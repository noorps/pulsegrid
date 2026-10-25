pipeline {
    agent any
    parameters {
        string(name: 'MIN_EVENTS_PER_SEC', defaultValue: '750', description: 'Minimum benchmark throughput')
        string(name: 'MAX_P95_MS', defaultValue: '150', description: 'Maximum p95 request latency in milliseconds')
        booleanParam(name: 'FORCE_GATE_FAILURE', defaultValue: false, description: 'Evidence run: use an impossible throughput threshold without changing measured results')
    }
    environment {
        COMPOSE_PROJECT_NAME = 'pulsegrid-jenkins'
        COMPOSE_FILE = 'docker-compose.yml:ops/jenkins/stack.yml'
        BENCHMARK_BASE_URL = 'http://docker:8080'
        WARMUP_EVENTS = '2000'
        BENCHMARK_IMAGE = 'python:3.13-slim'
    }
    options {
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }
    stages {
        stage('Build') {
            steps {
                sh 'rm -rf artifacts && mkdir -p artifacts'
                sh 'git rev-parse HEAD > artifacts/revision.txt'
                sh 'mvn --batch-mode clean package -DskipTests'
            }
        }
        stage('Unit tests') {
            steps {
                sh 'python3 -m unittest discover -s tools -p test_benchmark_gate.py -v'
                sh 'mvn --batch-mode test'
            }
            post { always { junit allowEmptyResults: false, testResults: 'target/surefire-reports/TEST-*.xml' } }
        }
        stage('Integration') {
            steps {
                sh 'docker compose up -d --build --wait --wait-timeout 180'
                sh '''#!/bin/sh
set -eu
for attempt in $(seq 1 60); do
    if curl -fsS "$BENCHMARK_BASE_URL/actuator/health" > artifacts/health.json &&
       python3 -c 'import json; assert json.load(open("artifacts/health.json"))["status"] == "UP"'; then
        exit 0
    fi
    sleep 3
done
echo 'Application did not become healthy' >&2
exit 1
'''
                // Settle JVM compilation and Kafka metadata before the measured 10k run.
                sh '''docker run --rm -i --name "$COMPOSE_PROJECT_NAME-benchmark" \
                    --network "${COMPOSE_PROJECT_NAME}_default" "$BENCHMARK_IMAGE" \
                    python - --events "$WARMUP_EVENTS" --workers 64 --base-url http://app:8080 \
                    < tools/load_test.py > artifacts/warmup.txt'''
            }
        }
        stage('Benchmark') {
            steps {
                // Redirect first so Python's failure cannot be hidden by a pipe to tee.
                sh '''docker run --rm -i --name "$COMPOSE_PROJECT_NAME-benchmark" \
                    --network "${COMPOSE_PROJECT_NAME}_default" "$BENCHMARK_IMAGE" \
                    python - --events 10000 --workers 64 --base-url http://app:8080 \
                    < tools/load_test.py > artifacts/benchmark.txt'''
                sh 'cat artifacts/benchmark.txt'
            }
        }
        stage('Gate') {
            steps {
                withEnv(["MIN_EVENTS_PER_SEC=${params.MIN_EVENTS_PER_SEC}",
                         "MAX_P95_MS=${params.MAX_P95_MS}",
                         "FORCE_GATE_FAILURE=${params.FORCE_GATE_FAILURE}"]) {
                    sh '''#!/bin/sh
set -eu
minimum="$MIN_EVENTS_PER_SEC"
if [ "$FORCE_GATE_FAILURE" = "true" ]; then
    minimum=1000000000000
fi
python3 tools/benchmark_gate.py artifacts/benchmark.txt \
    --min-events-per-sec "$minimum" --max-p95-ms "$MAX_P95_MS" \
    --output artifacts/gate.json
'''
                }
            }
        }
        stage('Publish') {
            steps { archiveArtifacts artifacts: 'artifacts/*,target/*.jar', fingerprint: true }
        }
    }
    post {
        always {
            script {
                // Finally guarantees teardown even when log collection fails.
                try {
                    sh 'mkdir -p artifacts; docker compose logs --no-color > artifacts/compose.log 2>&1'
                } finally {
                    try {
                        try {
                            sh '''if docker container inspect "$COMPOSE_PROJECT_NAME-benchmark" >/dev/null 2>&1; then
                                docker rm -f "$COMPOSE_PROJECT_NAME-benchmark"
                            fi'''
                        } finally {
                            sh 'docker compose down --volumes --remove-orphans'
                        }
                    } finally {
                        archiveArtifacts artifacts: 'artifacts/*', allowEmptyArchive: true
                    }
                }
            }
        }
    }
}
