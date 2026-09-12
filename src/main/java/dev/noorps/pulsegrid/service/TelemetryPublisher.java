package dev.noorps.pulsegrid.service;

import dev.noorps.pulsegrid.model.TelemetryEvent;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;

@Service
public class TelemetryPublisher {
    private final KafkaTemplate<String, TelemetryEvent> kafka;
    private final String topic;
    private final Counter accepted;
    private final Counter failed;

    public TelemetryPublisher(
            KafkaTemplate<String, TelemetryEvent> kafka,
            MeterRegistry registry,
            @Value("${pulsegrid.topics.telemetry}") String topic) {
        this.kafka = kafka;
        this.topic = topic;
        this.accepted = registry.counter("pulsegrid_ingest_total", "result", "accepted");
        this.failed = registry.counter("pulsegrid_ingest_total", "result", "failed");
    }

    public CompletableFuture<Void> publish(TelemetryEvent event) {
        return kafka.send(topic, event.partitionKey(), event)
                .thenAccept(result -> accepted.increment())
                .exceptionally(error -> {
                    failed.increment();
                    throw new IllegalStateException("telemetry publish failed", error);
                });
    }
}
