"""Evidence vault record and export helpers."""

import csv
import io
import os
import time
import uuid


def evidence_records(evidence_store, lock):
    """Return evidence vault records with display labels."""
    with lock:
        records = [dict(item) for item in evidence_store]
    for item in records:
        item['created_at_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('created_at', 0)))
    return records


def create_evidence_record(title, category, source, device, notes, content, uploaded_file, evidence_dir, evidence_store, lock, save_state, secure_filename):
    """Store a timestamped evidence record and optional uploaded file metadata."""
    title = (title or '').strip()
    if not title:
        raise ValueError('Evidence title is required')
    category = (category or 'note').strip().lower()
    if category not in {'note', 'scan-output', 'capture', 'screenshot', 'artifact'}:
        raise ValueError('Unsupported evidence category')

    record = {
        'id': uuid.uuid4().hex,
        'title': title,
        'category': category,
        'source': (source or '').strip(),
        'device': (device or '').strip(),
        'notes': (notes or '').strip(),
        'content': (content or '').strip(),
        'created_at': time.time(),
        'file_name': None,
        'file_size': None,
        'download_url': None,
    }

    if uploaded_file and uploaded_file.filename:
        os.makedirs(evidence_dir, exist_ok=True)
        safe_name = secure_filename(uploaded_file.filename)
        if not safe_name:
            raise ValueError('Uploaded file name is not valid')
        stored_name = f"{record['id']}-{safe_name}"
        path = os.path.join(evidence_dir, stored_name)
        uploaded_file.save(path)
        record.update({
            'file_name': safe_name,
            'stored_name': stored_name,
            'file_size': os.path.getsize(path),
            'download_url': f"/evidence/{record['id']}/download",
        })

    with lock:
        evidence_store.insert(0, record)
        del evidence_store[500:]
    save_state('evidence')
    return dict(record)


def evidence_as_csv(records):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Category', 'Source', 'Device', 'File', 'Created', 'Notes', 'Content'])
    for item in records:
        writer.writerow([
            item.get('title'),
            item.get('category'),
            item.get('source'),
            item.get('device'),
            item.get('file_name'),
            item.get('created_at_label'),
            item.get('notes'),
            item.get('content'),
        ])
    return output.getvalue()


def evidence_as_markdown(records):
    lines = ['# Evidence Vault', '']
    if not records:
        lines.append('_No evidence records captured yet._')
    for item in records:
        lines.extend([
            f"## {item.get('title')}",
            f"- Category: {item.get('category')}",
            f"- Source: {item.get('source') or 'Unknown'}",
            f"- Device: {item.get('device') or 'N/A'}",
            f"- Created: {item.get('created_at_label')}",
        ])
        if item.get('file_name'):
            lines.append(f"- File: {item.get('file_name')} ({item.get('file_size')} bytes)")
        if item.get('notes'):
            lines.extend(['', item.get('notes')])
        if item.get('content'):
            lines.extend(['', '```', item.get('content'), '```'])
        lines.append('')
    return '\n'.join(lines)
