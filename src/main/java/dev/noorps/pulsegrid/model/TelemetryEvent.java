package dev.noorps.pulsegrid.model;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.Instant;
import java.util.UUID;

public record TelemetryEvent(
        @NotBlank String tenantId,
        @NotBlank String deviceId,
        @NotNull UUID eventId,
        @NotNull Instant recordedAt,
        @NotBlank String metric,
        double value) {

    public String partitionKey() {
        return tenantId + ":" + deviceId;
    }
}
