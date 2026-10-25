FROM prom/prometheus:v3.2.1
COPY ops/prometheus.yml /etc/prometheus/prometheus.yml
