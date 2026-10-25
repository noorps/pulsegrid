param([ValidateRange(1, 120)][int]$Minutes = 30)

Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public static class PulseGridPowerRequest {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint flags);
}
'@

$deadline = (Get-Date).AddMinutes($Minutes)
try {
    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED; no persistent power-plan changes.
    if ([PulseGridPowerRequest]::SetThreadExecutionState([uint32]2147483649) -eq 0) {
        throw 'Could not request temporary idle-sleep prevention'
    }
    Write-Host "Preventing automatic idle sleep for up to $Minutes minutes. Press Ctrl+C to stop."
    while ((Get-Date) -lt $deadline) { Start-Sleep -Seconds 10 }
} finally {
    [void][PulseGridPowerRequest]::SetThreadExecutionState([uint32]2147483648)
}
