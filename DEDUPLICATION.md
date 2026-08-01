# Deduplication work branch

This branch is based on `agent/refactor-application-structure` and is intentionally separate so the consolidation work can be reviewed and applied later without blocking the main structural refactor.

## Completed consolidations

- Replaced twelve copied context-refresh decorators with `app_support.context`.
- Replaced two copies of Bluetooth helper-path discovery with `scripts.bluetooth_support.project_helper_candidates`.
- Replaced three copies of the BlueZ `busctl` availability probe with `scripts.bluetooth_support.bluez_service_available`.
- Replaced two private network MAC normalisers with `scripts.network.common.normalize_mac`.
- Replaced the duplicated Linux/Windows Wi-Fi scan flush functions with one shared `_flush_current_network` implementation.
- Preserved existing private names as aliases where callers or tests may rely on them.

## Audit result

The corrected AST audit scanned 72 Python files and 558 non-trivial functions. It found no remaining exact duplicate function bodies.

The remaining similarities are deliberately documented rather than automatically merged. They include CSV formatting, locked timestamped record snapshots, job-status routes, and several tiny domain-specific wrappers. These share control-flow shape but have different schemas, stores, messages, or semantic names; consolidating them now would add abstraction with little maintainability benefit.

A second-pass audit also ran Ruff, Vulture, and Radon against the pull-request merge result. Vulture found no likely unused functions at 80% confidence. The complete test suite still passed with 263 tests passed and 1 skipped.

See `duplicate_code_report.md` for the duplicate review notes and `tools/report_duplicate_code.py` for the repeatable audit.

## Further cleanup priorities

### 1. Replace dynamic namespace injection

The largest remaining architectural issue is the compatibility layer built around `globals().update(context_provider())`. It preserves legacy monkey-patching, but it prevents static analysis from resolving dependencies. Ruff consequently reports more than one thousand undefined-name findings inside extracted route and support modules, even though those names are supplied at runtime.

Replace it gradually with an explicit application dependency object or small typed context classes. Route registrars and support modules should receive only the dependencies they use. This will also allow many compatibility imports in `app.py` to be removed safely.

### 2. Split the highest-complexity functions

The most valuable targets are:

- `services/social_profile/validation.py::validate_profile` — split email, social-link, metadata, date, and custom-field parsing into focused validators.
- `services/wireless_clients.py::merge_network_clients` — split cache loading, observation merging, inventory enrichment, display decoration, and visible/disappeared partitioning.
- `app_support/client_intelligence.py` — split name resolution, health calculation, profile construction, metadata updates, and relationship mapping.
- `services/inventory.py` — split open-port recording and import validation/merging.
- `services/device_intel.py::infer_device_role` — move evidence rules into small ordered classifiers.

These are behaviour-sensitive changes and should be applied one function family at a time with focused tests.

### 3. Split the remaining monolithic compatibility modules

Radon marks these as the weakest-maintainability files:

- `app.py` — continue extracting runtime-state ownership, scan-job coordination, Bluetooth history, service discovery, and authentication helpers.
- `scripts/interfaceTools.py` — divide interface enumeration, address handling, Bluetooth discovery, wireless operations, and platform command adapters.
- `scripts/wifi/utils.py` — divide shared Wi-Fi models/state, Linux parsers, Windows parsers, scan backends, and grouping/presentation helpers.

The compatibility filenames can remain as thin re-export façades until callers migrate.

### 4. Narrow broad exception handling

The audit found 43 broad `except Exception` cases. Some are appropriate at process or background-worker boundaries, but inner parsing and command helpers should catch specific exceptions, preserve useful failure details, and log unexpected errors before returning fallbacks.

### 5. Make compatibility exports explicit

Ruff reports around 60 apparently unused imports, mostly because `app.py` deliberately exposes names for extracted modules and tests. Replace implicit exposure with documented compatibility façades and sorted `__all__` declarations. Genuine unused imports can then be removed without breaking monkey-patching.

### 6. Standardise legacy naming

New modules use snake_case, while compatibility names such as `networkTechnologies`, `interfaceTools`, and `networkScan` remain. Keep import-compatible aliases temporarily, but make all internal code use the snake_case names and document eventual removal of the legacy aliases.

### 7. Introduce static checks incrementally

Ruff should be added to normal CI only after the dependency-injection migration begins. Start with safe formatting and modernisation rules, then enable undefined-name and unused-import checks module by module as dynamic context injection is removed.

## Validation requirement

Every cleanup pass must compile and pass the complete pytest suite. The latest validated audit completed with 263 tests passed and 1 skipped.
