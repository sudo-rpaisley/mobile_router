"""Consolidate repeated MAC normalisation and Wi-Fi flush logic."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

NORMALIZE_BLOCK = """def _normalize_mac(mac):
    if not mac:
        return None
    return str(mac).strip().replace("-", ":").lower()
"""
NORMALIZE_IMPORT = "from .common import normalize_mac\n"
NORMALIZE_ALIAS = "_normalize_mac = normalize_mac\n"

NETWORK_COUNT_BLOCK = """def _network_count():
    return sum(len(network.access_points) for network in networks.values())
"""
FLUSH_HELPER = """def _flush_current_network(
    ssid,
    bssid,
    channel,
    signal,
    security,
    wps,
    wps_status,
    channel_width,
    width_source,
):
    if bssid:
        _add_network(
            ssid,
            bssid,
            channel,
            signal,
            security,
            wps=wps or _security_mentions_wps(security),
            wps_status=wps_status,
            channel_width=channel_width or 20,
            width_source=width_source,
        )
"""
NESTED_FLUSH_TEMPLATE = """    def {name}():
        if current_bssid:
            _add_network(
                current_ssid,
                current_bssid,
                current_channel,
                current_signal,
                current_security,
                wps=current_wps or _security_mentions_wps(current_security),
                wps_status=current_wps_status,
                channel_width=current_channel_width or 20,
                width_source=current_width_source,
            )

"""
FLUSH_CALL = """_flush_current_network(
                current_ssid,
                current_bssid,
                current_channel,
                current_signal,
                current_security,
                current_wps,
                current_wps_status,
                current_channel_width,
                current_width_source,
            )"""
FINAL_FLUSH_CALL = """_flush_current_network(
        current_ssid,
        current_bssid,
        current_channel,
        current_signal,
        current_security,
        current_wps,
        current_wps_status,
        current_channel_width,
        current_width_source,
    )"""


def consolidate_normalizer(relative_path: str) -> None:
    path = ROOT / relative_path
    source = path.read_text(encoding="utf-8")
    if NORMALIZE_ALIAS in source:
        return
    if NORMALIZE_BLOCK not in source:
        raise RuntimeError(f"MAC normaliser not found in {path}")

    lines = source.splitlines(keepends=True)
    import_end = 0
    for index, line in enumerate(lines):
        if line.startswith(("import ", "from ")):
            import_end = index + 1
    lines.insert(import_end, NORMALIZE_IMPORT)
    updated = "".join(lines).replace(NORMALIZE_BLOCK, NORMALIZE_ALIAS, 1)
    while "\n\n\n\n" in updated:
        updated = updated.replace("\n\n\n\n", "\n\n\n")
    path.write_text(updated, encoding="utf-8")


def consolidate_wifi_flush() -> None:
    path = ROOT / "scripts/wifi/utils.py"
    source = path.read_text(encoding="utf-8")
    if FLUSH_HELPER not in source:
        if NETWORK_COUNT_BLOCK not in source:
            raise RuntimeError("Wi-Fi network count anchor was not found")
        source = source.replace(
            NETWORK_COUNT_BLOCK,
            NETWORK_COUNT_BLOCK + "\n\n" + FLUSH_HELPER,
            1,
        )

    for name in ("flush_bss", "flush_bssid"):
        block = NESTED_FLUSH_TEMPLATE.format(name=name)
        if block in source:
            source = source.replace(block, "", 1)

    source = source.replace("flush_bss()", FLUSH_CALL, 1)
    source = source.replace("flush_bss()", FINAL_FLUSH_CALL, 1)
    source = source.replace("flush_bssid()", FLUSH_CALL, 2)
    source = source.replace("flush_bssid()", FINAL_FLUSH_CALL, 1)

    if "def flush_bss" in source or "def flush_bssid" in source:
        raise RuntimeError("Nested Wi-Fi flush functions remain")
    path.write_text(source, encoding="utf-8")


def main() -> None:
    consolidate_normalizer("scripts/network/classification.py")
    consolidate_normalizer("scripts/network/passive_capture.py")
    consolidate_wifi_flush()


if __name__ == "__main__":
    main()
