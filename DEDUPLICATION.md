# Deduplication and cleanup work branch

This branch is based on `agent/refactor-application-structure` and remains separate so the consolidation and cleanup work can be reviewed or applied later without blocking the main structural refactor.

## Shared-code consolidations completed

- Replaced twelve copied context-refresh implementations with shared helpers in `app_support.context`.
- Replaced two copies of Bluetooth helper-path discovery with `scripts.bluetooth_support.project_helper_candidates`.
- Replaced three copies of the BlueZ `busctl` availability probe with `scripts.bluetooth_support.bluez_service_available`.
- Replaced two private network MAC normalisers with `scripts.network.common.normalize_mac`.
- Replaced the duplicated Linux and Windows Wi-Fi scan flush functions with one shared `_flush_current_network` implementation.
- Preserved private compatibility aliases where existing callers or tests may still rely on them.

## Complexity cleanup completed

### Social profile validation

`services/social_profile/validation.py::validate_profile` now coordinates focused helpers for:

- email parsing and legacy-email compatibility;
- social-link and recovery-data parsing;
- phone metadata;
- profile status, tags, review dates, and retention data;
- custom fields and legacy platform URLs.

The public function signature and persisted profile shape are unchanged.

### Wireless client merging

`services/wireless_clients.py::merge_network_clients` now coordinates separate stages for:

- loading the network-scoped cache;
- merging current wireless observations;
- matching and enriching from inventory records;
- decorating client state and labels;
- partitioning visible and disappeared clients.

The public signature, cache format, and network response shape are unchanged.

### Client service modules

The former `app_support/client_services.py` implementation is now a small compatibility façade over:

- `app_support/client_service_dependencies.py`;
- `app_support/client_service_http.py`;
- `app_support/client_service_scheduling.py`.

This separates HTTP inspection and banner work from scheduled checks and watched-client alerts while preserving the original import surface.

## Explicit dependency migration

`app_support.context` now provides a non-mutating `DependencyProxy` and `dependency_proxy` helper. These resolve only an explicit allow-list of dependencies from the application provider and do not copy application globals into another module.

The following areas have been migrated away from dynamic namespace mutation:

- `app_support.client_services` and its focused implementation modules;
- `routes.core_routes`.

The dynamic provider remains deliberate for now so existing tests and compatibility callers can still monkey-patch application-owned functions. New architecture tests prevent these migrated modules from returning to `globals().update`, `bind_context`, or `context_refresher`.

The core route migration also replaced a broad contact-form `except Exception` handler with specific `OSError`, `TypeError`, and `ValueError` handling.

## Final audit result

The repeatable AST audit scanned **75 Python files** and **586 non-trivial functions**. It found **no exact duplicate function bodies**.

The remaining matches are structural similarities rather than duplicated implementations. They include small page-rendering routes, CSV exports with different schemas, locked record snapshots, job-status handlers, tiny domain wrappers, subprocess call syntax, and unique-list filtering. They remain separate where a generic abstraction would add more indirection than maintainability.

The audit still highlights the same legacy context-refresh setup in:

- `app_support/client_intelligence.py`;
- `app_support/passive_monitoring.py`.

See `duplicate_code_report.md` for the generated report and `tools/report_duplicate_code.py` for the repeatable audit.

## Remaining cleanup priorities

### 1. Continue explicit dependency migration

Migrate `client_intelligence.py` and `passive_monitoring.py` next, followed by the client, diagnostic, interface, laboratory, and social route families. Each migration should use a narrow dependency allow-list and retain dynamic resolution only where compatibility tests require it.

### 2. Continue complexity reduction

The next valuable function families are:

- client name resolution, health calculation, and relationship mapping in `app_support/client_intelligence.py`;
- open-port recording and import validation in `services/inventory.py`;
- evidence rules in `services/device_intel.py::infer_device_role`;
- platform parsing and command execution in `scripts/interfaceTools.py` and `scripts/wifi/utils.py`.

### 3. Reduce remaining application ownership

Continue moving runtime-state ownership, scan-job coordination, Bluetooth history, authentication support, and service-discovery coordination out of `app.py`. Compatibility names can remain as explicit re-exports until callers migrate.

### 4. Narrow exception handling

Broad exception handling should remain only at process, worker, or request boundaries where a final safety net is intentional. Inner parsers and command helpers should catch specific failures and retain useful diagnostic detail.

### 5. Introduce static checks incrementally

Enable Ruff rules module by module as namespace injection is removed. Begin with the migrated modules, then add unused-import and undefined-name enforcement only after their dependencies are explicit.

## Validation requirement

Every cleanup pass must compile, produce a clean duplicate audit, and pass the complete pytest suite. The latest validated pull-request merge result completed with **264 tests passed and 1 skipped**.
