# Automotive implementation roadmap

The in-app **System → Roadmap** page is the canonical status list. This document
records the intended implementation order and acceptance boundaries for the
larger automotive milestones.

## 1. Reader-independent diagnostic foundation

- Build an ELM327-style simulated reader before physical hardware is available.
- Define one transport contract for simulation, USB serial, Bluetooth Classic,
  adapter-specific BLE, and Wi-Fi TCP readers.
- Persist immutable diagnostic sessions separately from editable workshop
  reports, including adapter identity, protocol, raw responses, categorized
  DTCs, freeze-frame data, readiness, PID samples, warnings, and timestamps.
- Add a diagnostics workspace for connection state, scans, saved sessions, and
  report creation.

The SQLite schema and manual/simulator-ready service methods can already store
and display diagnostic-session records. The canonical **Immutable diagnostic
sessions** milestone remains open until the application enforces immutability
through the complete create/view/report workflow and the simulator exercises
that boundary. Transport connectors and the live diagnostics workspace also
remain open.

- Extend the saved vehicle identity inventory with canonical VIN, chassis/frame,
  body, engine and transmission serials, registration/fleet identifiers, and
  per-ECU part, serial, hardware, software, calibration, CVN, and reported-VIN
  observations. A mismatching module VIN must be flagged, never auto-promoted.

## 2. Hardware transports

- Implement USB serial ELM327/STN discovery, bounded initialization, baud and
  protocol detection, cancellation, and raw exchange capture first.
- Add Bluetooth Classic RFCOMM/SPP and Wi-Fi TCP using the same session layer.
- Add BLE through explicit adapter/GATT plugins; do not assume generic serial
  framing across BLE readers.
- Gate DTC clearing behind a saved pre-clear scan, explicit confirmation,
  readiness-reset guidance, an audit event, and an automatic post-clear scan.
- Stored module-value snapshots and staged parameter changes are now supported.
  Applying a change is intentionally simulator-only until a hardware transport
  implements compatibility checks, pre-write backup, verified write, read-back,
  rollback guidance, and an immutable audit record.

## 3. Offline data quality

- Add a versioned adapter for an authoritative downloadable full VIN dataset;
  VIN decoding must remain local after installation.
- Replace destructive `(code, make)` DTC replacement with versioned definitions
  that retain source, page, language, vehicle applicability, module, confidence,
  and user translations.
- Retain uploaded PDF originals and page-level extraction provenance, add a
  correction/review workflow, and optionally stage OCR results for scanned PDFs.
- A first conflict-review workflow now allows administrators to supersede a
  definition or adjust its priority without treating conflicts as duplicates.

## 4. Workshop records

- Replace the minimal PDF with Unicode, wrapping, pagination, tables, branding,
  dates, diagnostic-session summaries, before/after results, parts, labor,
  recommendations, attachments, and signature fields.
- Add draft/final/amended/void report revisions and prevent finalized records
  from changing silently.
- Add full automotive backup and validated restore for imports, vehicles,
  diagnostic sessions, reports, and retained source documents.

## 5. Verification

- Add service, route, browser, migration, rollback, security, simulated-reader,
  report-download, accessibility, and mobile-layout coverage.
- Exercise real transports only against explicitly selected authorized vehicles
  and keep arbitrary raw diagnostic commands out of browser-facing endpoints.
