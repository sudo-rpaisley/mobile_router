# Deduplication and cleanup status

The application-structure refactor and shared-code consolidation are now present on `main`. This document records the current architecture, completed work, remaining cleanup priorities, and the validation required for future changes.

## Shared-code consolidations completed

- Replaced twelve copied context-refresh implementations with shared helpers in `app_support.context`.
- Replaced duplicate Bluetooth helper-path discovery with `scripts.bluetooth_support.project_helper_candidates`.
- Replaced duplicate BlueZ `busctl` availability probes with `scripts.bluetooth_support.bluez_service_available`.
- Replaced private network MAC normalisers with `scripts.network.common.normalize_mac` and the shared application identifier helpers.
- Replaced the duplicated Linux and Windows Wi-Fi scan flush functions with one shared implementation.
- Preserved compatibility aliases where existing callers or tests still rely on them.

## Complexity cleanup completed

### Social profile validation

`services/social_profile/validation.py::validate_profile` coordinates focused helpers for email records, social links, recovery data, phone metadata, profile dates and status, custom fields, and legacy platform URLs. The public signature and persisted profile shape remain compatible.

### Wireless client merging

`services/wireless_clients.py::merge_network_clients` coordinates cache loading, current observation merging, inventory matching and enrichment, display/state decoration, and visible/disappeared partitioning. The public signature, cache format, and response shape remain compatible.

### Client service modules

`app_support/client_services.py` is a small compatibility façade over:

- `app_support/client_service_dependencies.py`;
- `app_support/client_service_http.py`;
- `app_support/client_service_scheduling.py`.

This separates HTTP inspection and banner work from scheduled checks and watched-client alerts while retaining the established import surface.

### Client intelligence modules

`app_support/client_intelligence.py` is now a small compatibility façade over:

- `app_support/client_intelligence_dependencies.py`;
- `app_support/client_identity.py`;
- `app_support/client_metadata.py`;
- `app_support/client_profile.py`.

Identity discovery, user-maintained metadata, baselines, health, timelines, exports, and relationship maps are separated while all established application imports remain available.

### Passive monitoring modules

`app_support/passive_monitoring.py` is now a small compatibility façade over:

- `app_support/passive_monitoring_dependencies.py`;
- `app_support/passive_analytics.py`;
- `app_support/passive_monitor_control.py`;
- `app_support/comprehensive_scan.py`.

Passive observation analytics, worker lifecycle, and combined network discovery are separated without changing the public support API.

### Social profile services

`services/social_profiles.py` remains a small compatibility façade over the focused validation, storage, relationship, credential, and device modules. Automotive identity documents and signatures are retained during normalization, profile merging, and deletion cleanup.

## Explicit dependency migration

`app_support.context` provides `DependencyProxy` and `dependency_proxy`, which resolve only an explicit allow-list from the application provider without copying the application namespace into another module.

The following areas have been migrated away from dynamic namespace mutation:

- `app_support.client_services` and its focused implementation modules;
- `app_support.client_intelligence` and its focused implementation modules;
- `app_support.passive_monitoring` and its focused implementation modules;
- `routes.core_routes`.

Request-time helper replacement remains supported through explicit provider resolution, preserving the existing tests and compatibility callers without mutating module globals. Architecture tests prevent migrated modules from returning to `globals().update`, `bind_context`, or `context_refresher`.

## Current audit result

The latest validated audit scanned **86 Python files** and **696 non-trivial functions**. It found **no exact duplicate function bodies**.

The former repeated context-refresh setup in client intelligence and passive monitoring is gone. Remaining matches are structural similarities rather than interchangeable implementations. They include small page-rendering routes, explicit dependency-provider setup, image and deletion handlers with different storage semantics, CSV exports with different schemas, locked record snapshots, job-status handlers, small automotive domain wrappers, subprocess call syntax, and unique-list filtering.

The generated snapshot is stored in `duplicate_code_report.md`; every pull request also uploads an operating-system-specific report artifact.

## Remaining cleanup priorities

### 1. Continue explicit dependency migration

Continue through the client, diagnostic, interface, laboratory, and social route families. Each migration should use a narrow dependency allow-list and retain dynamic resolution only where compatibility tests require it.

### 2. Continue complexity reduction

The next valuable function families are:

- open-port recording and import validation in `services/inventory.py`;
- device-role evidence rules in `services/device_intel.py::infer_device_role`;
- platform parsing and command execution in `scripts/interfaceTools.py` and `scripts/wifi/utils.py`;
- remaining large route handlers after their dependency boundaries are explicit.

### 3. Reduce remaining application ownership

Continue moving runtime-state ownership, scan-job coordination, Bluetooth history, authentication support, and service-discovery coordination out of `app.py`. Compatibility names can remain as explicit re-exports until callers migrate.

### 4. Narrow exception handling

Broad exception handling should remain only at process, worker, or request boundaries where a final safety net is intentional. Inner parsers and command helpers should catch specific failures and retain useful diagnostic detail.

### 5. Introduce static checks incrementally

Enable Ruff rules module by module as namespace injection is removed. Begin with migrated modules, then add unused-import and undefined-name enforcement once dependencies are explicit.

## Merge and regression safeguards

The test suite now enforces that:

- `app.py` remains below the composition-entry-point size boundary;
- `app.py` contains no direct `@app.route` handlers;
- expected extracted route registrars are called exactly once;
- registered URL/method combinations are unique;
- importing the application succeeds;
- compatibility façades and focused modules remain within their size boundaries;
- migrated support families do not use namespace mutation helpers.

GitHub Actions validates the repository on both Linux and Windows.

## Validation requirement

Every cleanup pass must compile, import the application, produce a duplicate audit with no exact duplicate bodies, and pass the complete pytest suite on both supported CI operating systems. The latest cross-platform validation completed with **314 tests passed and 1 skipped** on both Linux and Windows.
