<#
POS-PAX Connectivity Diagnostic
- Checks TCP connectivity from this Windows PC to a PAX terminal.
- Optionally checks DNS + TCP connectivity to configured payment-host endpoints.
- Does NOT initiate payment transactions or send cardholder data.
- Confirm terminal protocol/port and payment processor endpoints with your POS/TSYS provider.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$PaxIP,

    [ValidateRange(1, 65535)]
    [int]$PaxPort = 10009,

    [string[]]$TsysHosts = @(),

    [ValidateRange(1, 65535)]
    [int]$TsysPort = 5003,

    [ValidateRange(250, 60000)]
    [int]$TimeoutMs = 3000,

    [string]$ReportPath = ".\pos-pax-diagnostic.csv"
)

$ErrorActionPreference = "Stop"
$results = [System.Collections.Generic.List[object]]::new()

function Test-TcpPort {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][int]$Timeout
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    $watch = [System.Diagnostics.Stopwatch]::StartNew()

    try {
        $task = $client.ConnectAsync($HostName, $Port)
        if (-not $task.Wait($Timeout)) {
            $watch.Stop()
            return [PSCustomObject]@{
                Time       = (Get-Date).ToString("o")
                Target     = $Name
                Host       = $HostName
                Port       = $Port
                Status     = "TIMEOUT"
                LatencyMs  = $watch.ElapsedMilliseconds
                Detail     = "No TCP connection within ${Timeout}ms; this alone does not prove a firewall block."
            }
        }

        # Throws if the asynchronous connection failed.
        $task.GetAwaiter().GetResult()
        $watch.Stop()

        return [PSCustomObject]@{
            Time       = (Get-Date).ToString("o")
            Target     = $Name
            Host       = $HostName
            Port       = $Port
            Status     = "PASS"
            LatencyMs  = $watch.ElapsedMilliseconds
            Detail     = "TCP handshake succeeded from this PC."
        }
    }
    catch {
        $watch.Stop()
        $message = $_.Exception.GetBaseException().Message
        return [PSCustomObject]@{
            Time       = (Get-Date).ToString("o")
            Target     = $Name
            Host       = $HostName
            Port       = $Port
            Status     = "FAIL"
            LatencyMs  = $watch.ElapsedMilliseconds
            Detail     = $message
        }
    }
    finally {
        $client.Dispose()
    }
}

Write-Host "`n=== POS -> PAX LAN test ===" -ForegroundColor Cyan
Write-Host "Target: ${PaxIP}:$PaxPort (confirm the actual port on the terminal first)"
$paxResult = Test-TcpPort -Name "POS_TO_PAX" -HostName $PaxIP -Port $PaxPort -Timeout $TimeoutMs
$results.Add($paxResult)
$paxResult | Format-List

if ($TsysHosts.Count -gt 0) {
    Write-Host "`n=== This PC -> configured payment endpoint test ===" -ForegroundColor Cyan
    Write-Host "These tests do NOT verify the PAX terminal's own Internet connection."
    foreach ($hostName in $TsysHosts) {
        try {
            $addresses = @(
                [System.Net.Dns]::GetHostAddresses($hostName) |
                ForEach-Object { $_.IPAddressToString }
            )
            $dnsResult = [PSCustomObject]@{
                Time      = (Get-Date).ToString("o")
                Target    = "PAYMENT_HOST_DNS"
                Host      = $hostName
                Port      = $TsysPort
                Status    = "PASS"
                LatencyMs = $null
                Detail    = ($addresses -join ", ")
            }
        }
        catch {
            $dnsResult = [PSCustomObject]@{
                Time      = (Get-Date).ToString("o")
                Target    = "PAYMENT_HOST_DNS"
                Host      = $hostName
                Port      = $TsysPort
                Status    = "FAIL"
                LatencyMs = $null
                Detail    = $_.Exception.GetBaseException().Message
            }
        }
        $results.Add($dnsResult)
        $dnsResult | Format-List

        if ($dnsResult.Status -eq "PASS") {
            $tcpResult = Test-TcpPort -Name "THIS_PC_TO_PAYMENT_HOST" -HostName $hostName -Port $TsysPort -Timeout $TimeoutMs
            $results.Add($tcpResult)
            $tcpResult | Format-List
        }
    }
}
else {
    Write-Host "`nSkipping payment-host tests. Add -TsysHosts with provider-confirmed hostnames to enable them." -ForegroundColor Yellow
}

$fullReportPath = [System.IO.Path]::GetFullPath($ReportPath)
$parent = Split-Path -Parent $fullReportPath
if ($parent -and -not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
$results | Export-Csv -Path $fullReportPath -NoTypeInformation -Encoding UTF8
Write-Host "`nCSV report saved to: $fullReportPath" -ForegroundColor Green
Write-Host "Reminder: TCP PASS confirms a TCP handshake only; it does not validate ECR protocol or payment processing."
