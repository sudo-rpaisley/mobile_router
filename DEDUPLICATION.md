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

See `duplicate_code_report.md` for the review notes and `tools/report_duplicate_code.py` for the repeatable audit.

## Validation requirement

Every consolidation pass must compile and pass the complete pytest suite. The latest validated pass completed with 263 tests passed and 1 skipped.
