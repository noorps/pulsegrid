package dev.noorps.pulsegrid.service;

import dev.noorps.pulsegrid.model.TelemetryEvent;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class LatestReadingStoreTest {
    private final LatestReadingStore store = new LatestReadingStore();

    @Test
    void ignoresDuplicateEvents() {
        UUID id = UUID.randomUUID();
        var event = event(id, "2026-09-11T12:00:00Z", 42.0);

        assertThat(store.record(event)).isTrue();
        assertThat(store.record(event)).isFalse();
    }

    @Test
    void lateEventsDoNotOverwriteNewerReadings() {
        store.record(event(UUID.randomUUID(), "2026-09-11T12:05:00Z", 80.0));
        store.record(event(UUID.randomUUID(), "2026-09-11T12:00:00Z", 10.0));

        assertThat(store.latest("demo", "vehicle-7", "battery_pct"))
                .get().extracting(TelemetryEvent::value).isEqualTo(80.0);
    }

    @Test
    void tenantDataIsIsolated() {
        store.record(event(UUID.randomUUID(), "2026-09-11T12:00:00Z", 42.0));

        assertThat(store.latest("other", "vehicle-7", "battery_pct")).isEmpty();
    }

    private TelemetryEvent event(UUID id, String timestamp, double value) {
        return new TelemetryEvent("demo", "vehicle-7", id, Instant.parse(timestamp), "battery_pct", value);
    }
}
