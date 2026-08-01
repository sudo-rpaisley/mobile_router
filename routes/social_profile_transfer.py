"""Profile import, export, and auditable client actions."""

from functools import wraps


def register_social_profile_transfer_routes(app, context_provider):
    globals().update(context_provider())

    def _refresh_context(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            globals().update(context_provider())
            return view(*args, **kwargs)
        return wrapped

    @app.route('/social-engineering/export')
    @social_login_required()
    @_refresh_context
    def export_social_profiles():
        profiles = owned_social_profiles()
        if request.args.get('format') == 'csv':
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['full_name', 'organization', 'job_title', 'phone', 'emails', 'tags', 'status'])
            writer.writeheader()
            for item in profiles:
                writer.writerow({'full_name': item['full_name'], 'organization': item.get('organization'), 'job_title': item.get('job_title'),
                                 'phone': item.get('phone'), 'emails': ', '.join(email['value'] for email in item.get('emails', [])),
                                 'tags': ', '.join(item.get('tags', [])), 'status': item.get('profile_status')})
            return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=contacts.csv'})
        safe_profiles = [{key: value for key, value in item.items() if key != 'credentials'} for item in profiles]
        return Response(json.dumps({'profiles': safe_profiles}, indent=2), mimetype='application/json', headers={'Content-Disposition': 'attachment; filename=contacts.json'})

    @app.route('/social-engineering/import', methods=['POST'])
    @social_login_required({'editor', 'admin'})
    @_refresh_context
    def import_social_profiles():
        upload = request.files.get('contacts_file')
        if not upload:
            return json_error('Choose a JSON contacts export.')
        try:
            payload = json.loads(upload.read(2 * 1024 * 1024).decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return json_error('The contacts file is not valid JSON.')
        records = payload.get('profiles', []) if isinstance(payload, dict) else []
        if not isinstance(records, list) or len(records) > 1000:
            return json_error('The contacts export is invalid or too large.')
        created = 0
        for record in records:
            if not isinstance(record, dict):
                continue
            values = {'full_name': record.get('full_name'), 'organization': record.get('organization'),
                      'job_title': record.get('job_title'), 'phone': record.get('phone'), 'notes': record.get('notes'),
                      'phone_status': record.get('phone_status'), 'phone_source': record.get('phone_source'),
                      'phone_confidence': record.get('phone_confidence'), 'phone_verified_date': record.get('phone_verified_date'),
                      'tags': ','.join(record.get('tags', [])), 'profile_status': record.get('profile_status'),
                      'authorization_basis': record.get('authorization_basis'), 'review_date': record.get('review_date'),
                      'retention_until': record.get('retention_until'),
                      'email_id': [item.get('id') for item in record.get('emails', [])],
                      'email_label': [item.get('label') for item in record.get('emails', [])],
                      'email_value': [item.get('value') for item in record.get('emails', [])],
                      'email_status': [item.get('status') for item in record.get('emails', [])],
                      'email_source': [item.get('source') for item in record.get('emails', [])],
                      'email_confidence': [item.get('confidence') for item in record.get('emails', [])],
                      'email_verified_date': [item.get('verified_date') for item in record.get('emails', [])],
                      'custom_field_name': [item.get('name') for item in record.get('custom_fields', [])],
                      'custom_field_value': [item.get('value') for item in record.get('custom_fields', [])],
                      'custom_field_type': [item.get('type') for item in record.get('custom_fields', [])]}
            try:
                profile = social_profile_service.create_profile(values, social_profiles, social_profiles_lock)
            except ValueError:
                continue
            with social_profiles_lock:
                social_profiles[profile['id']]['owner'] = current_app_user()['username']
            created += 1
        record_social_audit('profiles.import', detail=str(created))
        save_runtime_state('profiles-import')
        return redirect(url_for('social_engineering_page'))

    @app.route('/social-engineering/profiles/<profile_id>/audit', methods=['POST'])
    @social_login_required()
    @_refresh_context
    def social_profile_client_audit(profile_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        action = str(request.form.get('action') or '')
        if action not in {'credential.reveal', 'vault.unlock'}:
            return json_error('Unsupported audit action.')
        record_social_audit(action, profile_id)
        save_runtime_state('social-profile-audit')
        return json_success()

    return {
        'export_social_profiles': export_social_profiles,
        'import_social_profiles': import_social_profiles,
        'social_profile_client_audit': social_profile_client_audit
    }
