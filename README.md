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
  detail. Wireless interfaces can scan for nearby networks.
- **Red‑Team section** – a set of experimental tools including DoS and broadcast
  flood examples that operate on a selected interface.

## Setup

1. Install Python 3.10 or newer.
2. Create a virtual environment and activate it:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the application directly with Python:

```bash
python app.py
```

The server listens on `0.0.0.0:8080`. Once running, navigate to
`http://localhost:8080` in a web browser to access the UI. From there you can
browse interfaces or open the **Red Team** page to try the network utilities.
