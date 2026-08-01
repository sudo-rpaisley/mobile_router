# Remaining `app.py` structure

Total lines: **3736**
Top-level named nodes: **288**
Decorated route handlers: **126**

## Largest top-level nodes

| Lines | Range | Kind | Name | Decorators |
|---:|---:|---|---|---|
| 77 | 2798-2874 | FunctionDef | `client_detail` | `app.route('/clients/<identifier>')` |
| 55 | 1364-1418 | FunctionDef | `record_passive_observation_analytics` | `` |
| 50 | 700-749 | FunctionDef | `client_intelligence_profile` | `` |
| 45 | 1542-1586 | FunctionDef | `comprehensive_network_device_scan` | `` |
| 44 | 875-918 | FunctionDef | `fingerprint_client_services` | `` |
| 42 | 2481-2522 | FunctionDef | `import_social_profiles` | `app.route('/social-engineering/import', methods=['POST']), social_login_required({'editor', 'admin'})` |
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
| 33 | 2126-2158 | FunctionDef | `social_profile_detail` | `app.route('/social-engineering/profiles/<profile_id>'), social_login_required()` |
| 31 | 1095-1125 | FunctionDef | `inventory_records` | `` |
| 31 | 1740-1770 | FunctionDef | `create_scan_job` | `` |
| 30 | 1709-1738 | FunctionDef | `create_port_scan_job` | `` |
| 29 | 2093-2121 | FunctionDef | `create_social_profile` | `app.route('/social-engineering/profiles', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` |
| 29 | 2956-2984 | FunctionDef | `client_export_route` | `app.route('/clients/<identifier>/export.<fmt>')` |
| 26 | 499-524 | FunctionDef | `_dhcp_lease_display_name` | `` |
| 26 | 1067-1092 | FunctionDef | `inspect_http_services` | `` |
| 26 | 2342-2367 | FunctionDef | `rotate_vault` | `app.route('/vault-rotate', methods=['POST']), social_login_required({'credential_manager', 'admin'})` |
| 25 | 387-411 | FunctionDef | `bluetooth_detail_fields` | `` |
| 24 | 921-944 | FunctionDef | `save_scheduled_client_check` | `` |
| 24 | 2172-2195 | FunctionDef | `update_social_profile` | `app.route('/social-engineering/profiles/<profile_id>/update', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` |
| 24 | 3302-3325 | FunctionDef | `wireless_network_clients_export` | `app.route('/wireless/network/clients.csv')` |
| 24 | 3534-3557 | FunctionDef | `bluetooth_action` | `app.route('/bluetooth-action', methods=['POST'])` |
| 23 | 597-619 | FunctionDef | `client_timeline` | `` |
| 22 | 851-872 | FunctionDef | `client_relationship_map` | `` |
| 22 | 2896-2917 | FunctionDef | `client_http_inspect` | `app.route('/clients/<identifier>/http-inspect', methods=['POST'])` |
| 21 | 1044-1064 | FunctionDef | `capture_http_preview_thumbnail` | `` |
| 21 | 1246-1266 | FunctionDef | `discover_mdns_services` | `` |
| 21 | 1983-2003 | FunctionDef | `social_auth_setup` | `app.route('/setup', methods=['GET', 'POST'])` |
| 21 | 2412-2432 | FunctionDef | `add_social_profile_attachment` | `app.route('/social-engineering/profiles/<profile_id>/attachments', methods=['POST']), social_login_required({'editor', 'admin'})` |
| 21 | 3099-3119 | FunctionDef | `port_scan_route` | `app.route('/port-scan', methods=['POST'])` |
| 21 | 3602-3622 | FunctionDef | `beacon_advertise` | `app.route('/beacon-advertise', methods=['POST'])` |
| 20 | 947-966 | FunctionDef | `scan_common_client_ports` | `` |
| 20 | 1153-1172 | FunctionDef | `record_scan_devices_for_wireless_network` | `` |
| 20 | 1955-1974 | FunctionDef | `require_application_login` | `app.before_request` |
| 20 | 3152-3171 | FunctionDef | `cancel_job` | `app.route('/jobs/<job_id>/cancel', methods=['POST'])` |
| 20 | 3710-3729 | FunctionDef | `aireplay_deauth_route` | `app.route('/aireplay-deauth', methods=['POST'])` |
| 19 | 667-685 | FunctionDef | `_ttl_os_hint` | `` |
| 19 | 794-812 | FunctionDef | `save_client_baseline` | `` |
| 19 | 1311-1329 | FunctionDef | `discover_lldp_neighbors` | `` |
| 19 | 1874-1892 | FunctionDef | `social_login_required` | `` |
| 19 | 1933-1951 | FunctionDef | `save_social_profile_photo` | `` |
| 19 | 3329-3347 | FunctionDef | `wireless_network_detail` | `app.route('/wireless/network')` |
| 19 | 3647-3665 | FunctionDef | `evil_twin_lab_route` | `app.route('/evil-twin-lab', methods=['POST'])` |
| 18 | 321-338 | FunctionDef | `_merge_inventory_device_state` | `` |
| 18 | 368-385 | FunctionDef | `forget_inventory_device` | `` |
| 18 | 831-848 | FunctionDef | `client_profile_export` | `` |
| 18 | 1790-1807 | FunctionDef | `bluetooth_phone_card_context` | `` |
| 18 | 2071-2088 | FunctionDef | `social_engineering_page` | `app.route('/social-engineering'), social_login_required()` |
| 18 | 3497-3514 | FunctionDef | `wlan_connect` | `app.route('/wlan-connect', methods=['POST'])` |
| 18 | 3626-3643 | FunctionDef | `deauth_route` | `app.route('/deauth', methods=['POST'])` |
| 17 | 302-318 | FunctionDef | `record_bluetooth_action_history` | `` |

## Route handlers in source order

| Range | Lines | Name | Decorators | Referenced globals |
|---:|---:|---|---|---|
| 1854-1855 | 2 | `index` | `app.route('/')` | app, current_context, render_template |
| 1859-1860 | 2 | `about` | `app.route('/about')` | app, current_context, render_template |
| 1864-1865 | 2 | `contact_page` | `app.route('/contact')` | app, current_context, render_template |
| 1983-2003 | 21 | `social_auth_setup` | `app.route('/setup', methods=['GET', 'POST'])` | ValueError, app, current_context, exc, json_error, record_social_audit, redirect, render_template, request, save_runtime_state, secrets, session, social_auth_service, social_csrf_token, social_profiles, social_profiles_lock, social_users, social_users_lock, str, url_for |
| 2007-2022 | 16 | `social_auth_login` | `app.route('/login', methods=['GET', 'POST'])` | app, current_context, json_error, record_social_audit, redirect, render_template, request, save_runtime_state, secrets, session, social_auth_service, social_csrf_token, social_users, social_users_lock, str, url_for |
| 2027-2031 | 5 | `social_auth_logout` | `app.route('/logout', methods=['POST']), social_login_required()` | app, record_social_audit, redirect, save_runtime_state, session, social_login_required, url_for |
| 2035-2036 | 2 | `legacy_social_auth_setup` | `app.route('/social-engineering/setup')` | app, redirect, url_for |
| 2040-2041 | 2 | `legacy_social_auth_login` | `app.route('/social-engineering/login')` | app, redirect, url_for |
| 2046-2049 | 4 | `application_users_page` | `app.route('/users'), social_login_required({'admin'})` | app, current_context, dict, render_template, social_csrf_token, social_login_required, social_users, social_users_lock |
| 2054-2066 | 13 | `create_application_user` | `app.route('/users', methods=['POST']), social_login_required({'admin'})` | ValueError, app, current_context, dict, exc, record_social_audit, redirect, render_template, request, save_runtime_state, social_auth_service, social_csrf_token, social_login_required, social_users, social_users_lock, str, url_for |
| 2071-2088 | 18 | `social_engineering_page` | `app.route('/social-engineering'), social_login_required()` | app, current_context, len, owned_social_profiles, recent_social_audit, render_template, request, session, social_csrf_token, social_login_required, social_profile_service, sorted, str |
| 2093-2121 | 29 | `create_social_profile` | `app.route('/social-engineering/profiles', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` | ValueError, app, current_app_user, current_context, exc, len, owned_social_profiles, recent_social_audit, record_social_audit, redirect, render_template, request, save_runtime_state, save_social_profile_photo, session, social_csrf_token, social_login_required, social_profile_service, social_profiles, social_profiles_lock, … |
| 2126-2158 | 33 | `social_profile_detail` | `app.route('/social-engineering/profiles/<profile_id>'), social_login_required()` | app, current_context, current_user_record, find_inventory_device, inventory_records, owned_social_profile, owned_social_profiles, render_template, session, social_csrf_token, social_login_required |
| 2163-2167 | 5 | `social_profile_photo` | `app.route('/social-engineering/profiles/<profile_id>/photo'), social_login_required()` | SOCIAL_PROFILE_PHOTO_DIR, app, owned_social_profile, send_from_directory, social_login_required |
| 2172-2195 | 24 | `update_social_profile` | `app.route('/social-engineering/profiles/<profile_id>/update', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` | KeyError, ValueError, app, current_context, current_user_record, exc, json_error, owned_social_profile, record_social_audit, redirect, render_template, request, save_runtime_state, save_social_profile_photo, session, social_csrf_token, social_login_required, social_profile_service, social_profiles, social_profiles_lock, … |
| 2200-2216 | 17 | `delete_social_profile` | `app.route('/social-engineering/profiles/<profile_id>/delete', methods=['POST']), social_login_required({'admin'})` | SOCIAL_PROFILE_ATTACHMENT_DIR, SOCIAL_PROFILE_PHOTO_DIR, app, json_error, os, owned_social_profile, record_social_audit, redirect, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for |
| 2221-2232 | 12 | `add_social_profile_credential` | `app.route('/social-engineering/profiles/<profile_id>/credentials', methods=['POST']), social_login_required({'credential_manager', 'admin'})` | KeyError, ValueError, app, exc, json_error, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2237-2248 | 12 | `delete_social_profile_credential` | `app.route('/social-engineering/profiles/<profile_id>/credentials/<credential_id>/delete', methods=['POST']), social_login_required({'credential_manager', 'admin'})` | KeyError, app, json_error, owned_social_profile, record_social_audit, redirect, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for |
| 2253-2266 | 14 | `update_social_profile_credential` | `app.route('/social-engineering/profiles/<profile_id>/credentials/<credential_id>/update', methods=['POST']), social_login_required({'credential_manager', 'admin'})` | KeyError, ValueError, app, exc, json_error, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2271-2284 | 14 | `add_social_profile_device` | `app.route('/social-engineering/profiles/<profile_id>/devices', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` | KeyError, ValueError, app, exc, json_error, normalize_mac, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2289-2300 | 12 | `delete_social_profile_device` | `app.route('/social-engineering/profiles/<profile_id>/devices/<device_id>/delete', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` | KeyError, app, json_error, owned_social_profile, record_social_audit, redirect, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for |
| 2305-2318 | 14 | `update_social_profile_device` | `app.route('/social-engineering/profiles/<profile_id>/devices/<device_id>/update', methods=['POST']), social_login_required({'editor', 'credential_manager', 'admin'})` | KeyError, ValueError, app, exc, json_error, normalize_mac, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2323-2337 | 15 | `save_vault_verifier` | `app.route('/vault-verifier', methods=['POST']), social_login_required()` | app, current_app_user, json_error, json_success, len, record_social_audit, request, save_runtime_state, social_login_required, social_users, social_users_lock, str |
| 2342-2367 | 26 | `rotate_vault` | `app.route('/vault-rotate', methods=['POST']), social_login_required({'credential_manager', 'admin'})` | any, app, current_app_user, dict, isinstance, json, json_error, json_success, owned_social_profiles, record_social_audit, request, save_runtime_state, set, social_login_required, social_profiles, social_profiles_lock, social_users, social_users_lock, str, time |
| 2372-2381 | 10 | `add_social_profile_relationship` | `app.route('/social-engineering/profiles/<profile_id>/relationships', methods=['POST']), social_login_required({'editor', 'admin'})` | KeyError, ValueError, app, exc, json_error, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2386-2392 | 7 | `delete_social_profile_relationship` | `app.route('/social-engineering/profiles/<profile_id>/relationships/<relationship_id>/delete', methods=['POST']), social_login_required({'editor', 'admin'})` | app, json_error, owned_social_profile, record_social_audit, redirect, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for |
| 2397-2407 | 11 | `merge_social_profiles` | `app.route('/social-engineering/profiles/merge', methods=['POST']), social_login_required({'editor', 'admin'})` | KeyError, ValueError, app, exc, json_error, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2412-2432 | 21 | `add_social_profile_attachment` | `app.route('/social-engineering/profiles/<profile_id>/attachments', methods=['POST']), social_login_required({'editor', 'admin'})` | SOCIAL_PROFILE_ATTACHMENT_DIR, app, hashlib, json_error, len, open, os, owned_social_profile, record_social_audit, redirect, request, save_runtime_state, secure_filename, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for, uuid |
| 2437-2443 | 7 | `download_social_profile_attachment` | `app.route('/social-engineering/profiles/<profile_id>/attachments/<attachment_id>'), social_login_required()` | SOCIAL_PROFILE_ATTACHMENT_DIR, app, json_error, next, owned_social_profile, record_social_audit, send_from_directory, social_login_required |
| 2448-2459 | 12 | `delete_social_profile_attachment` | `app.route('/social-engineering/profiles/<profile_id>/attachments/<attachment_id>/delete', methods=['POST']), social_login_required({'editor', 'admin'})` | SOCIAL_PROFILE_ATTACHMENT_DIR, app, json_error, os, owned_social_profile, record_social_audit, redirect, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, url_for |
| 2464-2476 | 13 | `export_social_profiles` | `app.route('/social-engineering/export'), social_login_required()` | Response, app, csv, io, json, owned_social_profiles, request, social_login_required |
| 2481-2522 | 42 | `import_social_profiles` | `app.route('/social-engineering/import', methods=['POST']), social_login_required({'editor', 'admin'})` | UnicodeDecodeError, ValueError, app, current_app_user, dict, isinstance, json, json_error, len, list, record_social_audit, redirect, request, save_runtime_state, social_login_required, social_profile_service, social_profiles, social_profiles_lock, str, url_for |
| 2527-2535 | 9 | `social_profile_client_audit` | `app.route('/social-engineering/profiles/<profile_id>/audit', methods=['POST']), social_login_required()` | app, json_error, json_success, owned_social_profile, record_social_audit, request, save_runtime_state, social_login_required, str |
| 2539-2552 | 14 | `submit_contact` | `app.route('/submit-contact', methods=['POST'])` | Exception, app, e, json, json_error, json_success, open, request, str, time |
| 2556-2557 | 2 | `favicon` | `app.route('/favicon.ico')` | app, os, send_from_directory |
| 2561-2562 | 2 | `red_team` | `app.route('/red-team')` | app, current_context, render_template |
| 2566-2573 | 8 | `roadmap_page` | `app.route('/roadmap')` | ROADMAP_SECTIONS, app, current_context, remaining_roadmap_items, render_template |
| 2582-2584 | 3 | `adapters` | `app.route('/adapters', methods=['POST'])` | app, jsonify, network_interfaces |
| 2588-2598 | 11 | `adapter_updates` | `app.route('/adapters/updates', methods=['POST'])` | adapter_snapshot, adapter_update_fragments, app, jsonify, network_interfaces, request |
| 2602-2606 | 5 | `export_interfaces_json` | `app.route('/export/interfaces.json')` | app, jsonify, network_interfaces, time |
| 2610-2615 | 6 | `export_capabilities_json` | `app.route('/export/capabilities.json')` | app, build_capabilities, jsonify, time |
| 2619-2620 | 2 | `evidence_page` | `app.route('/evidence')` | app, current_context, evidence_records, render_template |
| 2624-2639 | 16 | `create_evidence_route` | `app.route('/evidence', methods=['POST'])` | ValueError, app, create_evidence_record, current_context, e, evidence_records, json_error, json_success, render_template, request, str |
| 2643-2651 | 9 | `export_evidence` | `app.route('/evidence.<fmt>')` | Response, app, evidence_as_csv, evidence_as_markdown, evidence_records, json_error, jsonify, time |
| 2655-2663 | 9 | `download_evidence_file` | `app.route('/evidence/<evidence_id>/download')` | EVIDENCE_DIR, app, evidence_vault, evidence_vault_lock, json_error, next, os, send_file |
| 2667-2668 | 2 | `reports_page` | `app.route('/reports')` | app, build_report_data, current_context, render_template |
| 2672-2682 | 11 | `export_report` | `app.route('/reports.<fmt>')` | Response, app, build_report_data, json_error, jsonify, render_template, report_as_csv, report_as_markdown |
| 2686-2687 | 2 | `network_scan` | `app.route('/network-scan')` | app, current_context, render_template |
| 2691-2700 | 10 | `inventory_page` | `app.route('/inventory')` | app, current_context, inventory_records, manufacturer_insights, render_template |
| 2704-2705 | 2 | `inventory_export_json` | `app.route('/inventory/export.json')` | app, inventory_export_payload, jsonify |
| 2709-2723 | 15 | `inventory_import_route` | `app.route('/inventory/import', methods=['POST'])` | ValueError, app, e, import_inventory_payload, inventory_page, json, json_error, json_success, request, str |
| 2727-2728 | 2 | `alerts_page` | `app.route('/alerts')` | alert_records, app, current_context, render_template |
| 2732-2734 | 3 | `alerts_status` | `app.route('/alerts/status')` | alert_records, app, json_success, len |
| 2738-2742 | 5 | `mark_alert_read` | `app.route('/alerts/<alert_id>/read', methods=['POST'])` | alerts_service, app, json_error, json_success, new_device_alerts, new_device_alerts_lock |
| 2746-2747 | 2 | `mark_all_alerts_read` | `app.route('/alerts/read-all', methods=['POST'])` | alerts_service, app, json_success, new_device_alerts, new_device_alerts_lock |
| 2751-2752 | 2 | `port_scan_page` | `app.route('/port-scan')` | app, current_context, render_template |
| 2756-2757 | 2 | `jobs_page` | `app.route('/jobs')` | app, current_context, render_template |
| 2761-2762 | 2 | `traceroute_page` | `app.route('/traceroute')` | app, current_context, render_template |
| 2766-2767 | 2 | `diagnostics_page` | `app.route('/diagnostics')` | app, current_context, render_template |
| 2771-2772 | 2 | `service_discovery_page` | `app.route('/service-discovery')` | app, current_context, render_template |
| 2776-2777 | 2 | `advanced_diagnostics_page` | `app.route('/advanced-diagnostics')` | app, current_context, render_template |
| 2781-2783 | 3 | `http_preview_file` | `app.route('/http-previews/<path:filename>')` | HTTP_PREVIEW_DIR, app, send_from_directory |
| 2787-2794 | 8 | `client_service_detail` | `app.route('/clients/<identifier>/services/<int:port>')` | app, current_context, dict, enrich_ip_client_display_name, find_inventory_device, int, next, render_template |
| 2798-2874 | 77 | `client_detail` | `app.route('/clients/<identifier>')` | app, bluetooth_action_capability, bluetooth_action_history, bluetooth_adapter_choices, bluetooth_contextual_actions, bluetooth_detail_fields, client_baseline_diff, client_health_summary, client_reachability_history, client_relationship_map, client_timeline, current_context, display_name_for_inventory_device, enrich_ip_client_display_name, find_inventory_device, get_ip_by_mac, get_mac_by_ip, is_client_watched, lookup_manufacturer, normalize_mac, … |
| 2878-2892 | 15 | `watch_client` | `app.route('/clients/<identifier>/watch', methods=['POST'])` | app, append_client_timeline_event, json_error, json_success, request, save_runtime_state, str, watched_clients |
| 2896-2917 | 22 | `client_http_inspect` | `app.route('/clients/<identifier>/http-inspect', methods=['POST'])` | ValueError, any, app, append_client_timeline_event, e, find_inventory_device, inspect_http_services, json_error, json_success, len, parse_int, request, set, sorted, str |
| 2921-2935 | 15 | `client_summary_route` | `app.route('/clients/<identifier>/summary')` | app, display_name_for_inventory_device, enrich_ip_client_display_name, find_inventory_device, json_success |
| 2939-2945 | 7 | `client_metadata_route` | `app.route('/clients/<identifier>/metadata', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, str, update_client_metadata |
| 2949-2952 | 4 | `client_baseline_route` | `app.route('/clients/<identifier>/baseline', methods=['POST'])` | app, client_baseline_diff, json_success, save_client_baseline |
| 2956-2984 | 29 | `client_export_route` | `app.route('/clients/<identifier>/export.<fmt>')` | Response, app, client_profile_export, json_error, jsonify |
| 2988-2989 | 2 | `client_relationship_map_route` | `app.route('/clients/<identifier>/relationship-map')` | app, client_relationship_map, json_success |
| 2993-2995 | 3 | `client_intelligence_route` | `app.route('/clients/<identifier>/intelligence', methods=['POST'])` | app, client_intelligence_profile, json_success, request |
| 2999-3000 | 2 | `client_fingerprint_route` | `app.route('/clients/<identifier>/fingerprint', methods=['POST'])` | app, fingerprint_client_services, json_success |
| 3004-3009 | 6 | `client_scheduled_check_route` | `app.route('/clients/<identifier>/scheduled-check', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, save_scheduled_client_check, str |
| 3013-3018 | 6 | `client_scheduled_check_run_route` | `app.route('/clients/<identifier>/scheduled-check/run', methods=['POST'])` | ValueError, app, e, json_error, json_success, run_scheduled_client_check, str |
| 3022-3024 | 3 | `scheduled_checks_run_due_route` | `app.route('/scheduled-checks/run-due', methods=['POST'])` | app, json_success, len, run_due_scheduled_client_checks |
| 3028-3037 | 10 | `active_scan_route` | `app.route('/active-scan', methods=['POST'])` | active_scan, app, classify_scan_results, json_error, jsonify, record_inventory_devices, record_scan_devices_for_wireless_network, request |
| 3041-3051 | 11 | `passive_scan_route` | `app.route('/passive-scan', methods=['POST'])` | app, classify_scan_results, json_error, jsonify, passive_scan, record_inventory_devices, record_passive_observation_analytics, record_scan_devices_for_wireless_network, request |
| 3055-3057 | 3 | `passive_analytics_route` | `app.route('/passive-analytics.json')` | app, json_success, passive_observation_summary, request |
| 3061-3064 | 4 | `passive_monitor_status_route` | `app.route('/passive-monitor/status')` | app, jsonify, passive_monitor_snapshot, request |
| 3068-3077 | 10 | `passive_monitor_toggle_route` | `app.route('/passive-monitor/toggle', methods=['POST'])` | ValueError, app, exc, json_error, json_success, request, set_passive_monitor, str |
| 3081-3095 | 15 | `comprehensive_scan_route` | `app.route('/comprehensive-scan', methods=['POST'])` | ValueError, app, comprehensive_network_device_scan, e, json_error, json_success, record_scan_devices_for_wireless_network, request, str |
| 3099-3119 | 21 | `port_scan_route` | `app.route('/port-scan', methods=['POST'])` | PortScanError, ValueError, app, describe_open_ports, e, enrich_web_port_metadata, json_error, jsonify, missing_fields, parse_int, record_device_open_ports, request, scan_ports, str |
| 3123-3133 | 11 | `start_port_scan_job` | `app.route('/port-scan-jobs', methods=['POST'])` | ValueError, app, create_port_scan_job, e, json_error, json_success, missing_fields, parse_int, request, str |
| 3137-3142 | 6 | `port_scan_job_status` | `app.route('/port-scan-jobs/<job_id>')` | _port_scan_job_snapshot, app, json_error, json_success, port_scan_jobs, port_scan_jobs_lock |
| 3146-3148 | 3 | `jobs_status` | `app.route('/jobs/status')` | all_job_snapshots, app, json_success, len |
| 3152-3171 | 20 | `cancel_job` | `app.route('/jobs/<job_id>/cancel', methods=['POST'])` | _port_scan_job_snapshot, _scan_job_snapshot, app, json_error, json_success, port_scan_jobs, port_scan_jobs_lock, scan_jobs, scan_jobs_lock, time |
| 3175-3181 | 7 | `traceroute_route` | `app.route('/traceroute', methods=['POST'])` | app, json_error, jsonify, request, traceroute |
| 3185-3192 | 8 | `ping_route` | `app.route('/ping', methods=['POST'])` | ValueError, app, e, json_error, json_success, ping_history, request, run_ping_check, str, subprocess |
| 3196-3201 | 6 | `ping_sweep_route` | `app.route('/ping-sweep', methods=['POST'])` | ValueError, app, e, json_error, json_success, ping_history, request, run_ping_sweep, str |
| 3205-3207 | 3 | `route_diagnostics_route` | `app.route('/route-diagnostics', methods=['POST'])` | app, build_route_diagnostics, json_success, request |
| 3211-3213 | 3 | `mdns_discovery_route` | `app.route('/mdns-discovery', methods=['POST'])` | app, discover_mdns_services, json_success, request |
| 3217-3223 | 7 | `upnp_discovery_route` | `app.route('/upnp-discovery', methods=['POST'])` | ValueError, app, discover_upnp_devices, e, json_error, json_success, max, min, parse_int, request, str |
| 3227-3229 | 3 | `neighbor_discovery_route` | `app.route('/neighbor-discovery', methods=['POST'])` | app, discover_lldp_neighbors, json_success, request |
| 3233-3235 | 3 | `vlan_discovery_route` | `app.route('/vlan-discovery', methods=['POST'])` | app, discover_vlan_context, json_success, request |
| 3239-3240 | 2 | `egress_diagnostics_route` | `app.route('/egress-diagnostics', methods=['POST'])` | app, build_egress_diagnostics, json_success, request |
| 3244-3249 | 6 | `iperf3_test_route` | `app.route('/iperf3-test', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, run_iperf3_test, str, subprocess |
| 3253-3260 | 8 | `snmp_discovery_route` | `app.route('/snmp-discovery', methods=['POST'])` | ValueError, app, e, json_error, json_success, request, run_snmp_inventory, str |
| 3264-3266 | 3 | `ipv6_assessment_route` | `app.route('/ipv6-assessment', methods=['POST'])` | app, json_success, request, run_ipv6_assessment |
| 3270-3285 | 16 | `wireless_network_client_label_route` | `app.route('/wireless/network/label', methods=['POST'])` | app, json_error, json_success, request, save_runtime_state, wireless_network_client_label_key, wireless_network_labels |
| 3289-3298 | 10 | `wireless_network_clients_json` | `app.route('/wireless/network/clients.json')` | app, json_success, merge_wireless_network_clients, request, wifi_utils |
| 3302-3325 | 24 | `wireless_network_clients_export` | `app.route('/wireless/network/clients.csv')` | Response, app, csv, io, json, merge_wireless_network_clients, request, secure_filename, str, wifi_utils |
| 3329-3347 | 19 | `wireless_network_detail` | `app.route('/wireless/network')` | app, current_context, merge_wireless_network_clients, render_template, request, wifi_utils |
| 3351-3364 | 14 | `interface_power_state` | `app.route('/interfaces/<interface_name>/state', methods=['POST'])` | Exception, ValueError, app, exc, getattr, json_error, json_success, network_interfaces, next, request, set_interface_power_state, str |
| 3367-3374 | 8 | `interfaces_by_type` | `app.route('/<interface_type>')` | app, current_context, network_interfaces, render_template |
| 3378-3390 | 13 | `interface_detail` | `app.route('/<interface_type>/<interface_name>')` | app, bluetooth_phone_card_context, current_context, network_interfaces, next, render_template |
| 3394-3408 | 15 | `syn_flood` | `app.route('/syn-flood', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, missing_fields, networkAttacks, parse_int, request, str |
| 3412-3425 | 14 | `syn_flood_broadcast` | `app.route('/syn-flood-broadcast', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, missing_fields, networkAttacks, parse_int, request, str |
| 3429-3439 | 11 | `wlan_modes` | `app.route('/wlan-modes', methods=['GET'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 3443-3457 | 15 | `wlan_mode` | `app.route('/wlan-mode', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, request, str, wifi_utils |
| 3461-3467 | 7 | `start_scan_job` | `app.route('/scan-jobs', methods=['POST'])` | ValueError, app, create_scan_job, e, json_error, json_success, request, str |
| 3471-3476 | 6 | `scan_job_status` | `app.route('/scan-jobs/<job_id>')` | _scan_job_snapshot, app, json_error, json_success, scan_jobs, scan_jobs_lock |
| 3480-3493 | 14 | `wlan_scan` | `app.route('/wlan-scan', methods=['POST'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 3497-3514 | 18 | `wlan_connect` | `app.route('/wlan-connect', methods=['POST'])` | Exception, app, e, json_error, json_success, request, str, wifi_utils |
| 3518-3530 | 13 | `bluetooth_scan` | `app.route('/bluetooth-scan', methods=['POST'])` | Exception, app, asyncio, bluetooth_action_capability, bluetooth_device_summary, e, get_bluetooth_devices, json_error, json_success, request, str |
| 3534-3557 | 24 | `bluetooth_action` | `app.route('/bluetooth-action', methods=['POST'])` | BluetoothToolUnavailable, Exception, ValueError, _bluetooth_state_updates_for_action, _merge_inventory_device_state, _parse_bluetooth_info_output, app, bluetooth_contextual_actions, bluetooth_device_state, e, find_inventory_device, json_error, json_success, record_bluetooth_action_history, request, run_bluetoothctl_action, str |
| 3561-3576 | 16 | `bluetooth_device_refresh` | `app.route('/bluetooth-device/<address>/refresh', methods=['POST'])` | BluetoothToolUnavailable, Exception, ValueError, _merge_inventory_device_state, _parse_bluetooth_info_output, app, bluetooth_contextual_actions, bluetooth_device_state, e, json_error, json_success, record_bluetooth_action_history, request, run_bluetoothctl_action, str |
| 3580-3584 | 5 | `forget_inventory_route` | `app.route('/inventory/<identifier>/forget', methods=['POST'])` | app, forget_inventory_device, json_error, json_success |
| 3588-3598 | 11 | `spoof_mac_route` | `app.route('/spoof-mac', methods=['POST'])` | app, json_error, json_success, request, spoof_mac |
| 3602-3622 | 21 | `beacon_advertise` | `app.route('/beacon-advertise', methods=['POST'])` | Exception, ValueError, app, beaconSpoof, e, json_error, json_success, missing_fields, parse_int, request, str |
| 3626-3643 | 18 | `deauth_route` | `app.route('/deauth', methods=['POST'])` | Exception, ValueError, app, deauth, e, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, str |
| 3647-3665 | 19 | `evil_twin_lab_route` | `app.route('/evil-twin-lab', methods=['POST'])` | ValueError, app, e, evil_twin_lab_lock, evil_twin_lab_runs, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, save_runtime_state, str |
| 3669-3682 | 14 | `pineap_lab_route` | `app.route('/pineap-lab', methods=['POST'])` | Exception, ValueError, app, e, json_error, json_success, labs_service, len, missing_fields, normalize_mac, parse_int, pineap_lab_lock, pineap_lab_runs, request, save_runtime_state, str, wifi_utils |
| 3686-3696 | 11 | `handshake_lab_route` | `app.route('/handshake-lab', methods=['POST'])` | ValueError, app, create_evidence_record, e, handshake_lab_lock, handshake_lab_records, json_error, json_success, labs_service, missing_fields, normalize_mac, parse_int, request, save_runtime_state, str |
| 3700-3706 | 7 | `export_handshake_lab` | `app.route('/handshake-lab.<fmt>')` | Response, app, handshake_lab_lock, handshake_lab_records, json_error, jsonify, labs_service, time |
| 3710-3729 | 20 | `aireplay_deauth_route` | `app.route('/aireplay-deauth', methods=['POST'])` | Exception, ValueError, aireplay_deauth, app, e, json_error, json_success, missing_fields, parse_int, request, str |
