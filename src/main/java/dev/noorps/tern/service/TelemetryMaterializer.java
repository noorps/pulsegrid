package dev.noorps.tern.service;

import dev.noorps.tern.model.TelemetryEvent;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class TelemetryMaterializer {
    private final LatestReadingStore store;
    private final Counter materialized;
    private final Counter duplicates;

    public TelemetryMaterializer(LatestReadingStore store, MeterRegistry registry) {
        this.store = store;
        this.materialized = registry.counter("tern_materialized_total", "result", "stored");
        this.duplicates = registry.counter("tern_materialized_total", "result", "duplicate");
    }

    @KafkaListener(topics = "${tern.topics.telemetry}")
    public void consume(TelemetryEvent event) {
        if (store.record(event)) {
            materialized.increment();
        } else {
            duplicates.increment();
        }
    }
}
