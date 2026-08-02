# Duplicate Python code report

Scanned **78 Python files** and **691 non-trivial functions**.

Exact groups are high-confidence consolidation candidates. Structural groups only share control-flow shape and require manual review.

## Exact duplicate function bodies

No matches found.

## Structurally similar function bodies

### Structural group: 2 functions, 40 total lines

- `routes/social_profile_identity.py:156-175` — `delete_identity_document` (20 lines)
- `routes/social_profile_identity.py:230-249` — `delete_profile_signature` (20 lines)

### Structural group: 5 functions, 30 total lines

- `routes/core_routes.py:92-97` — `red_team` (6 lines)
- `routes/core_routes.py:280-285` — `network_scan` (6 lines)
- `routes/core_routes.py:288-293` — `diagnostics_page` (6 lines)
- `routes/core_routes.py:296-301` — `service_discovery_page` (6 lines)
- `routes/core_routes.py:304-309` — `advanced_diagnostics_page` (6 lines)

### Structural group: 2 functions, 26 total lines

- `routes/social_profile_identity.py:136-148` — `identity_document_image` (13 lines)
- `routes/social_profile_identity.py:210-222` — `profile_signature_image` (13 lines)

### Structural group: 2 functions, 23 total lines

- `services/evidence.py:64-79` — `evidence_as_csv` (16 lines)
- `services/labs.py:263-269` — `handshake_records_csv` (7 lines)

### Structural group: 3 functions, 15 total lines

- `services/automotive.py:732-736` — `delete_vehicle_identifier` (5 lines)
- `services/automotive.py:769-773` — `delete_vehicle_module` (5 lines)
- `services/automotive.py:881-885` — `delete_vehicle_person` (5 lines)

### Structural group: 2 functions, 14 total lines

- `services/alerts.py:65-71` — `alert_records` (7 lines)
- `services/evidence.py:10-16` — `evidence_records` (7 lines)

### Structural group: 2 functions, 12 total lines

- `routes/diagnostic_routes.py:64-69` — `port_scan_job_status` (6 lines)
- `routes/interface_routes.py:178-183` — `scan_job_status` (6 lines)

### Structural group: 2 functions, 10 total lines

- `scripts/train_controller.py:238-242` — `_controller` (5 lines)
- `scripts/train_controller.py:245-249` — `_engine` (5 lines)

### Structural group: 2 functions, 10 total lines

- `scripts/interfaceTools.py:182-186` — `get_ipv4` (5 lines)
- `scripts/interfaceTools.py:188-192` — `get_ipv6` (5 lines)

### Structural group: 2 functions, 10 total lines

- `scripts/capabilities.py:318-322` — `install_optional_package` (5 lines)
- `scripts/capabilities.py:325-329` — `install_required_package` (5 lines)

### Structural group: 2 functions, 10 total lines

- `services/automotive.py:707-711` — `vehicle_identifiers` (5 lines)
- `services/automotive.py:858-862` — `vehicle_people` (5 lines)

## Repeated six-line source blocks

### Block 1: 3 occurrences

- `scripts/bluetooth_phone.py:272`
- `scripts/bluetooth_phone.py:428`
- `scripts/bluetooth_phone_bluez.py:95`

```python
capture_output=True,
text=True,
timeout=timeout,
check=False,
)
except (OSError, subprocess.TimeoutExpired) as exc:
```

### Block 2: 2 occurrences

- `app_support/client_intelligence.py:12`
- `app_support/passive_monitoring.py:12`

```python


_refresh_context = context_refresher(globals(), lambda: _CONTEXT_PROVIDER)


@_refresh_context
```

### Block 3: 2 occurrences

- `app_support/client_intelligence.py:2`
- `app_support/passive_monitoring.py:2`

```python

from app_support.context import context_refresher


_CONTEXT_PROVIDER = None

```

### Block 4: 2 occurrences

- `app_support/client_intelligence.py:11`
- `app_support/passive_monitoring.py:11`

```python
_CONTEXT_PROVIDER = provider


_refresh_context = context_refresher(globals(), lambda: _CONTEXT_PROVIDER)


```

### Block 5: 2 occurrences

- `app_support/bluetooth_actions.py:56`
- `scripts/bluetooth_phone.py:388`

```python
capture_output=True,
text=True,
timeout=timeout,
check=False,
)
if result.returncode != 0:
```

### Block 6: 2 occurrences

- `scripts/interfaceTools.py:689`
- `scripts/network/discovery.py:70`

```python
continue
seen.add(key)
unique.append(device)
return unique


```

### Block 7: 2 occurrences

- `app_support/client_intelligence.py:3`
- `app_support/passive_monitoring.py:3`

```python
from app_support.context import context_refresher


_CONTEXT_PROVIDER = None


```

### Block 8: 2 occurrences

- `app_support/client_intelligence.py:10`
- `app_support/passive_monitoring.py:10`

```python
global _CONTEXT_PROVIDER
_CONTEXT_PROVIDER = provider


_refresh_context = context_refresher(globals(), lambda: _CONTEXT_PROVIDER)

```

### Block 9: 2 occurrences

- `scripts/interfaceTools.py:688`
- `scripts/network/discovery.py:69`

```python
if not key or key in seen:
continue
seen.add(key)
unique.append(device)
return unique

```
