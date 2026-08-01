# Remaining `app.py` structure

Total lines: **3191**
Top-level named nodes: **258**
Decorated route handlers: **96**

## Largest top-level nodes

| Lines | Range | Kind | Name | Decorators |
|---:|---:|---|---|---|
| 77 | 2253-2329 | FunctionDef | `client_detail` | `app.route('/clients/<identifier>')` |
| 55 | 1364-1418 | FunctionDef | `record_passive_observation_analytics` | `` |
| 50 | 700-749 | FunctionDef | `client_intelligence_profile` | `` |
| 45 | 1542-1586 | FunctionDef | `comprehensive_network_device_scan` | `` |
| 44 | 875-918 | FunctionDef | `fingerprint_client_services` | `` |
| 40 | 752-791 | FunctionDef | `update_client_metadata` | `` |
| 40 | 1269-1308 | FunctionDef | `discover_upnp_devices` | `` |
| 38 | 164-201 | FunctionDef | `load_runtime_state` | `` |
| 38 | 544-581 | FunctionDef | `enrich_ip_client_display_name` | `` |
| 36 | 1467-1502 | FunctionDef | `_passive_monitor_worker` | `` |
| 35 | 1421-1455 | FunctionDef | `passive_observation_summary` | `` |
| 35 | 1505-1539 | FunctionDef | `set_passive_monitor` | `` |
| 34 | 118-151 | FunctionDef | `runtime_state_snapshot` | `` |
| 34 | 622-655 | FunctionDef | `client_health_summary` | `` |
| 33 | 969-1001 | FunctionDef | `run_scheduled_client_check` | `` |
| 33 | 1627-1659 | FunctionDef | `_run_scan_job` | `` |
| 31 | 1095-1125 | FunctionDef | `inventory_records` | `` |
| 31 | 1740-1770 | FunctionDef | `create_scan_job` | `` |
| 30 | 1709-1738 | FunctionDef | `create_port_scan_job` | `` |
| 29 | 2411-2439 | FunctionDef | `client_export_route` | `app.route('/clients/<identifier>/export.<fmt>')` |
| 26 | 499-524 | FunctionDef | `_dhcp_lease_display_name` | `` |
| 26 | 1067-1092 | FunctionDef | `inspect_http_services` | `` |
| 25 | 387-411 | FunctionDef | `bluetooth_detail_fields` | `` |
| 24 | 921-944 | FunctionDef | `save_scheduled_client_check` | `` |
| 24 | 2757-2780 | FunctionDef | `wireless_network_clients_export` | `app.route('/wireless/network/clients.csv')` |
| 24 | 2989-3012 | FunctionDef | `bluetooth_action` | `app.route('/bluetooth-action', methods=['POST'])` |
| 23 | 597-619 | FunctionDef | `client_timeline` | `` |
| 22 | 851-872 | FunctionDef | `client_relationship_map` | `` |
| 22 | 2351-2372 | FunctionDef | `client_http_inspect` | `app.route('/clients/<identifier>/http-inspect', methods=['POST'])` |
| 21 | 1044-1064 | FunctionDef | `capture_http_preview_thumbnail` | `` |
| 21 | 1246-1266 | FunctionDef | `discover_mdns_services` | `` |
| 21 | 2554-2574 | FunctionDef | `port_scan_route` | `app.route('/port-scan', methods=['POST'])` |
| 21 | 3057-3077 | FunctionDef | `beacon_advertise` | `app.route('/beacon-advertise', methods=['POST'])` |
| 20 | 947-966 | FunctionDef | `scan_common_client_ports` | `` |
| 20 | 1153-1172 | FunctionDef | `record_scan_devices_for_wireless_network` | `` |
| 20 | 1955-1974 | FunctionDef | `require_application_login` | `app.before_request` |
| 20 | 2607-2626 | FunctionDef | `cancel_job` | `app.route('/jobs/<job_id>/cancel', methods=['POST'])` |
| 20 | 3165-3184 | FunctionDef | `aireplay_deauth_route` | `app.route('/aireplay-deauth', methods=['POST'])` |
| 19 | 667-685 | FunctionDef | `_ttl_os_hint` | `` |
| 19 | 794-812 | FunctionDef | `save_client_baseline` | `` |
| 19 | 1311-1329 | FunctionDef | `discover_lldp_neighbors` | `` |
| 19 | 1874-1892 | FunctionDef | `social_login_required` | `` |
| 19 | 1933-1951 | FunctionDef | `save_social_profile_photo` | `` |
| 19 | 2784-2802 | FunctionDef | `wireless_network_detail` | `app.route('/wireless/network')` |
| 19 | 3102-3120 | FunctionDef | `evil_twin_lab_route` | `app.route('/evil-twin-lab', methods=['POST'])` |
| 18 | 321-338 | FunctionDef | `_merge_inventory_device_state` | `` |
| 18 | 368-385 | FunctionDef | `forget_inventory_device` | `` |
| 18 | 831-848 | FunctionDef | `client_profile_export` | `` |
| 18 | 1790-1807 | FunctionDef | `bluetooth_phone_card_context` | `` |
| 18 | 2952-2969 | FunctionDef | `wlan_connect` | `app.route('/wlan-connect', methods=['POST'])` |
| 18 | 3081-3098 | FunctionDef | `deauth_route` | `app.route('/deauth', methods=['POST'])` |
| 17 | 302-318 | FunctionDef | `record_bluetooth_action_history` | `` |
| 17 | 461-477 | FunctionDef | `enrich_web_port_metadata` | `` |
| 16 | 1004-1019 | FunctionDef | `run_due_scheduled_client_checks` | `` |
| 16 | 1026-1041 | FunctionDef | `create_client_watch_alert` | `` |
| 16 | 2079-2094 | FunctionDef | `create_evidence_route` | `app.route('/evidence', methods=['POST'])` |
| 16 | 2725-2740 | FunctionDef | `wireless_network_client_label_route` | `app.route('/wireless/network/label', methods=['POST'])` |
| 16 | 3016-3031 | FunctionDef | `bluetooth_device_refresh` | `app.route('/bluetooth-device/<address>/refresh', methods=['POST'])` |
| 15 | 432-446 | FunctionDef | `record_device_open_ports` | `` |
| 15 | 527-541 | FunctionDef | `display_name_for_inventory_device` | `` |

## Route handlers in source order

| Range | Lines | Name | Decorators | Referenced globals |
|---:|---:|---|---|---|
| 1854-1855 | 2 | `index` | `app.route('/')` | app, current_context, render_template |
| 1859-1860 | 2 | `about` | `app.route('/about')` | app, current_context, render_template |
| 1864-1865 | 2 | `contact_page` | `app.route('/contact')` | app, current_context, render_template |
| 1994-2007 | 14 | `submit_contact` | `app.route('/submit-contact', methods=['POST'])` | Exception, app, e, json, json_error, json_success, open, request, str, time |
| 2011-2012 | 2 | `favicon` | `app.route('/favicon.ico')` | app, os, send_from_directory |
| 2016-2017 | 2 | `red_team` | `app.route('/red-team')` | app, current_context, render_template |
| 2021-2028 | 8 | `roadmap_page` | `app.route('/roadmap')` | ROADMAP_SECTIONS, app, current_context, remaining_roadmap_items, render_template |
| 2037-2039 | 3 | `adapters` | `app.route('/adapters', methods=['POST'])` | app, jsonify, network_interfaces |
| 2043-2053 | 11 | `adapter_updates` | `app.route('/adapters/updates', methods=['POST'])` | adapter_snapshot, adapter_update_fragments, app, jsonify, network_interfaces, request |
| 2057-2061 | 5 | `export_interfaces_json` | `app.route('/export/interfaces.json')` | app, jsonify, network_interfaces, time |
| 2065-2070 | 6 | `export_capabilities_json` | `app.route('/export/capabilities.json')` | app, build_capabilities, jsonify, time |
| 2074-2075 | 2 | `evidence_page` | `app.route('/evidence')` | app, current_context, evidence_records, render_template |
| 2079-2094 | 16 | `create_evidence_route` | `app.route('/evidence', methods=['POST'])` | ValueError, app, create_evidence_record, current_context, e, evidence_records, json_error, json_success, render_template, request, str |
| 2098-2106 | 9 | `export_evidence` | `app.route('/evidence.<fmt>')` | Response, app, evidence_as_csv, evidence_as_markdown, evidence_records, json_error, jsonify, time |
| 2110-2118 | 9 | `download_evidence_file` | `app.route('/evidence/<evidence_id>/download')` | EVIDENCE_DIR, app, evidence_vault, evidence_vault_lock, json_error, next, os, send_file |
| 2122-2123 | 2 | `reports_page` | `app.route('/reports')` | app, build_report_data, current_context, render_template |
| 2127-2137 | 11 | `export_report` | `app.route('/reports.<fmt>')` | Response, app, build_report_data, json_error, jsonify, render_template, report_as_csv, report_as_markdown |
| 2141-2142 | 2 | `network_scan` | `app.route('/network-scan')` | app, current_context, render_template |
| 2146-2155 | 10 | `inventory_page` | `app.route('/inventory')` | app, current_context, inventory_records, manufacturer_insights, render_template |
| 2159-2160 | 2 | `inventory_export_json` | `app.route('/inventory/export.json')` | app, inventory_export_payload, jsonify |
| 2164-2178 | 15 | `inventory_import_route` | `app.route('/inventory/import', methods=['POST'])` | ValueError, app, e, import_inventory_payload, inventory_page, json, json_error, json_success, request, str |
| 2182-2183 | 2 | `alerts_page` | `app.route('/alerts')` | alert_records, app, current_context, render_template |
| 2187-2189 | 3 | `alerts_status` | `app.route('/alerts/status')` | alert_records, app, json_success, len |
| 2193-2197 | 5 | `mark_alert_read` | `app.route('/alerts/<alert_id>/read', methods=['POST'])` | alerts_service, app, json_error, json_success, new_device_alerts, new_device_alerts_lock |
| 2201-2202 | 2 | `mark_all_alerts_read` | `app.route('/alerts/read-all', methods=['POST'])` | alerts_service, app, json_success, new_device_alerts, new_device_alerts_lock |
| 2206-2207 | 2 | `port_scan_page` | `app.route('/port-scan')` | app, current_context, render_template |
| 2211-2212 | 2 | `jobs_page` | `app.route('/jobs')` | app, current_context, render_template |
| 2216-2217 | 2 | `traceroute_page` | `app.route('/traceroute')` | app, current_context, render_template |
| 2221-2222 | 2 | `diagnostics_page` | `app.route('/diagnostics')` | app, current_context, render_template |
| 2226-2227 | 2 | `service_discovery_page` | `app.route('/service-discovery')` | app, current_context, render_template |
| 2231-2232 | 2 | `advanced_diagnostics_page` | `app.route('/advanced-diagnostics')` | app, current_context, render_template |
| 2236-2238 | 3 | `http_preview_file` | `app.route('/http-previews/<path:filename>')` | HTTP_PREVIEW_DIR, app, send_from_directory |
| 2242-2249 | 8 | `client_service_detail` | `app.route('/clients/<identifier>/services/<int:port>')` | app, current_context, dict, enrich_ip_client_display_name, find_inventory_device, int, next, render_template |
| 2253-2329 | 77 | `client_detail` | `app.route('/clients/<identifier>')` | app, bluetooth_action_capability, bluetooth_action_history, bluetooth_adapter_choices, bluetooth_contextual_actions, bluetooth_detail_fields, client_baseline_diff, client_health_summary, client_reachability_history, client_relationship_map, client_timeline, current_context, display_name_for_inventory_device, enrich_ip_client_display_name, find_inventory_device, get_ip_by_mac, get_mac_by_ip, is_client_watched, lookup_manufacturer, normalize_mac, … |
| 2333-2347 | 15 | `watch_client` | `app.route('/clients/<identifier>/watch', methods=['POST'])` | app, append_client_timeline_event, json_error, json_success, request, save_runtime_state, str, watched_clients |
| 2351-2372 | 22 | `client_http_inspect` | `app.route('/clients/<identifier>/http-inspect', methods=['POST'])` | ValueError, any, app, append_client_timeline_event, e, find_inventory_device, inspect_http_services, json_error, json_success, len, parse_int, request, set, sorted, str |
| 2376-2390 | 15 | `client_summary_route` | `app.route('/clients/<identifier>/summary')` | app, display_name_for_inventory_device, enrich_ip_client_display_name, find_inventory_device, json_success |
| 2394-2400 | 7 | `client_metadata_route` | `app.route('/clients/<identifier>/metadata', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, str, update_client_metadata |
| 2404-2407 | 4 | `client_baseline_route` | `app.route('/clients/<identifier>/baseline', methods=['POST'])` | app, client_baseline_diff, json_success, save_client_baseline |
| 2411-2439 | 29 | `client_export_route` | `app.route('/clients/<identifier>/export.<fmt>')` | Response, app, client_profile_export, json_error, jsonify |
| 2443-2444 | 2 | `client_relationship_map_route` | `app.route('/clients/<identifier>/relationship-map')` | app, client_relationship_map, json_success |
| 2448-2450 | 3 | `client_intelligence_route` | `app.route('/clients/<identifier>/intelligence', methods=['POST'])` | app, client_intelligence_profile, json_success, request |
| 2454-2455 | 2 | `client_fingerprint_route` | `app.route('/clients/<identifier>/fingerprint', methods=['POST'])` | app, fingerprint_client_services, json_success |
| 2459-2464 | 6 | `client_scheduled_check_route` | `app.route('/clients/<identifier>/scheduled-check', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, save_scheduled_client_check, str |
| 2468-2473 | 6 | `client_scheduled_check_run_route` | `app.route('/clients/<identifier>/scheduled-check/run', methods=['POST'])` | ValueError, app, e, json_error, json_success, run_scheduled_client_check, str |
| 2477-2479 | 3 | `scheduled_checks_run_due_route` | `app.route('/scheduled-checks/run-due', methods=['POST'])` | app, json_success, len, run_due_scheduled_client_checks |
| 2483-2492 | 10 | `active_scan_route` | `app.route('/active-scan', methods=['POST'])` | active_scan, app, classify_scan_results, json_error, jsonify, record_inventory_devices, record_scan_devices_for_wireless_network, request |
| 2496-2506 | 11 | `passive_scan_route` | `app.route('/passive-scan', methods=['POST'])` | app, classify_scan_results, json_error, jsonify, passive_scan, record_inventory_devices, record_passive_observation_analytics, record_scan_devices_for_wireless_network, request |
| 2510-2512 | 3 | `passive_analytics_route` | `app.route('/passive-analytics.json')` | app, json_success, passive_observation_summary, request |
| 2516-2519 | 4 | `passive_monitor_status_route` | `app.route('/passive-monitor/status')` | app, jsonify, passive_monitor_snapshot, request |
| 2523-2532 | 10 | `passive_monitor_toggle_route` | `app.route('/passive-monitor/toggle', methods=['POST'])` | ValueError, app, exc, json_error, json_success, request, set_passive_monitor, str |
| 2536-2550 | 15 | `comprehensive_scan_route` | `app.route('/comprehensive-scan', methods=['POST'])` | ValueError, app, comprehensive_network_device_scan, e, json_error, json_success, record_scan_devices_for_wireless_network, request, str |
| 2554-2574 | 21 | `port_scan_route` | `app.route('/port-scan', methods=['POST'])` | PortScanError, ValueError, app, describe_open_ports, e, enrich_web_port_metadata, json_error, jsonify, missing_fields, parse_int, record_device_open_ports, request, scan_ports, str |
| 2578-2588 | 11 | `start_port_scan_job` | `app.route('/port-scan-jobs', methods=['POST'])` | ValueError, app, create_port_scan_job, e, json_error, json_success, missing_fields, parse_int, request, str |
| 2592-2597 | 6 | `port_scan_job_status` | `app.route('/port-scan-jobs/<job_id>')` | _port_scan_job_snapshot, app, json_error, json_success, port_scan_jobs, port_scan_jobs_lock |
| 2601-2603 | 3 | `jobs_status` | `app.route('/jobs/status')` | all_job_snapshots, app, json_success, len |
| 2607-2626 | 20 | `cancel_job` | `app.route('/jobs/<job_id>/cancel', methods=['POST'])` | _port_scan_job_snapshot, _scan_job_snapshot, app, json_error, json_success, port_scan_jobs, port_scan_jobs_lock, scan_jobs, scan_jobs_lock, time |
| 2630-2636 | 7 | `traceroute_route` | `app.route('/traceroute', methods=['POST'])` | app, json_error, jsonify, request, traceroute |
| 2640-2647 | 8 | `ping_route` | `app.route('/ping', methods=['POST'])` | ValueError, app, e, json_error, json_success, ping_history, request, run_ping_check, str, subprocess |
| 2651-2656 | 6 | `ping_sweep_route` | `app.route('/ping-sweep', methods=['POST'])` | ValueError, app, e, json_error, json_success, ping_history, request, run_ping_sweep, str |
| 2660-2662 | 3 | `route_diagnostics_route` | `app.route('/route-diagnostics', methods=['POST'])` | app, build_route_diagnostics, json_success, request |
| 2666-2668 | 3 | `mdns_discovery_route` | `app.route('/mdns-discovery', methods=['POST'])` | app, discover_mdns_services, json_success, request |
| 2672-2678 | 7 | `upnp_discovery_route` | `app.route('/upnp-discovery', methods=['POST'])` | ValueError, app, discover_upnp_devices, e, json_error, json_success, max, min, parse_int, request, str |
| 2682-2684 | 3 | `neighbor_discovery_route` | `app.route('/neighbor-discovery', methods=['POST'])` | app, discover_lldp_neighbors, json_success, request |
| 2688-2690 | 3 | `vlan_discovery_route` | `app.route('/vlan-discovery', methods=['POST'])` | app, discover_vlan_context, json_success, request |
| 2694-2695 | 2 | `egress_diagnostics_route` | `app.route('/egress-diagnostics', methods=['POST'])` | app, build_egress_diagnostics, json_success, request |
| 2699-2704 | 6 | `iperf3_test_route` | `app.route('/iperf3-test', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, run_iperf3_test, str, subprocess |
| 2708-2715 | 8 | `snmp_discovery_route` | `app.route('/snmp-discovery', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, run_snmp_inventory, str |
| 2719-2721 | 3 | `ipv6_assessment_route` | `app.route('/ipv6-assessment', methods=['POST'])` | app, json_success, request, run_ipv6_assessment |
| 2725-2740 | 16 | `wireless_network_client_label_route` | `app.route('/wireless/network/label', methods=['POST'])` | app, json_error, json_success, request, save_runtime_state, wireless_network_client_label_key, wireless_network_labels |
| 2744-2753 | 10 | `wireless_network_clients_json` | `app.route('/wireless/network/clients.json')` | app, json_success, merge_wireless_network_clients, request, wifi_utils |
| 2757-2780 | 24 | `wireless_network_clients_export` | `app.route('/wireless/network/clients.csv')` | Response, app, csv, io, json, merge_wireless_network_clients, request, secure_filename, str, wifi_utils |
| 2784-2802 | 19 | `wireless_network_detail` | `app.route('/wireless/network')` | app, current_context, merge_wireless_network_clients, render_template, request, wifi_utils |
| 2806-2819 | 14 | `interface_power_state` | `app.route('/interfaces/<interface_name>/state', methods=['POST'])` | Exception, ValueError, app, exc, getattr, json_error, json_success, network_interfaces, next, request, set_interface_power_state, str |
| 2822-2829 | 8 | `interfaces_by_type` | `app.route('/<interface_type>')` | app, current_context, network_interfaces, render_template |
| 2833-2845 | 13 | `interface_detail` | `app.route('/<interface_type>/<interface_name>')` | app, bluetooth_phone_card_context, current_context, network_interfaces, next, render_template |
| 2849-2863 | 15 | `syn_flood` | `app.route('/syn-flood', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, missing_fields, networkAttacks, parse_int, request, str |
| 2867-2880 | 14 | `syn_flood_broadcast` | `app.route('/syn-flood-broadcast', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, missing_fields, networkAttacks, parse_int, request, str |
| 2884-2894 | 11 | `wlan_modes` | `app.route('/wlan-modes', methods=['GET'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 2898-2912 | 15 | `wlan_mode` | `app.route('/wlan-mode', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, request, str, wifi_utils |
| 2916-2922 | 7 | `start_scan_job` | `app.route('/scan-jobs', methods=['POST'])` | ValueError, app, create_scan_job, e, json_error, json_success, request, str |
| 2926-2931 | 6 | `scan_job_status` | `app.route('/scan-jobs/<job_id>')` | _scan_job_snapshot, app, json_error, json_success, scan_jobs, scan_jobs_lock |
| 2935-2948 | 14 | `wlan_scan` | `app.route('/wlan-scan', methods=['POST'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 2952-2969 | 18 | `wlan_connect` | `app.route('/wlan-connect', methods=['POST'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 2973-2985 | 13 | `bluetooth_scan` | `app.route('/bluetooth-scan', methods=['POST'])` | Exception, app, asyncio, bluetooth_action_capability, bluetooth_device_summary, e, get_bluetooth_devices, json_error, json_success, request, str |
| 2989-3012 | 24 | `bluetooth_action` | `app.route('/bluetooth-action', methods=['POST'])` | BluetoothToolUnavailable, Exception, ValueError, _bluetooth_state_updates_for_action, _merge_inventory_device_state, _parse_bluetooth_info_output, app, bluetooth_contextual_actions, bluetooth_device_state, e, find_inventory_device, json_error, json_success, record_bluetooth_action_history, request, run_bluetoothctl_action, str |
| 3016-3031 | 16 | `bluetooth_device_refresh` | `app.route('/bluetooth-device/<address>/refresh', methods=['POST'])` | BluetoothToolUnavailable, Exception, ValueError, _merge_inventory_device_state, _parse_bluetooth_info_output, app, bluetooth_contextual_actions, bluetooth_device_state, e, json_error, json_success, record_bluetooth_action_history, request, run_bluetoothctl_action, str |
| 3035-3039 | 5 | `forget_inventory_route` | `app.route('/inventory/<identifier>/forget', methods=['POST'])` | app, forget_inventory_device, json_error, json_success |
| 3043-3053 | 11 | `spoof_mac_route` | `app.route('/spoof-mac', methods=['POST'])` | app, json_error, json_success, request, spoof_mac |
| 3057-3077 | 21 | `beacon_advertise` | `app.route('/beacon-advertise', methods=['POST'])` | Exception, ValueError, app, beaconSpoof, e, json_error, json_success, missing_fields, parse_int, request, str |
| 3081-3098 | 18 | `deauth_route` | `app.route('/deauth', methods=['POST'])` | Exception, ValueError, app, deauth, e, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, str |
| 3102-3120 | 19 | `evil_twin_lab_route` | `app.route('/evil-twin-lab', methods=['POST'])` | ValueError, app, e, evil_twin_lab_lock, evil_twin_lab_runs, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, save_runtime_state, str |
| 3124-3137 | 14 | `pineap_lab_route` | `app.route('/pineap-lab', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, labs_service, len, missing_fields, normalize_mac, parse_int, pineap_lab_lock, pineap_lab_runs, request, save_runtime_state, str, wifi_utils |
| 3141-3151 | 11 | `handshake_lab_route` | `app.route('/handshake-lab', methods=['POST'])` | ValueError, app, create_evidence_record, e, handshake_lab_lock, handshake_lab_records, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, save_runtime_state, str |
| 3155-3161 | 7 | `export_handshake_lab` | `app.route('/handshake-lab.<fmt>')` | Response, app, handshake_lab_lock, handshake_lab_records, json_error, jsonify, labs_service, time |
| 3165-3184 | 20 | `aireplay_deauth_route` | `app.route('/aireplay-deauth', methods=['POST'])` | Exception, ValueError, aireplay_deauth, app, e, json_error, json_success, missing_fields, parse_int, request, str |
