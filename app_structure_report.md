# Remaining `app.py` structure

Total lines: **3875**
Top-level named nodes: **295**
Decorated route handlers: **126**

## Largest top-level nodes

| Lines | Range | Kind | Name | Decorators |
|---:|---:|---|---|---|
| 77 | 2937-3013 | FunctionDef | `client_detail` | `app.route('/clients/<identifier>')` |
| 55 | 1503-1557 | FunctionDef | `record_passive_observation_analytics` | `` |
| 50 | 700-749 | FunctionDef | `client_intelligence_profile` | `` |
| 45 | 1681-1725 | FunctionDef | `comprehensive_network_device_scan` | `` |
| 44 | 875-918 | FunctionDef | `fingerprint_client_services` | `` |
| 42 | 2620-2661 | FunctionDef | `import_social_profiles` | `app.route('/social-engineering/import', methods=['POST']), social_login_required({'editor', 'admin'})` |
| 40 | 752-791 | FunctionDef | `update_client_metadata` | `` |
| 40 | 1322-1361 | FunctionDef | `discover_upnp_devices` | `` |
| 38 | 164-201 | FunctionDef | `load_runtime_state` | `` |
| 38 | 544-581 | FunctionDef | `enrich_ip_client_display_name` | `` |
| 36 | 1606-1641 | FunctionDef | `_passive_monitor_worker` | `` |
| 35 | 1560-1594 | FunctionDef | `passive_observation_summary` | `` |
| 35 | 1644-1678 | FunctionDef | `set_passive_monitor` | `` |
| 34 | 118-151 | FunctionDef | `runtime_state_snapshot` | `` |
| 34 | 622-655 | FunctionDef | `client_health_summary` | `` |
| 33 | 969-1001 | FunctionDef | `run_scheduled_client_check` | `` |
| 33 | 1766-1798 | FunctionDef | `_run_scan_job` | `` |
| 33 | 2265-2297 | FunctionDef | `social_profile_detail` | `app.route('/social-engineering/profiles/<profile_id>'), social_login_required()` |
| 31 | 1095-1125 | FunctionDef | `inventory_records` | `` |
| 31 | 1879-1909 | FunctionDef | `create_scan_job` | `` |
| 30 | 1848-1877 | FunctionDef | `create_port_scan_job` | `` |
| 29 | 2232-2260 | FunctionDef | `create_social_profile` | `app.route('/social-engineering/profiles', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` |
| 29 | 3095-3123 | FunctionDef | `client_export_route` | `app.route('/clients/<identifier>/export.<fmt>')` |
| 26 | 499-524 | FunctionDef | `_dhcp_lease_display_name` | `` |
| 26 | 1067-1092 | FunctionDef | `inspect_http_services` | `` |
| 26 | 1364-1389 | FunctionDef | `_parse_lldpctl_keyvalue` | `` |
| 26 | 2481-2506 | FunctionDef | `rotate_vault` | `app.route('/vault-rotate', methods=['POST']), social_login_required({'credential_manager', 'admin'})` |
| 25 | 387-411 | FunctionDef | `bluetooth_detail_fields` | `` |
| 25 | 1295-1319 | FunctionDef | `_parse_ssdp_response` | `` |
| 24 | 921-944 | FunctionDef | `save_scheduled_client_check` | `` |
| 24 | 2311-2334 | FunctionDef | `update_social_profile` | `app.route('/social-engineering/profiles/<profile_id>/update', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` |
| 24 | 3441-3464 | FunctionDef | `wireless_network_clients_export` | `app.route('/wireless/network/clients.csv')` |
| 24 | 3673-3696 | FunctionDef | `bluetooth_action` | `app.route('/bluetooth-action', methods=['POST'])` |
| 23 | 597-619 | FunctionDef | `client_timeline` | `` |
| 22 | 851-872 | FunctionDef | `client_relationship_map` | `` |
| 22 | 1248-1269 | FunctionDef | `_parse_mdns_output` | `` |
| 22 | 3035-3056 | FunctionDef | `client_http_inspect` | `app.route('/clients/<identifier>/http-inspect', methods=['POST'])` |
| 21 | 1044-1064 | FunctionDef | `capture_http_preview_thumbnail` | `` |
| 21 | 1272-1292 | FunctionDef | `discover_mdns_services` | `` |
| 21 | 2122-2142 | FunctionDef | `social_auth_setup` | `app.route('/setup', methods=['GET', 'POST'])` |
| 21 | 2551-2571 | FunctionDef | `add_social_profile_attachment` | `app.route('/social-engineering/profiles/<profile_id>/attachments', methods=['POST']), social_login_required({'editor', 'admin'})` |
| 21 | 3238-3258 | FunctionDef | `port_scan_route` | `app.route('/port-scan', methods=['POST'])` |
| 21 | 3741-3761 | FunctionDef | `beacon_advertise` | `app.route('/beacon-advertise', methods=['POST'])` |
| 20 | 947-966 | FunctionDef | `scan_common_client_ports` | `` |
| 20 | 1153-1172 | FunctionDef | `record_scan_devices_for_wireless_network` | `` |
| 20 | 1445-1464 | FunctionDef | `parse_neighbor_table` | `` |
| 20 | 1467-1486 | FunctionDef | `merge_discovered_devices` | `` |
| 20 | 2094-2113 | FunctionDef | `require_application_login` | `app.before_request` |
| 20 | 3291-3310 | FunctionDef | `cancel_job` | `app.route('/jobs/<job_id>/cancel', methods=['POST'])` |
| 20 | 3849-3868 | FunctionDef | `aireplay_deauth_route` | `app.route('/aireplay-deauth', methods=['POST'])` |
| 19 | 667-685 | FunctionDef | `_ttl_os_hint` | `` |
| 19 | 794-812 | FunctionDef | `save_client_baseline` | `` |
| 19 | 1392-1410 | FunctionDef | `discover_lldp_neighbors` | `` |
| 19 | 2013-2031 | FunctionDef | `social_login_required` | `` |
| 19 | 2072-2090 | FunctionDef | `save_social_profile_photo` | `` |
| 19 | 3468-3486 | FunctionDef | `wireless_network_detail` | `app.route('/wireless/network')` |
| 19 | 3786-3804 | FunctionDef | `evil_twin_lab_route` | `app.route('/evil-twin-lab', methods=['POST'])` |
| 18 | 321-338 | FunctionDef | `_merge_inventory_device_state` | `` |
| 18 | 368-385 | FunctionDef | `forget_inventory_device` | `` |
| 18 | 831-848 | FunctionDef | `client_profile_export` | `` |

## Route handlers in source order

| Range | Lines | Name | Decorators | Referenced globals |
|---:|---:|---|---|---|
| 1993-1994 | 2 | `index` | `app.route('/')` | app, current_context, render_template |
| 1998-1999 | 2 | `about` | `app.route('/about')` | app, current_context, render_template |
| 2003-2004 | 2 | `contact_page` | `app.route('/contact')` | app, current_context, render_template |
| 2122-2142 | 21 | `social_auth_setup` | `app.route('/setup', methods=['GET', 'POST'])` | ValueError, app, current_context, exc, json_error, record_social_audit, redirect, render_template, request, save_runtime_state, secrets, session, social_auth_service, social_csrf_token, social_profiles, social_profiles_lock, social_users, social_users_lock, str, url_for |
| 2146-2161 | 16 | `social_auth_login` | `app.route('/login', methods=['GET', 'POST'])` | app, current_context, json_error, record_social_audit, redirect, render_template, request, save_runtime_state, secrets, session, social_auth_service, social_csrf_token, social_users, social_users_lock, str, url_for |
| 2166-2170 | 5 | `social_auth_logout` | `app.route('/logout', methods=['POST']), social_login_required()` | app, record_social_audit, redirect, save_runtime_state, session, social_login_required, url_for |
| 2174-2175 | 2 | `legacy_social_auth_setup` | `app.route('/social-engineering/setup')` | app, redirect, url_for |
| 2179-2180 | 2 | `legacy_social_auth_login` | `app.route('/social-engineering/login')` | app, redirect, url_for |
| 2185-2188 | 4 | `application_users_page` | `app.route('/users'), social_login_required({'admin'})` | app, current_context, dict, render_template, social_csrf_token, social_login_required, social_users, social_users_lock |
| 2193-2205 | 13 | `create_application_user` | `app.route('/users', methods=['POST']), social_login_required({'admin'})` | ValueError, app, current_context, dict, exc, record_social_audit, redirect, render_template, request, save_runtime_state, social_auth_service, social_csrf_token, social_login_required, social_users, social_users_lock, str, url_for |
| 2210-2227 | 18 | `social_engineering_page` | `app.route('/social-engineering'), social_login_required()` | app, current_context, len, owned_social_profiles, recent_social_audit, render_template, request, session, social_csrf_token, social_login_required, social_profile_service, sorted, str |
| 2232-2260 | 29 | `create_social_profile` | `app.route('/social-engineering/profiles', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` | ValueError, app, current_app_user, current_context, exc, len, owned_social_profiles, recent_social_audit, record_social_audit, redirect, render_template, request, save_runtime_state, save_social_profile_photo, session, social_csrf_token, social_login_required, social_profile_service, social_profiles, social_profiles_lock, … |
| 2265-2297 | 33 | `social_profile_detail` | `app.route('/social-engineering/profiles/<profile_id>'), social_login_required()` | app, current_context, current_user_record, find_inventory_device, inventory_records, owned_social_profile, owned_social_profiles, render_template, session, social_csrf_token, social_login_required |
| 2302-2306 | 5 | `social_profile_photo` | `app.route('/social-engineering/profiles/<profile_id>/photo'), social_login_required()` | SOCIAL_PROFILE_PHOTO_DIR, app, owned_social_profile, send_from_directory, social_login_required |
| 2311-2334 | 24 | `update_social_profile` | `app.route('/social-engineering/profiles/<profile_id>/update', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` | KeyError, ValueError, app, current_context, current_user_record, exc, json_error, owned_social_profile, record_social_audit, redirect, render_template, request, save_runtime_state, save_social_profile_photo, session, social_csrf_token, social_login_required, social_profile_service, social_profiles, social_profiles_lock, … |
| 2339-2355 | 17 | `delete_social_profile` | `app.route('/social-engineering/profiles/<profile_id>/delete', methods=['POST']), social_login_required({'admin'})` | SOCIAL_PROFILE_ATTACHMENT_DIR, SOCIAL_PROFILE_PHOTO_DIR, app, json_error, os, owned_social_profile, record_social_audit, redirect, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for |
| 2360-2371 | 12 | `add_social_profile_credential` | `app.route('/social-engineering/profiles/<profile_id>/credentials', methods=['POST']), social_login_required({'credential_manager', 'admin'})` | KeyError, ValueError, app, exc, json_error, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2376-2387 | 12 | `delete_social_profile_credential` | `app.route('/social-engineering/profiles/<profile_id>/credentials/<credential_id>/delete', methods=['POST']), social_login_required({'credential_manager', 'admin'})` | KeyError, app, json_error, owned_social_profile, record_social_audit, redirect, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for |
| 2392-2405 | 14 | `update_social_profile_credential` | `app.route('/social-engineering/profiles/<profile_id>/credentials/<credential_id>/update', methods=['POST']), social_login_required({'credential_manager', 'admin'})` | KeyError, ValueError, app, exc, json_error, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2410-2423 | 14 | `add_social_profile_device` | `app.route('/social-engineering/profiles/<profile_id>/devices', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` | KeyError, ValueError, app, exc, json_error, normalize_mac, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2428-2439 | 12 | `delete_social_profile_device` | `app.route('/social-engineering/profiles/<profile_id>/devices/<device_id>/delete', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` | KeyError, app, json_error, owned_social_profile, record_social_audit, redirect, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for |
| 2444-2457 | 14 | `update_social_profile_device` | `app.route('/social-engineering/profiles/<profile_id>/devices/<device_id>/update', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` | KeyError, ValueError, app, exc, json_error, normalize_mac, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2462-2476 | 15 | `save_vault_verifier` | `app.route('/vault-verifier', methods=['POST']), social_login_required()` | app, current_app_user, json_error, json_success, len, record_social_audit, request, save_runtime_state, social_login_required, social_users, social_users_lock, str |
| 2481-2506 | 26 | `rotate_vault` | `app.route('/vault-rotate', methods=['POST']), social_login_required({'credential_manager', 'admin'})` | any, app, current_app_user, dict, isinstance, json, json_error, json_success, owned_social_profiles, record_social_audit, request, save_runtime_state, set, social_login_required, social_profiles, social_profiles_lock, social_users, social_users_lock, str, time |
| 2511-2520 | 10 | `add_social_profile_relationship` | `app.route('/social-engineering/profiles/<profile_id>/relationships', methods=['POST']), social_login_required({'editor', 'admin'})` | KeyError, ValueError, app, exc, json_error, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2525-2531 | 7 | `delete_social_profile_relationship` | `app.route('/social-engineering/profiles/<profile_id>/relationships/<relationship_id>/delete', methods=['POST']), social_login_required({'editor', 'admin'})` | app, json_error, owned_social_profile, record_social_audit, redirect, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for |
| 2536-2546 | 11 | `merge_social_profiles` | `app.route('/social-engineering/profiles/merge', methods=['POST']), social_login_required({'editor', 'admin'})` | KeyError, ValueError, app, exc, json_error, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2551-2571 | 21 | `add_social_profile_attachment` | `app.route('/social-engineering/profiles/<profile_id>/attachments', methods=['POST']), social_login_required({'editor', 'admin'})` | SOCIAL_PROFILE_ATTACHMENT_DIR, app, hashlib, json_error, len, open, os, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, secure_filename, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for, uuid |
| 2576-2582 | 7 | `download_social_profile_attachment` | `app.route('/social-engineering/profiles/<profile_id>/attachments/<attachment_id>'), social_login_required()` | SOCIAL_PROFILE_ATTACHMENT_DIR, app, json_error, next, owned_social_profile, record_social_audit, send_from_directory, social_login_required |
| 2587-2598 | 12 | `delete_social_profile_attachment` | `app.route('/social-engineering/profiles/<profile_id>/attachments/<attachment_id>/delete', methods=['POST']), social_login_required({'editor', 'admin'})` | SOCIAL_PROFILE_ATTACHMENT_DIR, app, json_error, os, owned_social_profile, record_social_audit, redirect, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for |
| 2603-2615 | 13 | `export_social_profiles` | `app.route('/social-engineering/export'), social_login_required()` | Response, app, csv, io, json, owned_social_profiles, request, social_login_required |
| 2620-2661 | 42 | `import_social_profiles` | `app.route('/social-engineering/import', methods=['POST']), social_login_required({'editor', 'admin'})` | UnicodeDecodeError, ValueError, app, current_app_user, dict, isinstance, json, json_error, len, list, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2666-2674 | 9 | `social_profile_client_audit` | `app.route('/social-engineering/profiles/<profile_id>/audit', methods=['POST']), social_login_required()` | app, json_error, json_success, owned_social_profile, record_social_audit, request, save_runtime_state, social_login_required, str |
| 2678-2691 | 14 | `submit_contact` | `app.route('/submit-contact', methods=['POST'])` | Exception, app, e, json, json_error, json_success, open, request, str, time |
| 2695-2696 | 2 | `favicon` | `app.route('/favicon.ico')` | app, os, send_from_directory |
| 2700-2701 | 2 | `red_team` | `app.route('/red-team')` | app, current_context, render_template |
| 2705-2712 | 8 | `roadmap_page` | `app.route('/roadmap')` | ROADMAP_SECTIONS, app, current_context, remaining_roadmap_items, render_template |
| 2721-2723 | 3 | `adapters` | `app.route('/adapters', methods=['POST'])` | app, jsonify, network_interfaces |
| 2727-2737 | 11 | `adapter_updates` | `app.route('/adapters/updates', methods=['POST'])` | adapter_snapshot, adapter_update_fragments, app, jsonify, network_interfaces, request |
| 2741-2745 | 5 | `export_interfaces_json` | `app.route('/export/interfaces.json')` | app, jsonify, network_interfaces, time |
| 2749-2754 | 6 | `export_capabilities_json` | `app.route('/export/capabilities.json')` | app, build_capabilities, jsonify, time |
| 2758-2759 | 2 | `evidence_page` | `app.route('/evidence')` | app, current_context, evidence_records, render_template |
| 2763-2778 | 16 | `create_evidence_route` | `app.route('/evidence', methods=['POST'])` | ValueError, app, create_evidence_record, current_context, e, evidence_records, json_error, json_success, render_template, request, str |
| 2782-2790 | 9 | `export_evidence` | `app.route('/evidence.<fmt>')` | Response, app, evidence_as_csv, evidence_as_markdown, evidence_records, json_error, jsonify, time |
| 2794-2802 | 9 | `download_evidence_file` | `app.route('/evidence/<evidence_id>/download')` | EVIDENCE_DIR, app, evidence_vault, evidence_vault_lock, json_error, next, os, send_file |
| 2806-2807 | 2 | `reports_page` | `app.route('/reports')` | app, build_report_data, current_context, render_template |
| 2811-2821 | 11 | `export_report` | `app.route('/reports.<fmt>')` | Response, app, build_report_data, json_error, jsonify, render_template, report_as_csv, report_as_markdown |
| 2825-2826 | 2 | `network_scan` | `app.route('/network-scan')` | app, current_context, render_template |
| 2830-2839 | 10 | `inventory_page` | `app.route('/inventory')` | app, current_context, inventory_records, manufacturer_insights, render_template |
| 2843-2844 | 2 | `inventory_export_json` | `app.route('/inventory/export.json')` | app, inventory_export_payload, jsonify |
| 2848-2862 | 15 | `inventory_import_route` | `app.route('/inventory/import', methods=['POST'])` | ValueError, app, e, import_inventory_payload, inventory_page, json, json_error, json_success, request, str |
| 2866-2867 | 2 | `alerts_page` | `app.route('/alerts')` | alert_records, app, current_context, render_template |
| 2871-2873 | 3 | `alerts_status` | `app.route('/alerts/status')` | alert_records, app, json_success, len |
| 2877-2881 | 5 | `mark_alert_read` | `app.route('/alerts/<alert_id>/read', methods=['POST'])` | alerts_service, app, json_error, json_success, new_device_alerts, new_device_alerts_lock |
| 2885-2886 | 2 | `mark_all_alerts_read` | `app.route('/alerts/read-all', methods=['POST'])` | alerts_service, app, json_success, new_device_alerts, new_device_alerts_lock |
| 2890-2891 | 2 | `port_scan_page` | `app.route('/port-scan')` | app, current_context, render_template |
| 2895-2896 | 2 | `jobs_page` | `app.route('/jobs')` | app, current_context, render_template |
| 2900-2901 | 2 | `traceroute_page` | `app.route('/traceroute')` | app, current_context, render_template |
| 2905-2906 | 2 | `diagnostics_page` | `app.route('/diagnostics')` | app, current_context, render_template |
| 2910-2911 | 2 | `service_discovery_page` | `app.route('/service-discovery')` | app, current_context, render_template |
| 2915-2916 | 2 | `advanced_diagnostics_page` | `app.route('/advanced-diagnostics')` | app, current_context, render_template |
| 2920-2922 | 3 | `http_preview_file` | `app.route('/http-previews/<path:filename>')` | HTTP_PREVIEW_DIR, app, send_from_directory |
| 2926-2933 | 8 | `client_service_detail` | `app.route('/clients/<identifier>/services/<int:port>')` | app, current_context, dict, enrich_ip_client_display_name, find_inventory_device, int, next, render_template |
| 2937-3013 | 77 | `client_detail` | `app.route('/clients/<identifier>')` | app, bluetooth_action_capability, bluetooth_action_history, bluetooth_adapter_choices, bluetooth_contextual_actions, bluetooth_detail_fields, client_baseline_diff, client_health_summary, client_reachability_history, client_relationship_map, client_timeline, current_context, display_name_for_inventory_device, enrich_ip_client_display_name, find_inventory_device, get_ip_by_mac, get_mac_by_ip, is_client_watched, lookup_manufacturer, normalize_mac, … |
| 3017-3031 | 15 | `watch_client` | `app.route('/clients/<identifier>/watch', methods=['POST'])` | app, append_client_timeline_event, json_error, json_success, request, save_runtime_state, str, watched_clients |
| 3035-3056 | 22 | `client_http_inspect` | `app.route('/clients/<identifier>/http-inspect', methods=['POST'])` | ValueError, any, app, append_client_timeline_event, e, find_inventory_device, inspect_http_services, json_error, json_success, len, parse_int, request, set, sorted, str |
| 3060-3074 | 15 | `client_summary_route` | `app.route('/clients/<identifier>/summary')` | app, display_name_for_inventory_device, enrich_ip_client_display_name, find_inventory_device, json_success |
| 3078-3084 | 7 | `client_metadata_route` | `app.route('/clients/<identifier>/metadata', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, str, update_client_metadata |
| 3088-3091 | 4 | `client_baseline_route` | `app.route('/clients/<identifier>/baseline', methods=['POST'])` | app, client_baseline_diff, json_success, save_client_baseline |
| 3095-3123 | 29 | `client_export_route` | `app.route('/clients/<identifier>/export.<fmt>')` | Response, app, client_profile_export, json_error, jsonify |
| 3127-3128 | 2 | `client_relationship_map_route` | `app.route('/clients/<identifier>/relationship-map')` | app, client_relationship_map, json_success |
| 3132-3134 | 3 | `client_intelligence_route` | `app.route('/clients/<identifier>/intelligence', methods=['POST'])` | app, client_intelligence_profile, json_success, request |
| 3138-3139 | 2 | `client_fingerprint_route` | `app.route('/clients/<identifier>/fingerprint', methods=['POST'])` | app, fingerprint_client_services, json_success |
| 3143-3148 | 6 | `client_scheduled_check_route` | `app.route('/clients/<identifier>/scheduled-check', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, save_scheduled_client_check, str |
| 3152-3157 | 6 | `client_scheduled_check_run_route` | `app.route('/clients/<identifier>/scheduled-check/run', methods=['POST'])` | ValueError, app, e, json_error, json_success, run_scheduled_client_check, str |
| 3161-3163 | 3 | `scheduled_checks_run_due_route` | `app.route('/scheduled-checks/run-due', methods=['POST'])` | app, json_success, len, run_due_scheduled_client_checks |
| 3167-3176 | 10 | `active_scan_route` | `app.route('/active-scan', methods=['POST'])` | active_scan, app, classify_scan_results, json_error, jsonify, record_inventory_devices, record_scan_devices_for_wireless_network, request |
| 3180-3190 | 11 | `passive_scan_route` | `app.route('/passive-scan', methods=['POST'])` | app, classify_scan_results, json_error, jsonify, passive_scan, record_inventory_devices, record_passive_observation_analytics, record_scan_devices_for_wireless_network, request |
| 3194-3196 | 3 | `passive_analytics_route` | `app.route('/passive-analytics.json')` | app, json_success, passive_observation_summary, request |
| 3200-3203 | 4 | `passive_monitor_status_route` | `app.route('/passive-monitor/status')` | app, jsonify, passive_monitor_snapshot, request |
| 3207-3216 | 10 | `passive_monitor_toggle_route` | `app.route('/passive-monitor/toggle', methods=['POST'])` | ValueError, app, exc, json_error, json_success, request, set_passive_monitor, str |
| 3220-3234 | 15 | `comprehensive_scan_route` | `app.route('/comprehensive-scan', methods=['POST'])` | ValueError, app, comprehensive_network_device_scan, e, json_error, json_success, record_scan_devices_for_wireless_network, request, str |
| 3238-3258 | 21 | `port_scan_route` | `app.route('/port-scan', methods=['POST'])` | PortScanError, ValueError, app, describe_open_ports, e, enrich_web_port_metadata, json_error, jsonify, missing_fields, parse_int, record_device_open_ports, request, scan_ports, str |
| 3262-3272 | 11 | `start_port_scan_job` | `app.route('/port-scan-jobs', methods=['POST'])` | ValueError, app, create_port_scan_job, e, json_error, json_success, missing_fields, parse_int, request, str |
| 3276-3281 | 6 | `port_scan_job_status` | `app.route('/port-scan-jobs/<job_id>')` | _port_scan_job_snapshot, app, json_error, json_success, port_scan_jobs, port_scan_jobs_lock |
| 3285-3287 | 3 | `jobs_status` | `app.route('/jobs/status')` | all_job_snapshots, app, json_success, len |
| 3291-3310 | 20 | `cancel_job` | `app.route('/jobs/<job_id>/cancel', methods=['POST'])` | _port_scan_job_snapshot, _scan_job_snapshot, app, json_error, json_success, port_scan_jobs, port_scan_jobs_lock, scan_jobs, scan_jobs_lock, time |
| 3314-3320 | 7 | `traceroute_route` | `app.route('/traceroute', methods=['POST'])` | app, json_error, jsonify, request, traceroute |
| 3324-3331 | 8 | `ping_route` | `app.route('/ping', methods=['POST'])` | ValueError, app, e, json_error, json_success, ping_history, request, run_ping_check, str, subprocess |
| 3335-3340 | 6 | `ping_sweep_route` | `app.route('/ping-sweep', methods=['POST'])` | ValueError, app, e, json_error, json_success, ping_history, request, run_ping_sweep, str |
| 3344-3346 | 3 | `route_diagnostics_route` | `app.route('/route-diagnostics', methods=['POST'])` | app, build_route_diagnostics, json_success, request |
| 3350-3352 | 3 | `mdns_discovery_route` | `app.route('/mdns-discovery', methods=['POST'])` | app, discover_mdns_services, json_success, request |
| 3356-3362 | 7 | `upnp_discovery_route` | `app.route('/upnp-discovery', methods=['POST'])` | ValueError, app, discover_upnp_devices, e, json_error, json_success, max, min, parse_int, request, str |
| 3366-3368 | 3 | `neighbor_discovery_route` | `app.route('/neighbor-discovery', methods=['POST'])` | app, discover_lldp_neighbors, json_success, request |
| 3372-3374 | 3 | `vlan_discovery_route` | `app.route('/vlan-discovery', methods=['POST'])` | app, discover_vlan_context, json_success, request |
| 3378-3379 | 2 | `egress_diagnostics_route` | `app.route('/egress-diagnostics', methods=['POST'])` | app, build_egress_diagnostics, json_success, request |
| 3383-3388 | 6 | `iperf3_test_route` | `app.route('/iperf3-test', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, run_iperf3_test, str, subprocess |
| 3392-3399 | 8 | `snmp_discovery_route` | `app.route('/snmp-discovery', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, run_snmp_inventory, str |
| 3403-3405 | 3 | `ipv6_assessment_route` | `app.route('/ipv6-assessment', methods=['POST'])` | app, json_success, request, run_ipv6_assessment |
| 3409-3424 | 16 | `wireless_network_client_label_route` | `app.route('/wireless/network/label', methods=['POST'])` | app, json_error, json_success, request, save_runtime_state, wireless_network_client_label_key, wireless_network_labels |
| 3428-3437 | 10 | `wireless_network_clients_json` | `app.route('/wireless/network/clients.json')` | app, json_success, merge_wireless_network_clients, request, wifi_utils |
| 3441-3464 | 24 | `wireless_network_clients_export` | `app.route('/wireless/network/clients.csv')` | Response, app, csv, io, json, merge_wireless_network_clients, request, secure_filename, str, wifi_utils |
| 3468-3486 | 19 | `wireless_network_detail` | `app.route('/wireless/network')` | app, current_context, merge_wireless_network_clients, render_template, request, wifi_utils |
| 3490-3503 | 14 | `interface_power_state` | `app.route('/interfaces/<interface_name>/state', methods=['POST'])` | Exception, ValueError, app, exc, getattr, json_error, json_success, network_interfaces, next, request, set_interface_power_state, str |
| 3506-3513 | 8 | `interfaces_by_type` | `app.route('/<interface_type>')` | app, current_context, network_interfaces, render_template |
| 3517-3529 | 13 | `interface_detail` | `app.route('/<interface_type>/<interface_name>')` | app, bluetooth_phone_card_context, current_context, network_interfaces, next, render_template |
| 3533-3547 | 15 | `syn_flood` | `app.route('/syn-flood', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, missing_fields, networkAttacks, parse_int, request, str |
| 3551-3564 | 14 | `syn_flood_broadcast` | `app.route('/syn-flood-broadcast', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, missing_fields, networkAttacks, parse_int, request, str |
| 3568-3578 | 11 | `wlan_modes` | `app.route('/wlan-modes', methods=['GET'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 3582-3596 | 15 | `wlan_mode` | `app.route('/wlan-mode', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, request, str, wifi_utils |
| 3600-3606 | 7 | `start_scan_job` | `app.route('/scan-jobs', methods=['POST'])` | ValueError, app, create_scan_job, e, json_error, json_success, request, str |
| 3610-3615 | 6 | `scan_job_status` | `app.route('/scan-jobs/<job_id>')` | _scan_job_snapshot, app, json_error, json_success, scan_jobs, scan_jobs_lock |
| 3619-3632 | 14 | `wlan_scan` | `app.route('/wlan-scan', methods=['POST'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 3636-3653 | 18 | `wlan_connect` | `app.route('/wlan-connect', methods=['POST'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 3657-3669 | 13 | `bluetooth_scan` | `app.route('/bluetooth-scan', methods=['POST'])` | Exception, app, asyncio, bluetooth_action_capability, bluetooth_device_summary, e, get_bluetooth_devices, json_error, json_success, request, str |
| 3673-3696 | 24 | `bluetooth_action` | `app.route('/bluetooth-action', methods=['POST'])` | BluetoothToolUnavailable, Exception, ValueError, _bluetooth_state_updates_for_action, _merge_inventory_device_state, _parse_bluetooth_info_output, app, bluetooth_contextual_actions, bluetooth_device_state, e, find_inventory_device, json_error, json_success, record_bluetooth_action_history, request, run_bluetoothctl_action, str |
| 3700-3715 | 16 | `bluetooth_device_refresh` | `app.route('/bluetooth-device/<address>/refresh', methods=['POST'])` | BluetoothToolUnavailable, Exception, ValueError, _merge_inventory_device_state, _parse_bluetooth_info_output, app, bluetooth_contextual_actions, bluetooth_device_state, e, json_error, json_success, record_bluetooth_action_history, request, run_bluetoothctl_action, str |
| 3719-3723 | 5 | `forget_inventory_route` | `app.route('/inventory/<identifier>/forget', methods=['POST'])` | app, forget_inventory_device, json_error, json_success |
| 3727-3737 | 11 | `spoof_mac_route` | `app.route('/spoof-mac', methods=['POST'])` | app, json_error, json_success, request, spoof_mac |
| 3741-3761 | 21 | `beacon_advertise` | `app.route('/beacon-advertise', methods=['POST'])` | Exception, ValueError, app, beaconSpoof, e, json_error, json_success, missing_fields, parse_int, request, str |
| 3765-3782 | 18 | `deauth_route` | `app.route('/deauth', methods=['POST'])` | Exception, ValueError, app, deauth, e, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, str |
| 3786-3804 | 19 | `evil_twin_lab_route` | `app.route('/evil-twin-lab', methods=['POST'])` | ValueError, app, e, evil_twin_lab_lock, evil_twin_lab_runs, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, save_runtime_state, str |
| 3808-3821 | 14 | `pineap_lab_route` | `app.route('/pineap-lab', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, labs_service, len, missing_fields, normalize_mac, parse_int, pineap_lab_lock, pineap_lab_runs, request, save_runtime_state, str, wifi_utils |
| 3825-3835 | 11 | `handshake_lab_route` | `app.route('/handshake-lab', methods=['POST'])` | ValueError, app, create_evidence_record, e, handshake_lab_lock, handshake_lab_records, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, save_runtime_state, str |
| 3839-3845 | 7 | `export_handshake_lab` | `app.route('/handshake-lab.<fmt>')` | Response, app, handshake_lab_lock, handshake_lab_records, json_error, jsonify, labs_service, time |
| 3849-3868 | 20 | `aireplay_deauth_route` | `app.route('/aireplay-deauth', methods=['POST'])` | Exception, ValueError, aireplay_deauth, app, e, json_error, json_success, missing_fields, parse_int, request, str |
