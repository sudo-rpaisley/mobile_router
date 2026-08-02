from pathlib import Path


SCRIPT = Path('static/js/wireless-deauth-buttons.js')
FOOTER = Path('templates/_footer.html')


def test_bounded_deauth_button_controller_is_loaded_globally():
    footer = FOOTER.read_text(encoding='utf-8')

    assert '/static/js/wireless-deauth-buttons.js' in footer
    assert SCRIPT.is_file()


def test_network_quick_control_is_upgraded_to_start_stop_session():
    source = SCRIPT.read_text(encoding='utf-8')

    assert "upgradeNetworkForm" in source
    assert "Start AP deauth" in source
    assert "Stop deauth" in source
    assert "'/deauth/start'" in source
    assert "'/deauth/stop'" in source
    assert "'/deauth/heartbeat'" in source
    assert "frames: 1" not in source
    assert "event.stopImmediatePropagation()" in source
    assert "MutationObserver" in source


def test_individual_client_gets_targeted_bounded_deauth_panel():
    source = SCRIPT.read_text(encoding='utf-8')

    assert "window.location.pathname.startsWith('/clients/')" in source
    assert "data-client-deauth-panel" in source
    assert "Bounded Device Deauth" in source
    assert "Start device deauth" in source
    assert "data-deauth-ap-input" in source
    assert "data-deauth-interface-input" in source
    assert "data-deauth-authorized" in source
    assert "form.dataset.target || BROADCAST_MAC" in source


def test_deauth_buttons_retain_fail_closed_browser_behaviour():
    source = SCRIPT.read_text(encoding='utf-8')

    assert "HEARTBEAT_INTERVAL_MS = 2000" in source
    assert "navigator.sendBeacon('/deauth/stop'" in source
    assert "Administrator login is required." in source
    assert "authorized isolated lab" in source
    assert "Another deauth session is active" in source
