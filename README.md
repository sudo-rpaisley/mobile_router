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

## Setup

Running the following script will ensure Python is available, create a
virtual environment and install any required packages. If everything is
already installed these steps will be skipped and the server will start
immediately.

```bash
./setup.sh
```

## Usage

Run the application directly with Python:

```bash
python app.py
```

The server listens on `0.0.0.0:8080`. Once running, navigate to
`http://localhost:8080` in a web browser to access the UI. From there you can
browse interfaces or open the **Red Team** page to try the network utilities.
