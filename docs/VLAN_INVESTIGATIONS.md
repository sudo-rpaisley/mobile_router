# VLAN Investigations

Mobile Router provides a VLAN and routed-network workspace at `/vlans`. The
feature stores definitions in `instance/vlan_investigations.sqlite3` and makes a
known network label visible throughout the device inventory and device pages.

## VLAN labels

When an 802.1Q tag is known, the application displays a prominent label such as:

```text
VLAN 20 · Users
```

When only a routed subnet is known, the label uses the network name and CIDR
without claiming that a tag was observed. Device assignment uses the
most-specific matching saved subnet. An explicit device assignment retained from
an investigation or infrastructure import takes precedence over inference.

## Visibility levels

A routed investigation can identify IP reachability, route context, reverse DNS,
and selected listening TCP services when the firewall permits them. It cannot
normally see ARP, DHCP broadcasts, mDNS, SSDP, or other link-local/layer-2
activity in another VLAN.

Use one of these sources for deeper visibility:

- read-only pfSense or infrastructure records;
- a Mobile Router host with a local address in the VLAN;
- the restricted remote probe in `scripts/vlan_probe_agent.py`.

The UI labels every result as routed, infrastructure, or local layer-2 evidence.

## Safety limits

- IPv4 CIDRs are supported in the first release.
- Saved VLAN subnets and explicit tags cannot overlap or conflict.
- Routed investigations are limited to 1,024 usable addresses.
- Optional service checks are limited to 16 selected TCP ports.
- Infrastructure responses/imports are limited to 2 MiB.
- Remote-probe submissions are limited to 1 MiB and 4,096 device records.
- Definitions, scans, integrations, probes, and segmentation tests require an
  administrator, a valid CSRF token, and explicit scan authorisation.

## pfSense integration

The pfSense adapter is deliberately read-only and configurable because endpoint
paths vary between API packages and deployments. The VLAN page accepts a JSON
export containing `vlans` or `interfaces`, plus optional `leases`,
`dhcp_leases`, `arp`, `arp_table`, or `devices` collections.

A live integration stores only:

- HTTPS base URL;
- endpoint paths;
- authentication-header name and prefix;
- environment-variable reference;
- TLS verification preference.

The token itself remains in the environment, for example:

```bash
export MOBILE_ROUTER_PFSENSE_TOKEN='replace-with-read-only-token'
python app.py
```

TLS certificate verification is enabled by default. Disabling verification is
an explicit administrator choice intended only for a known local appliance with
a self-signed certificate.

## Remote probe

Create a probe from a VLAN detail page, then set the named secret environment
variable on both the main application host and the probe host:

```bash
export MOBILE_ROUTER_VLAN50_PROBE_KEY='replace-with-long-random-secret'
```

Run the dependency-free agent from inside the VLAN:

```bash
python scripts/vlan_probe_agent.py \
  --server https://mobile-router.example.internal \
  --probe-id PROBE_ID_FROM_CONFIG \
  --subnet 10.50.0.0/24 \
  --secret-env MOBILE_ROUTER_VLAN50_PROBE_KEY
```

Use `--dry-run` to inspect the payload without submitting it. The agent performs
only a bounded ping sweep and reads the local neighbour table. It does not
capture payloads, scan ports, attempt authentication, or alter endpoints.

Every submission includes:

- HMAC-SHA256 over the exact request body, timestamp, and nonce;
- a timestamp accepted only within five minutes;
- a one-time nonce rejected on replay;
- the configured probe identity and VLAN association.

The application stores the environment-variable name but never exports or logs
the secret value.

## Segmentation matrix

A segmentation expectation records:

- source VLAN;
- optional destination VLAN;
- destination host;
- TCP, UDP, or ICMP;
- destination port where applicable;
- expected `allow` or `block` result;
- optional source remote probe.

Main-host TCP and ICMP tests are clearly marked as a routed perspective. A saved
source address may bind the TCP socket when the Mobile Router host actually has
that address. UDP is reported as indeterminate from the main host unless a
protocol-specific or remote-probe observation is supplied. A result is flagged
when observed access differs from the saved expectation.
