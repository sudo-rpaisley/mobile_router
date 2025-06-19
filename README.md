# Mobile Router Web Interface

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

Running the following script will ensure Python 3 is available, install any
required packages to a local `pylibs` directory and then start the server.
If `requirements.txt` is missing the dependency step will be skipped.

```bash
./setup.sh
```

On OpenWRT the default firmware does not include build tools such as `gcc` or
header files. If `pip` fails with compilation errors, build the `pylibs`
directory on another machine and copy it to the router.

This project avoids packages that require native extensions. The network
interface code now uses built-in utilities instead of `psutil` so the
application can run on systems without a compiler.

## Usage

Run the application directly with Python:

```bash
python app.py
```

The server listens on `0.0.0.0:8080`. Once running, navigate to
`http://localhost:8080` in a web browser to access the UI. From there you can
browse interfaces or open the **Red Team** page to try the network utilities.

### OUI Database Location

The application looks for an `oui` directory containing `oui_db.csv`. By
default this folder lives in the project directory, but the lookup logic now
also checks the parent directory **and** one level above that. This allows
keeping the OUI database outside the repository if desired.
