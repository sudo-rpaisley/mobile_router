# Mobile Router Web Interface

## Train Controller integration

Mobile Router includes a native, tabbed DCC-EX workspace at `/train-controller`.
It supports editable layout, controller, and engine rosters; setup and emergency
commands; bounded throttles; lights and horn functions; cancellable background
engine discovery with selective roster import; collapsible controller cards;
action history and Evidence Vault capture; and a persistent guided Training mode
with trophies. This is a clean-room Python implementation; it does not embed or
run the source Node app.

Hardware commands are disabled by default. After connecting Mobile Router to an
authorized model-railway network, enable them with:

```bash
export TRAIN_CONTROLLER_ENABLED=1
export TRAIN_CONTROLLER_PORT=2560       # optional
export TRAIN_CONTROLLER_TIMEOUT=2       # optional, seconds
```

State is stored in `instance/train_controller.json`. Raw DCC commands are never
accepted from the browser: supported commands are validated and generated in the
service module, and every hardware request requires authorization confirmation.

### Source compatibility inventory

The inspected source is an Express/EJS app that stores layouts, TCP controller
addresses, names, and engine rosters in `config.json`. It provides setup,
emergency stop, cab scanning (1–127), speed/direction, lights, horn, stop, inline
roster management, themes, status toasts, and controller-card collapse state. Its
runtime dependencies are Express and EJS; TCP uses Node's standard library. Its
two Mocha/Supertest tests cover layout naming and basic roster CRUD. The attached
checkout contains no license file or package license field, so no source code or
assets were copied.

The protocol behavior and roster model were suitable to reimplement. Express
routes, EJS templates, CSS/theme code, browser persistence, and unimplemented
“Red Team” buttons required replacement with Mobile Router's Flask, Jinja,
Bootstrap, capability, safety, history, and server-persistence patterns. The
DCC-EX TCP endpoint is LAN/hardware-specific, unauthenticated, unencrypted, and
can move physical trains; deploy only on an authorized trusted network. Node
dependencies are not added. Hardware behavior is mock-tested and never simulated
in the UI.

This project exposes a Flask based web UI for interacting with network interfaces and
running basic red team tools. It is intended for local use while experimenting with
wireless and wired adapters.

## Features

- **Network interface overview** – lists available interfaces (wired, wireless,
  loopback, etc.) and displays details such as MAC and IP addresses.
- **Dynamic updates** – interface information is polled in the background and the
  page automatically refreshes via WebSockets.
- **Per‑technology pages** – view adapters by type and inspect each interface in
  detail. Wireless interfaces can scan for nearby networks and Bluetooth
  adapters can discover nearby devices.
- **Beacon advertiser** – send spoofed 802.11 beacon frames with configurable
  MAC addresses and SSID to mimic other devices.
- **Red‑Team section** – a set of experimental tools including DoS and broadcast
  flood examples that operate on a selected interface.
- **Aireplay-ng integration** – optionally send deauth frames via the external
  `aireplay-ng` utility if it is installed.

## Setup

Running the following script will ensure Python 3 is available, install the
core packages from `requirements.txt` to a local `pylibs` directory and then
start the server. If `requirements.txt` is missing the dependency step will be
skipped.

```bash
./setup.sh
```

On OpenWRT the default firmware does not include build tools such as `gcc` or
header files. If `pip` fails with compilation errors, build the `pylibs`
directory on another machine and copy it to the router.

This project avoids packages that require native extensions. The network
interface code now uses built-in utilities instead of `psutil` so the
application can run on systems without a compiler.


## Platform Compatibility

The core web UI and Minecraft lab are designed to run on Windows, macOS, Linux,
and constrained Linux/OpenWRT devices such as the GL.iNet GL-AXT1800. Network
interface discovery uses built-in OS commands (`ip`, `ifconfig`, `ipconfig`) and
Python's socket APIs instead of native-extension inventory libraries.

Some radio-specific features still depend on platform tools or optional Python
packages being present. Bluetooth scanning can use `bleak` for BLE discovery and
falls back to Windows PowerShell or Linux `bluetoothctl` when available. Wi-Fi
network scanning can use `nmcli`/`iw`/`scapy` on Linux or `netsh`/`pywifi` on
Windows; deeper Linux packet capture still requires monitor-mode support and
`scapy`. Windows Wi-Fi connection management requires `pywifi`, and aireplay
deauthentication requires `aireplay-ng`. Optional Python packages live in
`requirements-optional.txt` so limited systems can install only the core web app.
When optional tools are missing, the core app should continue running while the
specific feature returns no results or an error message.

## Usage

Run the application directly with Python:

```bash
python app.py
```

### Running tests

Install the development dependencies, then invoke pytest through Python. Using
`python -m pytest` also works on Windows when the standalone `pytest` command is
not available on `PATH`.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

### Protecting Social Engineering profiles

The first visit to Mobile Router creates a local administrator account, and
authentication then protects the entire application. Administrators can create
additional role-based accounts from **System → User Management**. Each account
has its own private Social Engineering profiles, devices, and credentials.
Set `MOBILE_ROUTER_SECRET_KEY` to a long, stable random value so login sessions
remain valid across application restarts. New credential secrets are encrypted
in the browser with a user-supplied vault password before they are written to
the Git-ignored `data/runtime_state.json` file. Browser encryption requires a
secure context, such as `localhost` or HTTPS. The vault password is not stored
and cannot be recovered by the application.

The server listens on `0.0.0.0:8080`. Once running, navigate to
`http://localhost:8080` in a web browser to access the UI. From there you can
browse interfaces or open the **Red Team** page to try the network utilities.


### Windows Bluetooth phone helper

For the Bluetooth Phone Integration card on Windows, Mobile Router bundles a
lightweight helper at `helpers/windows/mobile-router-bluetooth-helper.py`. When
advertising is enabled, this helper starts a Mobile Router-owned Bluetooth LE
advertisement with an app-specific service UUID instead of opening Windows
Bluetooth settings. That keeps discovery scoped to Mobile Router and avoids
pairing the phone with the whole laptop or renaming the PC Bluetooth adapter.

The bundled helper is intentionally advertising-only: a phone needs a Mobile
Router companion/client app that knows the advertised service UUID to connect to
this app-scoped service. PBAP/MAP contact, call-history, and message sync still
require a full native helper executable when that is available. Put that
executable in one of these project folders before starting Mobile Router:

- `helpers/windows/mobile-router-bluetooth-helper.exe`
- `helpers/bluetooth/mobile-router-bluetooth-helper.exe`
- `bin/mobile-router-bluetooth-helper.exe`

If you prefer a system-wide install, put `mobile-router-bluetooth-helper.exe` on
`PATH`. Advanced deployments can still set `MOBILE_ROUTER_BLUETOOTH_HELPER` to a
full helper path. The app checks `MOBILE_ROUTER_BLUETOOTH_HELPER` first, then the project
folders, then `PATH` when deciding whether Windows Bluetooth sync is available;
the bundled Python helper is used as the fallback for app-scoped BLE advertising.

### OUI Database Location

The application looks for an `oui` directory containing `oui_db.csv`. By
default this folder lives in the project directory, but the lookup logic also
checks the parent directory and one level above that. This allows keeping the
OUI database outside the repository if desired. Lookups rely solely on this
offline database, including Bluetooth device vendor lookups.

To refresh the local database from the IEEE public OUI CSV listing, run:

```bash
python scripts/update_oui_db.py
```

The downloader writes a compact `prefix,vendor` CSV to `oui/oui_db.csv`, which
keeps runtime lookups offline after the database is downloaded.

### Offline automotive data and reports

Open **Tools → Automotive** to import VIN/WMI and diagnostic trouble-code data,
look up VINs and codes without an internet query, save vehicles, and create work
reports. Automotive records are stored separately in
`data/automotive.sqlite3`; override that location with
`MOBILE_ROUTER_AUTOMOTIVE_DB` when removable or encrypted storage is preferred.

VIN imports are CSV files with `wmi`, `manufacturer`, and `country` columns.
Additional columns are retained and returned by the decoder. Code imports can
be CSV (`code`, `description`, and optional `make`), plain text, or a searchable
PDF. Image-only/scanned PDFs must be OCRed first. A direct HTTP(S) link can be
supplied as an explicit import action, but all later lookups use the saved local
copy. Imports are capped at 25 MB.

A small bundled WMI baseline provides useful first-run offline results before a
larger database is imported; it currently includes Saab passenger vehicles
(`YS3`). Imported rows extend the baseline and take precedence for matching WMIs.

Reports can associate error codes and make-specific translations with a saved
vehicle, record odometer, technician, work performed, and notes, and export as
JSON, CSV, or PDF. The reader panel documents the intended future OBD-II adapter
support: USB serial and Bluetooth Classic first, with BLE and Wi-Fi connectors
as later additions. Manual lookups and reports do not require reader hardware.

Imported files are limited to 25 MB and tracked by SHA-256 checksum so accidental
duplicate imports can be rejected. Direct-link imports reject loopback, private,
link-local, and reserved destinations, including redirect targets. Saved reports
snapshot the code translations used at creation time, so later database updates
do not rewrite historical workshop records. Vehicles can be edited or archived
from their detail page.

Each saved vehicle keeps one canonical VIN and can also retain typed chassis,
frame, body, engine, transmission, registration, fleet, manufacturer, and legacy
identifiers. Control modules can be recorded with address, manufacturer, part,
hardware, software, serial, calibration ID, CVN, notes, and the VIN reported by
that module. Module VINs are compared with the canonical VIN and mismatches are
flagged without replacing the saved vehicle identity.

Database uploads are staged before they affect live lookups. The review page
shows every parsed record and lets an administrator exclude incorrect rows,
approve the selected records in one transaction, or discard the staged import.
