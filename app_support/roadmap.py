"""Static product-roadmap data and projections."""

ROADMAP_SECTIONS = [
    {
        'title': 'High-impact UX',
        'items': [
            {'title': 'Adapter health badges', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Shows Ready/state, No address, and adapter type directly on adapter cards.', 'description': 'Show Ready, Missing tools, Down, No address, monitor-mode, and action availability directly on adapter cards.'},
            {'title': 'Adapter action readiness panel', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Interface detail pages include an Action Readiness panel with available actions and dependency guidance.', 'description': 'Summarize exactly what each adapter can do and why unavailable actions are disabled.'},
            {'title': 'Better empty and error states', 'priority': 'High', 'priority_class': 'danger', 'description': 'Replace generic scan failures with actionable install/setup guidance and links to capabilities.'},
            {'title': 'Layout density and navigation review', 'priority': 'High', 'priority_class': 'danger', 'description': 'Compare tabs, accordions, split panels, compact/advanced modes, and dashboard drill-downs before adding more controls to dense pages.'},
            {'title': 'Tabbed interface detail layout', 'priority': 'High', 'priority_class': 'danger', 'description': 'Adopt option A: organize dense interface pages into tabs such as Overview, Scan Results, Charts, Actions, Diagnostics, and History.'},
            {'title': 'Export reports', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Reports page exports inventory, interfaces, capabilities, jobs, alerts, and evidence as JSON, CSV, Markdown, or HTML.', 'description': 'Export interfaces, scan results, capabilities, and discovered devices as JSON, CSV, Markdown, or HTML.'},
        ],
    },
    {
        'title': 'Guided modes and progression',
        'items': [
            {'title': 'Full and training mode switch', 'priority': 'High', 'priority_class': 'danger', 'description': 'Add a mode selector where Full mode exposes every available feature and Training mode starts with a limited guided toolset.'},
            {'title': 'Progressive training unlocks', 'priority': 'High', 'priority_class': 'danger', 'description': 'In Training mode, unlock the next control only after the learner completes the current step, such as scanning before connection, diagnostics, exports, or advanced actions.'},
            {'title': 'Guided focus overlay', 'priority': 'High', 'priority_class': 'danger', 'description': 'Guide learners by dimming the layout and spotlighting/circling the next control, with step instructions and progress state.'},
            {'title': 'Guided connectivity diagnostics module', 'priority': 'High', 'priority_class': 'danger', 'description': 'Teach learners to select a host, test reachability, interpret latency and loss, trace its route, run a bounded service scan, and save the results as evidence.'},
            {'title': 'Training trophies and milestones', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award trophies for milestones such as 20 completed scans, first Bluetooth refresh, first OUI lookup, first export, and completion of each guided module.'},
        ],
    },
    {
        'title': 'Training trophies',
        'items': [
            {'title': 'Scan milestone trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award first Wi-Fi scan, first Bluetooth scan, 10 scans, 20 scans, first scan with more than five networks, first multi-BSSID SSID, and first hidden network discovered.'},
            {'title': 'Wireless analysis trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award channel congestion review, 2.4/5 GHz comparison, occupancy export, BSSID drill-down, OUI/vendor lookup, WPS exposure finding, and best-channel recommendation review.'},
            {'title': 'Bluetooth workflow trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award first Bluetooth device discovery, metadata refresh, state interpretation, vendor identification, action history entry, and inventory-only forget action.'},
            {'title': 'Connectivity diagnostics trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award First Contact, Name Resolver, Dual Stack, Latency Analyst, Pathfinder, and Network Medic milestones for completing increasingly detailed reachability and route diagnostics.'},
            {'title': 'Reporting and evidence trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award first report export, evidence note, saved scan evidence, complete training report, and explain-this-finding write-up.'},
            {'title': 'Training completion trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award Wireless Basics, Bluetooth Basics, Diagnostics, Reports, and Full Training Path completion trophies as learners finish guided modules.'},
        ],
    },
    {
        'title': 'Network visibility',
        'items': [
            {'title': 'Device inventory page', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'The /inventory page aggregates discovered devices, sources, interfaces, manufacturers, and first/last seen timestamps.', 'description': 'Aggregate discovered IPs, MACs, manufacturers, ports, SSIDs, and first/last seen timestamps.'},
            {'title': 'Persistent local inventory state', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Inventory devices, saved port profiles, client timelines, labels, watched clients, scheduled check plans, evidence, alerts, and lab records are now snapshotted to data/runtime_state.json and loaded on startup.', 'description': 'Persist device profiles, ports, labels, timelines, alerts, and evidence locally so large scans do not need to be rerun after restart.'},
            {'title': 'Comprehensive network device scan', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Network Scan now combines active ARP, passive observations, local ARP/neighbor tables, optional ping sweeps, mDNS, UPnP/SSDP, and LLDP/CDP metadata into one inventory-building workflow.', 'description': 'Scan local networks for devices using multiple discovery methods and merge results into inventory with source attribution.'},
            {'title': 'IP client profiles and watchlists', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Client pages now include health scoring, saved service history, web inspection, watch alerts, timeline events, owner/location/tags, baselines, drift checks, reachability history, and per-client JSON/Markdown exports.', 'description': 'Turn discovered IP clients into investigation profiles with health, ownership, baseline, watch, timeline, and export workflows.'},
            {'title': 'Network map', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Visualize adapters, SSIDs, access points, clients, and wired hosts as a simple topology map.'},
            {'title': 'Client relationship map', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Client profiles now show relationship nodes and links for interfaces, discovery sources, saved services, and related evidence records.', 'description': 'Show each IP client connected to interfaces, SSIDs, gateways, VLAN context, services, evidence records, and alerts.'},
            {'title': 'Scheduled client checks', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Client profiles can save recurring check plans and run due/on-demand ping, bounded common-port refresh, HTTP inspection, service fingerprinting, and baseline drift checks.', 'description': 'Run recurring reachability, common-port, service-fingerprint, and drift checks for watched clients with alerting.'},
            {'title': 'Client remediation checklist', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Turn baseline drift, sensitive services, and unknown identity hints into suggested remediation tasks with resolved/accepted-risk state.'},
            {'title': 'Client change approval log', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Let users approve expected port, owner, location, and tag changes with reviewer notes for audit-friendly inventory maintenance.'},
            {'title': 'Dedicated wireless occupancy report page', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Create a drill-down page that compares adapters, channel congestion, BSSID detail, historical heatmaps, and exportable recommendations.'},
            {'title': 'Manufacturer/OUI insights', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Inventory groups devices by manufacturer and highlights unknown OUIs for review.', 'description': 'Group discovered devices by vendor and highlight unknown or unusual manufacturers.'},
            {'title': 'New device alerts', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'New devices create unread alerts with a navbar badge and alert center.', 'description': 'Notify when a newly observed MAC, IP, SSID, or Bluetooth device appears.'},
            {'title': 'Grouped discovery notifications', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Inventory discovery now creates one grouped alert for multi-device active/job scans while preserving individual passive-scan alerts.', 'description': 'When multiple devices are discovered in the same scan, group them into one notification while keeping individual passive-discovery alerts for devices that appear later.'},
        ],
    },
    {
        'title': 'Core network tools',
        'items': [
            {'title': 'Tabbed connectivity diagnostics workspace', 'priority': 'High', 'priority_class': 'danger', 'description': 'Create an option-A diagnostics workspace with Overview, Reachability, DNS, Routes, Neighbors, Services, Traffic, and History tabs rather than adding more controls to a single long page.'},
            {'title': 'Device-page reachability actions', 'priority': 'High', 'priority_class': 'danger', 'description': 'Add contextual Ping, Traceroute, and bounded Port Scan actions to IP device pages with live reachability state, last-checked time, latency, and packet-loss summaries.'},
            {'title': 'Reachability history and comparisons', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Store recent reachability checks so users can compare latency and loss across hosts, interfaces, IPv4/IPv6, and repeated assessments.'},
            {'title': 'Ping and reachability testing', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Diagnostics now includes single-host ping, bounded subnet sweeps, packet loss, latency parsing, and recent reachability history.', 'description': 'Add single-host ping, subnet ping sweeps, packet-loss summaries, latency stats, and IPv4/IPv6 reachability history.'},
            {'title': 'ARP and neighbor discovery viewer', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Comprehensive network scans now include local ARP cache and neighbor-table observations with OUI/vendor enrichment and inventory links.', 'description': 'Show local ARP and IPv6 neighbor tables with interface, state, OUI/vendor enrichment, and inventory links.'},
            {'title': 'DNS lookup and diagnostics toolkit', 'priority': 'High', 'priority_class': 'danger', 'description': 'Support A, AAAA, PTR, MX, TXT, NS, and CNAME lookups, resolver comparison, timing, and split-horizon troubleshooting.'},
            {'title': 'Route table and gateway diagnostics', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Diagnostics now reports default gateways, parsed IPv4/IPv6 routes, per-interface metrics, VPN route hints, and target scan-path context.', 'description': 'Display default gateways, per-interface routes, metrics, IPv4/IPv6 routes, VPN route hints, and scan-path context.'},
            {'title': 'Connectivity health check', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Check gateway, DNS, HTTP, HTTPS, NTP, IPv4, IPv6, captive portal state, and explain which layer is failing.'},
            {'title': 'Packet capture and protocol summary', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Start and stop scoped packet captures, export PCAP files, summarize protocols/top talkers, and attach captures to evidence.'},
            {'title': 'Live traffic monitor', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Show bandwidth, packets per second, top talkers, protocol mix, and short history per interface.'},
            {'title': 'Local socket and listener inventory', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'List local listening ports and established connections with process names where available and highlight externally exposed listeners.'},
            {'title': 'Service fingerprinting and banner detection', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'IP client profiles can run safe banner probes and HTTP checks against saved open ports with confidence labels.', 'description': 'Identify services beyond port numbers using banners and safe protocol checks with confidence labels.'},
            {'title': 'HTTP service inspector', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Inspect HTTP/HTTPS services for status, redirects, page title, server headers, login forms, TLS details, and basic security headers.'},
        ],
    },
    {
        'title': 'Extended network tools',
        'items': [
            {'title': 'TLS certificate inspection', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Show certificate subject, issuer, SANs, expiration, self-signed status, hostname mismatch, and chain details.'},
            {'title': 'DHCP lease and server inspection', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Display DHCP lease details, DNS/router options, renewal timing, and warnings for multiple or unexpected DHCP servers.'},
            {'title': 'mDNS and Bonjour service discovery', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Service Discovery now parses mDNS/Bonjour service records, hostnames, ports, TXT records, roles, and inventory metadata.', 'description': 'Discover local mDNS services, hostnames, ports, TXT records, device roles, and add service metadata to inventory.'},
            {'title': 'UPnP and SSDP discovery', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Service Discovery now performs bounded SSDP discovery and catalogs friendly names, model/manufacturer hints, service types, and control URLs.', 'description': 'Discover UPnP devices, friendly names, model/manufacturer metadata, service lists, and exposed control URLs.'},
            {'title': 'LLDP and CDP neighbor discovery', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Service Discovery now surfaces lldpctl neighbor data including switch/router names, ports, VLAN hints, and management addresses when visible.', 'description': 'Reveal switch/router neighbors, port IDs, chassis IDs, VLAN hints, and management addresses when packets are visible.'},
            {'title': 'VLAN discovery and segmentation notes', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Advanced Diagnostics now inventories VLAN interfaces/tags and stores SSID-to-VLAN segmentation validation notes.', 'description': 'Track VLAN interfaces, observed tags, SSID-to-VLAN notes, and segmentation validation context.'},
            {'title': 'Egress and public IP diagnostics', 'priority': 'Low', 'priority_class': 'secondary', 'status': 'Done', 'completed_note': 'Advanced Diagnostics now reports public IP hints, NAT context, DNS resolvers, IPv6 egress, VPN/proxy hints, and per-interface route context.', 'description': 'Show public IP, NAT context, DNS egress resolver, IPv6 egress, VPN/proxy hints, and per-interface egress differences.'},
            {'title': 'iperf3 performance testing', 'priority': 'Low', 'priority_class': 'secondary', 'status': 'Done', 'completed_note': 'Advanced Diagnostics now runs bounded iperf3 client/server checks for LAN throughput baselines when iperf3 is installed.', 'description': 'Run controlled iperf3 client/server tests for throughput, jitter, loss, and LAN performance baselines.'},
            {'title': 'SNMP inventory discovery', 'priority': 'Low', 'priority_class': 'secondary', 'status': 'Done', 'completed_note': 'Advanced Diagnostics now safely collects SNMP system and interface metadata from authorized targets when credentials are supplied.', 'description': 'Safely collect SNMP system identity and interface metadata from authorized devices when credentials are provided.'},
            {'title': 'IPv6 assessment toolkit', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Advanced Diagnostics now includes IPv6 ping, traceroute, neighbor/default-route views, AAAA lookup, and bounded IPv6 TCP checks.', 'description': 'Add IPv6 ping, traceroute, neighbor discovery, router advertisement visibility, DNS records, and IPv6 port scanning support.'},
        ],
    },
    {
        'title': 'Automotive diagnostics',
        'items': [
            {'title': 'Offline VIN, DTC, vehicle, and workshop records', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Automotive pages now provide local WMI/VIN and DTC lookups, saved vehicles, translation snapshots, report exports, and SQLite persistence.', 'description': 'Provide the local automotive data and reporting foundation without online lookups.'},
            {'title': 'Staged automotive database imports', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'VIN and DTC uploads are checksum-tracked, staged for row review, selectively approved in one transaction, or discarded.', 'description': 'Review parsed VIN and DTC records before they affect live lookup results.'},
            {'title': 'Vehicle and module identity inventory', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Vehicle pages retain chassis, frame, body, engine, transmission, registration, fleet, and legacy identifiers plus ECU/module identities, calibration data, and module-reported VIN match warnings.', 'description': 'Keep one canonical vehicle VIN while tracking physical identifiers and every control-module identity observation.'},
            {'title': 'Simulated OBD-II reader', 'priority': 'High', 'priority_class': 'danger', 'description': 'Build an ELM327-style simulator for connection, VIN, current/pending/permanent DTC, freeze-frame, readiness, live-PID, timeout, malformed-response, and clear-code scenarios before hardware arrives.'},
            {'title': 'Transport-neutral OBD architecture', 'priority': 'High', 'priority_class': 'danger', 'description': 'Define shared discovery, connect, command, timeout, cancellation, and disconnect contracts for simulated, USB serial, Bluetooth Classic, BLE, and Wi-Fi readers.'},
            {'title': 'Immutable diagnostic sessions', 'priority': 'High', 'priority_class': 'danger', 'description': 'Persist adapter identity, protocol, vehicle VIN, raw responses, categorized DTCs, freeze-frame values, readiness monitors, PID samples, warnings, and before/after state.'},
            {'title': 'Automotive diagnostics workspace', 'priority': 'High', 'priority_class': 'danger', 'description': 'Add reader and vehicle selection, connection state, quick/full scans, readiness, freeze-frame, live data, saved sessions, and create-report actions.'},
            {'title': 'USB serial ELM327 and STN support', 'priority': 'High', 'priority_class': 'danger', 'description': 'Discover ports, probe baud rates, initialize supported adapters, detect protocols, enforce bounded commands, cancel work, and retain raw exchanges.'},
            {'title': 'Bluetooth Classic and Wi-Fi OBD transports', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Support paired RFCOMM/SPP readers and configured TCP readers through the same diagnostic-session service.'},
            {'title': 'Adapter-specific Bluetooth LE plugins', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add BLE GATT transports as explicit adapter plugins rather than treating every BLE reader as a generic serial device.'},
            {'title': 'Safe DTC clearing workflow', 'priority': 'High', 'priority_class': 'danger', 'description': 'Require a saved pre-clear scan and explicit warning, record the action, explain readiness reset, and automatically capture a post-clear scan.'},
            {'title': 'Full downloadable VIN decoder dataset', 'priority': 'High', 'priority_class': 'danger', 'description': 'Add a versioned authoritative dataset adapter for make, model, year, body, engine, plant, restraint, and manufacturer-specific VDS decoding while keeping runtime lookup offline.'},
            {'title': 'Versioned DTC definition library', 'priority': 'High', 'priority_class': 'danger', 'description': 'Preserve multiple sourced definitions and translations by make, model, year, engine, module, language, source page, confidence, and superseded state instead of replacing code/make pairs.'},
            {'title': 'PDF provenance and OCR review', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Retain original documents, page numbers, extracted context, confidence, and corrections, with optional OCR staging for image-only diagnostic manuals.'},
            {'title': 'Professional workshop PDF reports', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add Unicode, wrapping, pagination, DTC tables, branding, dates, diagnostic sessions, before/after results, parts, labor, recommendations, attachments, and signatures.'},
            {'title': 'Report revisions and finalization', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Support draft, final, amended, and void states with revision history, finalized-by identity, and immutable finalized records.'},
            {'title': 'Automotive backup and restore', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Export, validate, and restore the complete automotive database, source documents, vehicle histories, sessions, reports, and import provenance.'},
            {'title': 'Automotive route, browser, and hardware tests', 'priority': 'High', 'priority_class': 'danger', 'description': 'Cover authentication, CSRF, uploads, redirects, corrupt PDFs, migrations, rollback, reader simulation, diagnostic sessions, report downloads, accessibility, and mobile layouts.'},
        ],
    },
    {
        'title': 'Train Controller integration',
        'source_url': 'https://github.com/sudo-rpaisley/Train-Controller',
        'items': [
            {'title': 'Train Controller repository compatibility review', 'priority': 'High', 'priority_class': 'danger', 'description': 'Review sudo-rpaisley/Train-Controller features, dependencies, entry points, data model, platform requirements, tests, and license, then map reusable functionality to Mobile Router capabilities and pages.'},
            {'title': 'Train Controller feature inventory and import plan', 'priority': 'High', 'priority_class': 'danger', 'description': 'Catalog the linked repository\'s user-facing controls and supporting services, identify code that can be reused versus adapted, and split the integration into independently testable phases before implementation.'},
            {'title': 'Train Controller integration boundary', 'priority': 'High', 'priority_class': 'danger', 'description': 'Define a capability-backed adapter or plugin boundary so selected Train Controller functionality can be added without tightly coupling either application or duplicating platform-specific logic.'},
            {'title': 'Train Controller workflow and progress bridge', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Expose approved Train Controller workflows through Full and Training modes while sharing guided steps, progress, trophies, action history, and evidence exports where appropriate.'},
        ],
    },
    {
        'title': 'Wireless and Bluetooth',
        'items': [
            {'title': 'Wi-Fi channel and band charts', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Wireless scan results include channel and band occupancy charts.', 'description': 'Chart 2.4/5 GHz occupancy, overlapping channels, security, and signal strength.'},
            {'title': 'Wireless network timelines', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Track signal, channel, security, AP count, and seen timestamps per SSID/BSSID.'},
            {'title': 'Server-side wireless occupancy history', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Persist repeated scan occupancy by adapter so heatmaps, channel recommendations, and reports survive browser sessions and server restarts.'},
            {'title': 'Bluetooth metadata refresh pipeline', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Parse single-device Bluetooth refresh output into inventory fields, update contextual controls, and show last-refreshed timestamps without a full page reload.'},
            {'title': 'Bluetooth destructive-action confirmations', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add clearer confirmation modals, host-stack vs inventory-only explanations, and undo for inventory-only forget actions.'},
            {'title': 'Known network labels', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Let users mark SSIDs as trusted, lab, suspicious, or ignored.'},
            {'title': 'Bluetooth action checklist', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Bluetooth scans report action capability and show host-tool guidance for bluetoothctl or BlueZ D-Bus support.', 'description': 'Show bluetoothctl, busctl, BlueZ D-Bus, adapter power, pairing, trust, and action readiness.'},
        ],
    },

    {
        'title': 'Wireless risk lab',
        'items': [
            {'title': 'WPA handshake capture lab', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Red Team now catalogs authorized WPA/WPA2 handshake or PMKID evidence with validation status, Evidence Vault mirroring, and JSON/CSV exports.', 'description': 'Capture, validate, catalog, and export WPA/WPA2 handshake or PMKID evidence from authorized lab networks.'},
            {'title': 'Scoped deauthentication actions', 'priority': 'High', 'priority_class': 'danger', 'description': 'Run AP-wide or client-specific deauthentication actions against authorized lab networks with targeting controls, rate limits, and clear logs.'},
            {'title': 'Remote cracking orchestration', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Queue authorized handshake material to stronger remote workers such as Spark, track job progress, and import results for password-strength review.'},
            {'title': 'PineAP-style recon and campaign engine', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Red Team now includes a PineAP-style lab console for authorized recon, campaign, handshake, and module workflow logging.', 'description': 'Build functional WiFi Pineapple-style recon, campaign, handshake, module, and Cloud C2-inspired workflows for authorized labs.'},
            {'title': 'Evil twin and captive portal lab', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Red Team now records authorized evil-twin/captive-portal lab plans with explicit SSID/BSSID/channel targeting, cleanup steps, and detection guidance.', 'description': 'Run controlled rogue-AP and captive-portal lab workflows with explicit SSID targeting, logging, cleanup, and detection guidance.'},
            {'title': 'WPS exposure checks', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Wireless scan results and network detail pages now flag APs advertising WPS and explain why WPS can weaken credential protection.', 'description': 'Identify lab networks advertising WPS and explain why WPS increases wireless credential risk.'},
            {'title': 'Client privacy and probe request monitor', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Monitor probe behavior to show device presence, preferred-network leakage, and tracking risk in authorized training environments.'},
            {'title': 'Rogue DHCP, DNS, and portal lab', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Run isolated post-association lab workflows for rogue DHCP, DNS manipulation, and portal redirection with validation checks.'},
            {'title': 'RF interference awareness', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Provide detection-only views for congestion and interference risks without implementing jamming behavior.'},
        ],
    },

    {
        'title': 'Hak5-inspired lab features',
        'items': [
            {'title': 'Payload profile switchboard', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Create selectable, named operational profiles with prerequisites, status feedback, logs, and operator review before execution.'},
            {'title': 'Inline network tap mode', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Offer Packet Squirrel-style lab views for packet capture, transparent bridge/NAT/VPN concepts, and defensive visibility.'},
            {'title': 'DNS manipulation lab', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Run DNS spoofing or redirection workflows inside isolated lab networks, with validation, logging, and cleanup controls.'},
            {'title': 'Cloud C2-style operations controller', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Coordinate approved jobs, progress, artifacts, and remote workers across local and remote lab devices from one dashboard.'},
            {'title': 'Payload/module marketplace', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add a curated module library with prerequisites, expected outputs, configuration, cleanup steps, and professional operator notes.'},
            {'title': 'Quick wired recon profile', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add Shark Jack-style rapid wired-network assessment views for host discovery, service summaries, and risk scoring.'},
            {'title': 'Evidence and loot vault', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Evidence Vault stores timestamped notes, scan output, captures, screenshots, and file metadata with JSON/CSV/Markdown export controls.', 'description': 'Collect scan outputs, captures, screenshots, and notes into a time-stamped class report with export controls.'},
            {'title': 'HID and USB training module', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Provide Rubber Ducky/Bash Bunny-inspired HID and composite-USB workflows for managed lab machines with logging and cleanup.'},
            {'title': 'Screen capture risk module', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Model Screen Crab-style HDMI observation risk with explicit lab device selection, consent state, and detection/reporting guidance.'},
        ],
    },
    {
        'title': 'Safety and architecture',
        'items': [
            {'title': 'Central capability registry', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Capabilities now come from a central registry with required commands, packages, platforms, runtime checks, install hints, UI rendering, and JSON export.', 'description': 'Describe each feature once with required commands, packages, platforms, checks, and install hints.'},
            {'title': 'Background scan jobs', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Wireless, Bluetooth, and port scans now use tracked background jobs with live status polling and cancellation controls.', 'description': 'Move long-running scans into cancellable jobs with progress updates over Socket.IO.'},
            {'title': 'Partial adapter updates', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Adapter polling now returns targeted navbar/card fragments for DOM replacement without a full-page reload.', 'description': 'Update adapter cards and navbar content without full-page reloads when interfaces change.'},
            {'title': 'Browser-level UI smoke tests', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Browser-oriented tests now assert the Bluetooth contextual controls, AJAX re-render hooks, Wi-Fi dashboard controls, BSSID mode, export buttons, and full-screen map hooks.', 'description': 'Cover high-value template and JavaScript behavior so richer UI controls do not regress.'},
        ],
    },
]

def remaining_roadmap_items():
    """Return roadmap entries that have not been checked off as done."""
    remaining = []
    for section in ROADMAP_SECTIONS:
        for item in section['items']:
            if item.get('status') != 'Done':
                remaining.append({**item, 'section': section['title']})
    return remaining
