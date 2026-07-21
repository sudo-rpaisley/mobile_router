"""Report assembly and export format helpers."""

import csv
import io
import time


def build_report_data(network_interfaces, inventory_records, manufacturer_insights, all_job_snapshots, alert_records, evidence_records, build_capabilities):
    """Collect the current application state for report exports."""
    devices = inventory_records()
    exported_at = time.time()
    return {
        'exported_at': exported_at,
        'exported_at_label': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exported_at)),
        'interfaces': [iface.to_dict() for iface in network_interfaces],
        'devices': devices,
        'insights': manufacturer_insights(devices),
        'jobs': all_job_snapshots(),
        'alerts': alert_records(),
        'evidence': evidence_records(),
        'capabilities': build_capabilities(),
    }


def report_as_csv(report):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Mobile Router Report'])
    writer.writerow(['Exported at', report['exported_at_label']])
    writer.writerow([])
    writer.writerow(['Devices'])
    writer.writerow(['Name', 'IP', 'MAC', 'Manufacturer', 'Sources', 'Interfaces', 'First seen', 'Last seen'])
    for device in report['devices']:
        writer.writerow([
            device.get('display_name'),
            device.get('ip'),
            device.get('mac') or device.get('bssid'),
            device.get('manufacturer'),
            ', '.join(device.get('sources', [])),
            ', '.join(device.get('interfaces', [])),
            device.get('first_seen_label'),
            device.get('last_seen_label'),
        ])
    writer.writerow([])
    writer.writerow(['Interfaces'])
    writer.writerow(['Name', 'Type', 'State', 'Manufacturer'])
    for iface in report['interfaces']:
        writer.writerow([iface.get('name'), iface.get('interface_type'), iface.get('state'), iface.get('manufacturer')])
    writer.writerow([])
    writer.writerow(['Jobs'])
    writer.writerow(['ID', 'Kind', 'Label', 'Status', 'Progress'])
    for job in report['jobs']:
        writer.writerow([job.get('id'), job.get('kind'), job.get('label') or job.get('scan_type'), job.get('status'), job.get('progress')])
    writer.writerow([])
    writer.writerow(['Evidence'])
    writer.writerow(['Title', 'Category', 'Source', 'Device', 'File', 'Created'])
    for item in report['evidence']:
        writer.writerow([item.get('title'), item.get('category'), item.get('source'), item.get('device'), item.get('file_name'), item.get('created_at_label')])
    writer.writerow([])
    writer.writerow(['Alerts'])
    writer.writerow(['Device', 'IP', 'MAC', 'Manufacturer', 'Source', 'Read', 'Created'])
    for alert in report['alerts']:
        writer.writerow([alert.get('display_name'), alert.get('ip'), alert.get('mac'), alert.get('manufacturer'), alert.get('source'), alert.get('read'), alert.get('created_at_label')])
    return output.getvalue()


def report_as_markdown(report):
    lines = [
        '# Mobile Router Report',
        '',
        f"Exported at: {report['exported_at_label']}",
        '',
        '## Summary',
        f"- Devices: {report['insights']['total_devices']}",
        f"- Known manufacturers: {report['insights']['known_manufacturers']}",
        f"- Unknown manufacturers: {report['insights']['unknown_manufacturers']}",
        f"- Interfaces: {len(report['interfaces'])}",
        f"- Jobs: {len(report['jobs'])}",
        f"- Alerts: {len(report['alerts'])}",
        f"- Evidence records: {len(report['evidence'])}",
        '',
        '## Devices',
        '| Name | IP | MAC/BSSID | Manufacturer | Sources |',
        '| --- | --- | --- | --- | --- |',
    ]
    for device in report['devices']:
        lines.append(f"| {device.get('display_name', '')} | {device.get('ip') or ''} | {device.get('mac') or device.get('bssid') or ''} | {device.get('manufacturer') or ''} | {', '.join(device.get('sources', []))} |")
    lines.extend(['', '## Interfaces', '| Name | Type | State | Manufacturer |', '| --- | --- | --- | --- |'])
    for iface in report['interfaces']:
        lines.append(f"| {iface.get('name', '')} | {iface.get('interface_type', '')} | {iface.get('state', '')} | {iface.get('manufacturer', '')} |")
    lines.extend(['', '## Evidence', '| Title | Category | Source | Device | File | Created |', '| --- | --- | --- | --- | --- | --- |'])
    for item in report['evidence']:
        lines.append(f"| {item.get('title', '')} | {item.get('category', '')} | {item.get('source') or ''} | {item.get('device') or ''} | {item.get('file_name') or ''} | {item.get('created_at_label') or ''} |")
    lines.extend(['', '## Alerts', '| Device | IP | MAC | Source | Read |', '| --- | --- | --- | --- | --- |'])
    for alert in report['alerts']:
        lines.append(f"| {alert.get('display_name', '')} | {alert.get('ip') or ''} | {alert.get('mac') or ''} | {alert.get('source') or ''} | {alert.get('read')} |")
    return '\n'.join(lines) + '\n'
