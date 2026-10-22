# POS–PAX Connectivity Diagnostic (Windows PowerShell)

This small diagnostic tool checks basic TCP reachability from the Windows PC running the Web POS to a PAX terminal. It can optionally test DNS resolution and TCP reachability to payment-host endpoints that your provider has confirmed.

## Important

- PAX POSLink commonly uses TCP port `10009`, but the actual terminal model, application, and communication mode may differ. Verify the configured ECR port/protocol on the terminal or with your POS/TSYS provider.
- Some TSYS/Vital configurations use `ssl2.vitalps.net:5003`; this is not universal. Use only the endpoint/port confirmed for your merchant configuration.
- Payment-host tests run from **this Windows PC**, not from the PAX terminal. They do not prove the terminal itself has Internet access.
- A TCP failure does not by itself prove a firewall is blocking the port. The service may be disabled, the IP/port may be wrong, or routing/VLAN rules may prevent access.
- The tool does not initiate payments and does not collect cardholder data.

## Requirements

- Windows PowerShell 5.1 or PowerShell 7
- Network access from the PC to the PAX terminal
- No third-party modules required

## Run the PAX LAN test

Open PowerShell in this folder and run:

```powershell
.\Test-PosPax.ps1 -PaxIP "192.168.1.50"
```

Replace `192.168.1.50` with the terminal's actual IP address.

If the terminal is configured to use a different port:

```powershell
.\Test-PosPax.ps1 -PaxIP "192.168.1.50" -PaxPort 10009
```

## Optional: test a provider-confirmed payment endpoint

For a TSYS/Vital setup where your provider confirms these values:

```powershell
.\Test-PosPax.ps1 `
  -PaxIP "192.168.1.50" `
  -TsysHosts "ssl2.vitalps.net","ssl3.vitalps.net" `
  -TsysPort 5003
```

Do not assume these hosts/port are correct for every TSYS deployment. Confirm them with your payment processor or terminal reseller before using them in production.

## Output

The tool prints each test result and writes a CSV report to:

`.\pos-pax-diagnostic.csv`

Status meanings:
- `PASS`: TCP handshake succeeded.
- `FAIL`: connection attempt failed; read the error details.
- `TIMEOUT`: no connection was established before the timeout.

## Understanding the two network paths

1. **POS PC → PAX terminal (LAN):** check terminal IP, configured ECR port, same/allowed VLAN, routing, terminal app state, and host/network firewalls.
2. **PAX terminal → TSYS/payment host (Internet):** this requires testing on the terminal or using provider-supported diagnostics/logs. The optional tests in this script only test the Windows PC's outbound path.

For a browser-based Web POS, browser JavaScript generally cannot open arbitrary raw TCP sockets. A local agent/service is a possible next step if you need the Web POS page to display these diagnostics; secure it to localhost and restrict allowed hosts/ports.

## References

- PAR documentation — suggested default ports lists PAX POSLink `10009`: https://product-docs.partech.com/docs/par-pos/system-requirements/suggested-default-ports
- PAR documentation — PAX POSLink port is the TCP port the device listens on: https://product-docs.partech.com/docs/par-pos/user-guides/Integration-Settings-Portal-User-Guide/payment-device
- Card Defender network requirements — lists TSYS/Vital endpoints and port `5003` for that deployment (third-party deployment guidance, not a universal TSYS specification): https://helpdesk.card-defender.com/support/solutions/articles/67000674804-card-defender-network-requirements
- Global Payments / Heartland developer resources — PAX integration and connection configuration: https://developer.globalpayments.com/heartland/resources/knowledge-center/in-person-payments

Always follow the port list and network policy provided for your specific merchant deployment.
