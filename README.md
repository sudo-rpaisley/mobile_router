# Mobile Router

This project is a small Flask application for interacting with network interfaces. It now supports looking up wireless access points via the WiGLE API and displaying their location on a map.

## WiGLE API Configuration

Set the following environment variables before starting the application:

- `WIGLE_API_NAME` – your WiGLE API username.
- `WIGLE_API_TOKEN` – your WiGLE API token.

These credentials are used to query the WiGLE network search endpoint.

## Running

Install dependencies and run the application:

```bash
pip install -r requirements.txt
python app.py
```

Navigate to `http://localhost:8080/wigle-map` to search for a BSSID and view its location on the map.
