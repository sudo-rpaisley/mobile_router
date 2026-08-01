# Remaining `app.py` structure

Total lines: **2465**
Top-level named nodes: **233**
Decorated route handlers: **96**

## Largest top-level nodes

| Lines | Range | Kind | Name | Decorators |
|---:|---:|---|---|---|
| 77 | 1527-1603 | FunctionDef | `client_detail` | `app.route('/clients/<identifier>')` |
| 40 | 768-807 | FunctionDef | `discover_upnp_devices` | `` |
| 38 | 164-201 | FunctionDef | `load_runtime_state` | `` |
| 34 | 118-151 | FunctionDef | `runtime_state_snapshot` | `` |
| 33 | 901-933 | FunctionDef | `_run_scan_job` | `` |
| 31 | 594-624 | FunctionDef | `inventory_records` | `` |
| 31 | 1014-1044 | FunctionDef | `create_scan_job` | `` |
| 30 | 983-1012 | FunctionDef | `create_port_scan_job` | `` |
| 29 | 1685-1713 | FunctionDef | `client_export_route` | `app.route('/clients/<identifier>/export.<fmt>')` |
| 25 | 387-411 | FunctionDef | `bluetooth_detail_fields` | `` |
| 24 | 2031-2054 | FunctionDef | `wireless_network_clients_export` | `app.route('/wireless/network/clients.csv')` |
| 24 | 2263-2286 | FunctionDef | `bluetooth_action` | `app.route('/bluetooth-action', methods=['POST'])` |
| 22 | 1625-1646 | FunctionDef | `client_http_inspect` | `app.route('/clients/<identifier>/http-inspect', methods=['POST'])` |
| 21 | 745-765 | FunctionDef | `discover_mdns_services` | `` |
| 21 | 1828-1848 | FunctionDef | `port_scan_route` | `app.route('/port-scan', methods=['POST'])` |
| 21 | 2331-2351 | FunctionDef | `beacon_advertise` | `app.route('/beacon-advertise', methods=['POST'])` |
| 20 | 652-671 | FunctionDef | `record_scan_devices_for_wireless_network` | `` |
| 20 | 1229-1248 | FunctionDef | `require_application_login` | `app.before_request` |
| 20 | 1881-1900 | FunctionDef | `cancel_job` | `app.route('/jobs/<job_id>/cancel', methods=['POST'])` |
| 20 | 2439-2458 | FunctionDef | `aireplay_deauth_route` | `app.route('/aireplay-deauth', methods=['POST'])` |
| 19 | 810-828 | FunctionDef | `discover_lldp_neighbors` | `` |
| 19 | 1148-1166 | FunctionDef | `social_login_required` | `` |
| 19 | 1207-1225 | FunctionDef | `save_social_profile_photo` | `` |
| 19 | 2058-2076 | FunctionDef | `wireless_network_detail` | `app.route('/wireless/network')` |
| 19 | 2376-2394 | FunctionDef | `evil_twin_lab_route` | `app.route('/evil-twin-lab', methods=['POST'])` |
| 18 | 321-338 | FunctionDef | `_merge_inventory_device_state` | `` |
| 18 | 368-385 | FunctionDef | `forget_inventory_device` | `` |
| 18 | 1064-1081 | FunctionDef | `bluetooth_phone_card_context` | `` |
| 18 | 2226-2243 | FunctionDef | `wlan_connect` | `app.route('/wlan-connect', methods=['POST'])` |
| 18 | 2355-2372 | FunctionDef | `deauth_route` | `app.route('/deauth', methods=['POST'])` |
| 17 | 302-318 | FunctionDef | `record_bluetooth_action_history` | `` |
| 17 | 461-477 | FunctionDef | `enrich_web_port_metadata` | `` |
| 16 | 1353-1368 | FunctionDef | `create_evidence_route` | `app.route('/evidence', methods=['POST'])` |
| 16 | 1999-2014 | FunctionDef | `wireless_network_client_label_route` | `app.route('/wireless/network/label', methods=['POST'])` |
| 16 | 2290-2305 | FunctionDef | `bluetooth_device_refresh` | `app.route('/bluetooth-device/<address>/refresh', methods=['POST'])` |
| 15 | 432-446 | FunctionDef | `record_device_open_ports` | `` |
| 15 | 1438-1452 | FunctionDef | `inventory_import_route` | `app.route('/inventory/import', methods=['POST'])` |
| 15 | 1607-1621 | FunctionDef | `watch_client` | `app.route('/clients/<identifier>/watch', methods=['POST'])` |
| 15 | 1650-1664 | FunctionDef | `client_summary_route` | `app.route('/clients/<identifier>/summary')` |
| 15 | 1810-1824 | FunctionDef | `comprehensive_scan_route` | `app.route('/comprehensive-scan', methods=['POST'])` |
| 15 | 2123-2137 | FunctionDef | `syn_flood` | `app.route('/syn-flood', methods=['POST'])` |
| 15 | 2172-2186 | FunctionDef | `wlan_mode` | `app.route('/wlan-mode', methods=['POST'])` |
| 14 | 266-279 | FunctionDef | `find_inventory_device` | `` |
| 14 | 573-586 | FunctionDef | `client_baseline_diff` | `` |
| 14 | 871-884 | FunctionDef | `_append_scan_event` | `` |
| 14 | 940-953 | FunctionDef | `_scan_job_snapshot` | `` |
| 14 | 1268-1281 | FunctionDef | `submit_contact` | `app.route('/submit-contact', methods=['POST'])` |
| 14 | 2080-2093 | FunctionDef | `interface_power_state` | `app.route('/interfaces/<interface_name>/state', methods=['POST'])` |
| 14 | 2141-2154 | FunctionDef | `syn_flood_broadcast` | `app.route('/syn-flood-broadcast', methods=['POST'])` |
| 14 | 2209-2222 | FunctionDef | `wlan_scan` | `app.route('/wlan-scan', methods=['POST'])` |
| 14 | 2398-2411 | FunctionDef | `pineap_lab_route` | `app.route('/pineap-lab', methods=['POST'])` |
| 13 | 354-366 | FunctionDef | `_parse_bluetooth_info_output` | `` |
| 13 | 2107-2119 | FunctionDef | `interface_detail` | `app.route('/<interface_type>/<interface_name>')` |
| 13 | 2247-2259 | FunctionDef | `bluetooth_scan` | `app.route('/bluetooth-scan', methods=['POST'])` |
| 12 | 282-293 | FunctionDef | `bluetooth_adapter_choices` | `` |
| 12 | 887-898 | FunctionDef | `_set_scan_job` | `` |
| 12 | 1083-1094 | FunctionDef | `adapter_snapshot` | `` |
| 11 | 253-263 | FunctionDef | `bluetooth_device_summary` | `` |
| 11 | 341-351 | FunctionDef | `_bluetooth_state_updates_for_action` | `` |
| 11 | 539-549 | FunctionDef | `append_client_timeline_event` | `` |

## Route handlers in source order

| Range | Lines | Name | Decorators | Referenced globals |
|---:|---:|---|---|---|
| 1128-1129 | 2 | `index` | `app.route('/')` | app, current_context, render_template |
| 1133-1134 | 2 | `about` | `app.route('/about')` | app, current_context, render_template |
| 1138-1139 | 2 | `contact_page` | `app.route('/contact')` | app, current_context, render_template |
| 1268-1281 | 14 | `submit_contact` | `app.route('/submit-contact', methods=['POST'])` | Exception, app, e, json, json_error, json_success, open, request, str, time |
| 1285-1286 | 2 | `favicon` | `app.route('/favicon.ico')` | app, os, send_from_directory |
| 1290-1291 | 2 | `red_team` | `app.route('/red-team')` | app, current_context, render_template |
| 1295-1302 | 8 | `roadmap_page` | `app.route('/roadmap')` | ROADMAP_SECTIONS, app, current_context, remaining_roadmap_items, render_template |
| 1311-1313 | 3 | `adapters` | `app.route('/adapters', methods=['POST'])` | app, jsonify, network_interfaces |
| 1317-1327 | 11 | `adapter_updates` | `app.route('/adapters/updates', methods=['POST'])` | adapter_snapshot, adapter_update_fragments, app, jsonify, network_interfaces, request |
| 1331-1335 | 5 | `export_interfaces_json` | `app.route('/export/interfaces.json')` | app, jsonify, network_interfaces, time |
| 1339-1344 | 6 | `export_capabilities_json` | `app.route('/export/capabilities.json')` | app, build_capabilities, jsonify, time |
| 1348-1349 | 2 | `evidence_page` | `app.route('/evidence')` | app, current_context, evidence_records, render_template |
| 1353-1368 | 16 | `create_evidence_route` | `app.route('/evidence', methods=['POST'])` | ValueError, app, create_evidence_record, current_context, e, evidence_records, json_error, json_success, render_template, request, str |
| 1372-1380 | 9 | `export_evidence` | `app.route('/evidence.<fmt>')` | Response, app, evidence_as_csv, evidence_as_markdown, evidence_records, json_error, jsonify, time |
| 1384-1392 | 9 | `download_evidence_file` | `app.route('/evidence/<evidence_id>/download')` | EVIDENCE_DIR, app, evidence_vault, evidence_vault_lock, json_error, next, os, send_file |
| 1396-1397 | 2 | `reports_page` | `app.route('/reports')` | app, build_report_data, current_context, render_template |
| 1401-1411 | 11 | `export_report` | `app.route('/reports.<fmt>')` | Response, app, build_report_data, json_error, jsonify, render_template, report_as_csv, report_as_markdown |
| 1415-1416 | 2 | `network_scan` | `app.route('/network-scan')` | app, current_context, render_template |
| 1420-1429 | 10 | `inventory_page` | `app.route('/inventory')` | app, current_context, inventory_records, manufacturer_insights, render_template |
| 1433-1434 | 2 | `inventory_export_json` | `app.route('/inventory/export.json')` | app, inventory_export_payload, jsonify |
| 1438-1452 | 15 | `inventory_import_route` | `app.route('/inventory/import', methods=['POST'])` | ValueError, app, e, import_inventory_payload, inventory_page, json, json_error, json_success, request, str |
| 1456-1457 | 2 | `alerts_page` | `app.route('/alerts')` | alert_records, app, current_context, render_template |
| 1461-1463 | 3 | `alerts_status` | `app.route('/alerts/status')` | alert_records, app, json_success, len |
| 1467-1471 | 5 | `mark_alert_read` | `app.route('/alerts/<alert_id>/read', methods=['POST'])` | alerts_service, app, json_error, json_success, new_device_alerts, new_device_alerts_lock |
| 1475-1476 | 2 | `mark_all_alerts_read` | `app.route('/alerts/read-all', methods=['POST'])` | alerts_service, app, json_success, new_device_alerts, new_device_alerts_lock |
| 1480-1481 | 2 | `port_scan_page` | `app.route('/port-scan')` | app, current_context, render_template |
| 1485-1486 | 2 | `jobs_page` | `app.route('/jobs')` | app, current_context, render_template |
| 1490-1491 | 2 | `traceroute_page` | `app.route('/traceroute')` | app, current_context, render_template |
| 1495-1496 | 2 | `diagnostics_page` | `app.route('/diagnostics')` | app, current_context, render_template |
| 1500-1501 | 2 | `service_discovery_page` | `app.route('/service-discovery')` | app, current_context, render_template |
| 1505-1506 | 2 | `advanced_diagnostics_page` | `app.route('/advanced-diagnostics')` | app, current_context, render_template |
| 1510-1512 | 3 | `http_preview_file` | `app.route('/http-previews/<path:filename>')` | HTTP_PREVIEW_DIR, app, send_from_directory |
| 1516-1523 | 8 | `client_service_detail` | `app.route('/clients/<identifier>/services/<int:port>')` | app, current_context, dict, enrich_ip_client_display_name, find_inventory_device, int, next, render_template |
| 1527-1603 | 77 | `client_detail` | `app.route('/clients/<identifier>')` | app, bluetooth_action_capability, bluetooth_action_history, bluetooth_adapter_choices, bluetooth_contextual_actions, bluetooth_detail_fields, client_baseline_diff, client_health_summary, client_reachability_history, client_relationship_map, client_timeline, current_context, display_name_for_inventory_device, enrich_ip_client_display_name, find_inventory_device, get_ip_by_mac, get_mac_by_ip, is_client_watched, lookup_manufacturer, normalize_mac, … |
| 1607-1621 | 15 | `watch_client` | `app.route('/clients/<identifier>/watch', methods=['POST'])` | app, append_client_timeline_event, json_error, json_success, request, save_runtime_state, str, watched_clients |
| 1625-1646 | 22 | `client_http_inspect` | `app.route('/clients/<identifier>/http-inspect', methods=['POST'])` | ValueError, any, app, append_client_timeline_event, e, find_inventory_device, inspect_http_services, json_error, json_success, len, parse_int, request, set, sorted, str |
| 1650-1664 | 15 | `client_summary_route` | `app.route('/clients/<identifier>/summary')` | app, display_name_for_inventory_device, enrich_ip_client_display_name, find_inventory_device, json_success |
| 1668-1674 | 7 | `client_metadata_route` | `app.route('/clients/<identifier>/metadata', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, str, update_client_metadata |
| 1678-1681 | 4 | `client_baseline_route` | `app.route('/clients/<identifier>/baseline', methods=['POST'])` | app, client_baseline_diff, json_success, save_client_baseline |
| 1685-1713 | 29 | `client_export_route` | `app.route('/clients/<identifier>/export.<fmt>')` | Response, app, client_profile_export, json_error, jsonify |
| 1717-1718 | 2 | `client_relationship_map_route` | `app.route('/clients/<identifier>/relationship-map')` | app, client_relationship_map, json_success |
| 1722-1724 | 3 | `client_intelligence_route` | `app.route('/clients/<identifier>/intelligence', methods=['POST'])` | app, client_intelligence_profile, json_success, request |
| 1728-1729 | 2 | `client_fingerprint_route` | `app.route('/clients/<identifier>/fingerprint', methods=['POST'])` | app, fingerprint_client_services, json_success |
| 1733-1738 | 6 | `client_scheduled_check_route` | `app.route('/clients/<identifier>/scheduled-check', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, save_scheduled_client_check, str |
| 1742-1747 | 6 | `client_scheduled_check_run_route` | `app.route('/clients/<identifier>/scheduled-check/run', methods=['POST'])` | ValueError, app, e, json_error, json_success, run_scheduled_client_check, str |
| 1751-1753 | 3 | `scheduled_checks_run_due_route` | `app.route('/scheduled-checks/run-due', methods=['POST'])` | app, json_success, len, run_due_scheduled_client_checks |
| 1757-1766 | 10 | `active_scan_route` | `app.route('/active-scan', methods=['POST'])` | active_scan, app, classify_scan_results, json_error, jsonify, record_inventory_devices, record_scan_devices_for_wireless_network, request |
| 1770-1780 | 11 | `passive_scan_route` | `app.route('/passive-scan', methods=['POST'])` | app, classify_scan_results, json_error, jsonify, passive_scan, record_inventory_devices, record_passive_observation_analytics, record_scan_devices_for_wireless_network, request |
| 1784-1786 | 3 | `passive_analytics_route` | `app.route('/passive-analytics.json')` | app, json_success, passive_observation_summary, request |
| 1790-1793 | 4 | `passive_monitor_status_route` | `app.route('/passive-monitor/status')` | app, jsonify, passive_monitor_snapshot, request |
| 1797-1806 | 10 | `passive_monitor_toggle_route` | `app.route('/passive-monitor/toggle', methods=['POST'])` | ValueError, app, exc, json_error, json_success, request, set_passive_monitor, str |
| 1810-1824 | 15 | `comprehensive_scan_route` | `app.route('/comprehensive-scan', methods=['POST'])` | ValueError, app, comprehensive_network_device_scan, e, json_error, json_success, record_scan_devices_for_wireless_network, request, str |
| 1828-1848 | 21 | `port_scan_route` | `app.route('/port-scan', methods=['POST'])` | PortScanError, ValueError, app, describe_open_ports, e, enrich_web_port_metadata, json_error, jsonify, missing_fields, parse_int, record_device_open_ports, request, scan_ports, str |
| 1852-1862 | 11 | `start_port_scan_job` | `app.route('/port-scan-jobs', methods=['POST'])` | ValueError, app, create_port_scan_job, e, json_error, json_success, missing_fields, parse_int, request, str |
| 1866-1871 | 6 | `port_scan_job_status` | `app.route('/port-scan-jobs/<job_id>')` | _port_scan_job_snapshot, app, json_error, json_success, port_scan_jobs, port_scan_jobs_lock |
| 1875-1877 | 3 | `jobs_status` | `app.route('/jobs/status')` | all_job_snapshots, app, json_success, len |
| 1881-1900 | 20 | `cancel_job` | `app.route('/jobs/<job_id>/cancel', methods=['POST'])` | _port_scan_job_snapshot, _scan_job_snapshot, app, json_error, json_success, port_scan_jobs, port_scan_jobs_lock, scan_jobs, scan_jobs_lock, time |
| 1904-1910 | 7 | `traceroute_route` | `app.route('/traceroute', methods=['POST'])` | app, json_error, jsonify, request, traceroute |
| 1914-1921 | 8 | `ping_route` | `app.route('/ping', methods=['POST'])` | ValueError, app, e, json_error, json_success, ping_history, request, run_ping_check, str, subprocess |
| 1925-1930 | 6 | `ping_sweep_route` | `app.route('/ping-sweep', methods=['POST'])` | ValueError, app, e, json_error, json_success, ping_history, request, run_ping_sweep, str |
| 1934-1936 | 3 | `route_diagnostics_route` | `app.route('/route-diagnostics', methods=['POST'])` | app, build_route_diagnostics, json_success, request |
| 1940-1942 | 3 | `mdns_discovery_route` | `app.route('/mdns-discovery', methods=['POST'])` | app, discover_mdns_services, json_success, request |
| 1946-1952 | 7 | `upnp_discovery_route` | `app.route('/upnp-discovery', methods=['POST'])` | ValueError, app, discover_upnp_devices, e, json_error, json_success, max, min, parse_int, request, str |
| 1956-1958 | 3 | `neighbor_discovery_route` | `app.route('/neighbor-discovery', methods=['POST'])` | app, discover_lldp_neighbors, json_success, request |
| 1962-1964 | 3 | `vlan_discovery_route` | `app.route('/vlan-discovery', methods=['POST'])` | app, discover_vlan_context, json_success, request |
| 1968-1969 | 2 | `egress_diagnostics_route` | `app.route('/egress-diagnostics', methods=['POST'])` | app, build_egress_diagnostics, json_success, request |
| 1973-1978 | 6 | `iperf3_test_route` | `app.route('/iperf3-test', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, run_iperf3_test, str, subprocess |
| 1982-1989 | 8 | `snmp_discovery_route` | `app.route('/snmp-discovery', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, run_snmp_inventory, str |
| 1993-1995 | 3 | `ipv6_assessment_route` | `app.route('/ipv6-assessment', methods=['POST'])` | app, json_success, request, run_ipv6_assessment |
| 1999-2014 | 16 | `wireless_network_client_label_route` | `app.route('/wireless/network/label', methods=['POST'])` | app, json_error, json_success, request, save_runtime_state, wireless_network_client_label_key, wireless_network_labels |
| 2018-2027 | 10 | `wireless_network_clients_json` | `app.route('/wireless/network/clients.json')` | app, json_success, merge_wireless_network_clients, request, wifi_utils |
| 2031-2054 | 24 | `wireless_network_clients_export` | `app.route('/wireless/network/clients.csv')` | Response, app, csv, io, json, merge_wireless_network_clients, request, secure_filename, str, wifi_utils |
| 2058-2076 | 19 | `wireless_network_detail` | `app.route('/wireless/network')` | app, current_context, merge_wireless_network_clients, render_template, request, wifi_utils |
| 2080-2093 | 14 | `interface_power_state` | `app.route('/interfaces/<interface_name>/state', methods=['POST'])` | Exception, ValueError, app, exc, getattr, json_error, json_success, network_interfaces, next, request, set_interface_power_state, str |
| 2096-2103 | 8 | `interfaces_by_type` | `app.route('/<interface_type>')` | app, current_context, network_interfaces, render_template |
| 2107-2119 | 13 | `interface_detail` | `app.route('/<interface_type>/<interface_name>')` | app, bluetooth_phone_card_context, current_context, network_interfaces, next, render_template |
| 2123-2137 | 15 | `syn_flood` | `app.route('/syn-flood', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, missing_fields, networkAttacks, parse_int, request, str |
| 2141-2154 | 14 | `syn_flood_broadcast` | `app.route('/syn-flood-broadcast', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, missing_fields, networkAttacks, parse_int, request, str |
| 2158-2168 | 11 | `wlan_modes` | `app.route('/wlan-modes', methods=['GET'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 2172-2186 | 15 | `wlan_mode` | `app.route('/wlan-mode', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, request, str, wifi_utils |
| 2190-2196 | 7 | `start_scan_job` | `app.route('/scan-jobs', methods=['POST'])` | ValueError, app, create_scan_job, e, json_error, json_success, request, str |
| 2200-2205 | 6 | `scan_job_status` | `app.route('/scan-jobs/<job_id>')` | _scan_job_snapshot, app, json_error, json_success, scan_jobs, scan_jobs_lock |
| 2209-2222 | 14 | `wlan_scan` | `app.route('/wlan-scan', methods=['POST'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 2226-2243 | 18 | `wlan_connect` | `app.route('/wlan-connect', methods=['POST'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 2247-2259 | 13 | `bluetooth_scan` | `app.route('/bluetooth-scan', methods=['POST'])` | Exception, app, asyncio, bluetooth_action_capability, bluetooth_device_summary, e, get_bluetooth_devices, json_error, json_success, request, str |
| 2263-2286 | 24 | `bluetooth_action` | `app.route('/bluetooth-action', methods=['POST'])` | BluetoothToolUnavailable, Exception, ValueError, _bluetooth_state_updates_for_action, _merge_inventory_device_state, _parse_bluetooth_info_output, app, bluetooth_contextual_actions, bluetooth_device_state, e, find_inventory_device, json_error, json_success, record_bluetooth_action_history, request, run_bluetoothctl_action, str |
| 2290-2305 | 16 | `bluetooth_device_refresh` | `app.route('/bluetooth-device/<address>/refresh', methods=['POST'])` | BluetoothToolUnavailable, Exception, ValueError, _merge_inventory_device_state, _parse_bluetooth_info_output, app, bluetooth_contextual_actions, bluetooth_device_state, e, json_error, json_success, record_bluetooth_action_history, request, run_bluetoothctl_action, str |
| 2309-2313 | 5 | `forget_inventory_route` | `app.route('/inventory/<identifier>/forget', methods=['POST'])` | app, forget_inventory_device, json_error, json_success |
| 2317-2327 | 11 | `spoof_mac_route` | `app.route('/spoof-mac', methods=['POST'])` | app, json_error, json_success, request, spoof_mac |
| 2331-2351 | 21 | `beacon_advertise` | `app.route('/beacon-advertise', methods=['POST'])` | Exception, ValueError, app, beaconSpoof, e, json_error, json_success, missing_fields, parse_int, request, str |
| 2355-2372 | 18 | `deauth_route` | `app.route('/deauth', methods=['POST'])` | Exception, ValueError, app, deauth, e, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, str |
| 2376-2394 | 19 | `evil_twin_lab_route` | `app.route('/evil-twin-lab', methods=['POST'])` | ValueError, app, e, evil_twin_lab_lock, evil_twin_lab_runs, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, save_runtime_state, str |
| 2398-2411 | 14 | `pineap_lab_route` | `app.route('/pineap-lab', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, labs_service, len, missing_fields, normalize_mac, parse_int, pineap_lab_lock, pineap_lab_runs, request, save_runtime_state, str, wifi_utils |
| 2415-2425 | 11 | `handshake_lab_route` | `app.route('/handshake-lab', methods=['POST'])` | ValueError, app, create_evidence_record, e, handshake_lab_lock, handshake_lab_records, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, save_runtime_state, str |
| 2429-2435 | 7 | `export_handshake_lab` | `app.route('/handshake-lab.<fmt>')` | Response, app, handshake_lab_lock, handshake_lab_records, json_error, jsonify, labs_service, time |
| 2439-2458 | 20 | `aireplay_deauth_route` | `app.route('/aireplay-deauth', methods=['POST'])` | Exception, ValueError, aireplay_deauth, app, e, json_error, json_success, missing_fields, parse_int, request, str |
