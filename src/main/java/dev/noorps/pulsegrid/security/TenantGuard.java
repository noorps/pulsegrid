package dev.noorps.pulsegrid.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Map;
import java.util.stream.Collectors;

@Component
public class TenantGuard {
    private final Map<String, String> keysByTenant;

    public TenantGuard(@Value("${pulsegrid.api-keys}") String configuredKeys) {
        this.keysByTenant = Arrays.stream(configuredKeys.split(","))
                .map(pair -> pair.split(":", 2))
                .filter(pair -> pair.length == 2)
                .collect(Collectors.toUnmodifiableMap(pair -> pair[0], pair -> pair[1]));
    }

    public void requireAccess(String tenantId, String suppliedKey) {
        String expected = keysByTenant.get(tenantId);
        boolean matches = expected != null && suppliedKey != null && MessageDigest.isEqual(
                expected.getBytes(StandardCharsets.UTF_8),
                suppliedKey.getBytes(StandardCharsets.UTF_8));
        if (!matches) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "invalid tenant credentials");
        }
    }
}
