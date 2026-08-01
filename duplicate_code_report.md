# Duplicate Python code report

Scanned **72 Python files** and **558 non-trivial functions**.

Exact groups are high-confidence consolidation candidates. Structural groups only share control-flow shape and require manual review.

## Exact duplicate function bodies

No matches found.

## Structurally similar function bodies

### CSV export formatting

- `services/evidence.py` — `evidence_as_csv`
- `services/labs.py` — `handshake_records_csv`

Both construct CSV output, but they use different schemas. A generic table-to-CSV helper may be useful if more exports are added; merging these two alone would add abstraction without much reduction.

### Timestamped record snapshots

- `services/alerts.py` — `alert_records`
- `services/evidence.py` — `evidence_records`

Both copy locked records and add a formatted creation timestamp. This is a reasonable future shared service helper, but the domain-specific names remain clearer at their call sites.

### Job status routes

- `routes/diagnostic_routes.py` — `port_scan_job_status`
- `routes/interface_routes.py` — `scan_job_status`

The response flow is similar, but each route owns a different store, lock, snapshot function, and not-found message. A shared job-status response helper is possible, but should wait for a broader job-registry consolidation.

### Small parameter wrappers

- `scripts/train_controller.py` — `_controller` and `_engine`
- `scripts/interfaceTools.py` — `get_ipv4` and `get_ipv6`
- `scripts/capabilities.py` — `install_optional_package` and `install_required_package`

These pairs are intentionally retained. Each wrapper is only five lines and gives the caller a clear domain-specific operation; replacing them with generic parameter plumbing would not materially improve maintainability.

## Consolidations completed

- one shared context-refresh implementation now serves nine route registrars and three extracted support modules;
- Bluetooth helper-path discovery is implemented once;
- the BlueZ `busctl` availability probe is implemented once;
- network discovery modules share one MAC normaliser;
- Linux and Windows Wi-Fi scan parsers share one network-flush implementation.

## Remaining repeated source fragments

The report still identifies repeated setup declarations around the three state-aware support modules and repeated `subprocess.run` argument blocks. These are configuration or call-site similarities rather than duplicated implementations. Consolidating them would obscure local error handling and is not recommended without a larger dependency-injection or command-runner redesign.
