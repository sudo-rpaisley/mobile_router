"""Background port-scan job state and execution helpers."""

import time

def job_snapshot(job):
    """Return a serializable snapshot of a port-scan job."""
    return {
        **job,
        'kind': 'port-scan',
        'open_ports': list(job.get('open_ports', [])),
        'open_port_details': list(job.get('open_port_details', [])),
        'cancelable': job.get('status') in {'queued', 'running'},
    }


def all_snapshots(jobs, lock):
    """Return all port-scan job snapshots sorted by update time."""
    with lock:
        snapshots = [job_snapshot(job) for job in jobs.values()]
    return sorted(
        snapshots,
        key=lambda item: item.get('updated_at') or item.get('created_at') or 0,
        reverse=True,
    )


def update_job(jobs, lock, job_id, **updates):
    """Update a port-scan job and return its latest snapshot."""
    with lock:
        job = jobs.get(job_id)
        if not job:
            return None
        job.update(updates)
        job['updated_at'] = time.time()
        return job_snapshot(job)


def running_count(jobs, lock):
    """Count queued or running port-scan jobs."""
    with lock:
        return len([job for job in jobs.values() if job.get('status') in {'queued', 'running'}])


def run_job(job_id, jobs, lock, enrich_web_port_metadata, record_device_open_ports):
    """Run a cancellable background TCP port scan and persist open-port profiles."""
    from scripts.portScanner import PortScanError, describe_open_ports, identify_port_service, scan_ports

    with lock:
        job = jobs.get(job_id)
        if not job:
            return
        host = job['host']
        start = job['start']
        end = job['end']
        total = job['total_ports']
        job['status'] = 'running'
        job['started_at'] = time.time()
        job['updated_at'] = job['started_at']

    scanned = 0

    def on_open(port):
        service_detail = enrich_web_port_metadata(host, identify_port_service(port))
        with lock:
            current = jobs.get(job_id)
            if not current:
                return
            if port not in current['open_ports']:
                current['open_ports'].append(port)
                current['open_ports'].sort()
                current.setdefault('open_port_details', []).append(service_detail)
                current['open_port_details'] = sorted(
                    current['open_port_details'],
                    key=lambda item: item['port'],
                )
            current['message'] = f"Open port found: {port} ({service_detail['service']})"
            current['updated_at'] = time.time()
        record_device_open_ports(host, [service_detail], source='port-scan-live')

    def should_cancel():
        with lock:
            return bool(jobs.get(job_id, {}).get('cancel_requested'))

    def on_progress(port):
        nonlocal scanned
        scanned += 1
        with lock:
            current = jobs.get(job_id)
            if not current:
                return
            current['scanned_ports'] = scanned
            current['current_port'] = port
            current['progress'] = round((scanned / total) * 100, 1) if total else 100
            current['updated_at'] = time.time()

    try:
        ports = scan_ports(
            host,
            start,
            end,
            on_open=on_open,
            on_progress=on_progress,
            should_cancel=should_cancel,
            max_ports=None,
        )
        if should_cancel():
            update_job(
                jobs,
                lock,
                job_id,
                status='cancelled',
                completed_at=time.time(),
                message='Port scan cancelled.',
            )
            return
        final_details = [enrich_web_port_metadata(host, detail) for detail in describe_open_ports(ports)]
        record_device_open_ports(host, final_details, source='port-scan')
        update_job(
            jobs,
            lock,
            job_id,
            status='complete',
            open_ports=ports,
            open_port_details=final_details,
            scanned_ports=total,
            current_port=end,
            progress=100,
            completed_at=time.time(),
            message=f'Port scan complete: {len(ports)} open port(s) found.',
        )
    except PortScanError as exc:
        update_job(jobs, lock, job_id, status='failed', error=str(exc), message=str(exc), completed_at=time.time())
    except Exception as exc:
        update_job(
            jobs,
            lock,
            job_id,
            status='failed',
            error=str(exc),
            message=f'Port scan failed: {exc}',
            completed_at=time.time(),
        )
