package dev.noorps.pulsegrid.service;

import dev.noorps.pulsegrid.model.TelemetryEvent;
import org.springframework.stereotype.Component;

import java.util.Comparator;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class LatestReadingStore {
    private final Map<String, TelemetryEvent> latestByMetric = new ConcurrentHashMap<>();
    private final Map<UUID, Boolean> processedEvents = new ConcurrentHashMap<>();

    public boolean record(TelemetryEvent event) {
        if (processedEvents.putIfAbsent(event.eventId(), Boolean.TRUE) != null) {
            return false;
        }
        latestByMetric.merge(key(event), event, (current, incoming) ->
                Comparator.comparing(TelemetryEvent::recordedAt).compare(incoming, current) > 0 ? incoming : current);
        return true;
    }

    public Optional<TelemetryEvent> latest(String tenantId, String deviceId, String metric) {
        return Optional.ofNullable(latestByMetric.get(key(tenantId, deviceId, metric)));
    }

    private String key(TelemetryEvent event) {
        return key(event.tenantId(), event.deviceId(), event.metric());
    }

    private String key(String tenantId, String deviceId, String metric) {
        return tenantId + "\u0000" + deviceId + "\u0000" + metric;
    }
}
