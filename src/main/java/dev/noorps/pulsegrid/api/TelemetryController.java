package dev.noorps.pulsegrid.api;

import dev.noorps.pulsegrid.model.TelemetryEvent;
import dev.noorps.pulsegrid.security.TenantGuard;
import dev.noorps.pulsegrid.service.LatestReadingStore;
import dev.noorps.pulsegrid.service.TelemetryPublisher;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;
import java.util.concurrent.CompletableFuture;

@RestController
@RequestMapping("/v1/tenants/{tenantId}")
public class TelemetryController {
    private final TenantGuard guard;
    private final TelemetryPublisher publisher;
    private final LatestReadingStore store;

    public TelemetryController(TenantGuard guard, TelemetryPublisher publisher, LatestReadingStore store) {
        this.guard = guard;
        this.publisher = publisher;
        this.store = store;
    }

    @PostMapping("/telemetry")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public CompletableFuture<Map<String, String>> ingest(
            @PathVariable String tenantId,
            @RequestHeader("X-API-Key") String apiKey,
            @Valid @RequestBody TelemetryEvent event) {
        guard.requireAccess(tenantId, apiKey);
        if (!tenantId.equals(event.tenantId())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "path tenant must match event tenant");
        }
        return publisher.publish(event).thenApply(ignored -> Map.of(
                "status", "accepted",
                "eventId", event.eventId().toString()));
    }

    @GetMapping("/devices/{deviceId}/latest")
    public TelemetryEvent latest(
            @PathVariable String tenantId,
            @PathVariable String deviceId,
            @RequestParam String metric,
            @RequestHeader("X-API-Key") String apiKey) {
        guard.requireAccess(tenantId, apiKey);
        return store.latest(tenantId, deviceId, metric)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "reading not found"));
    }
}
