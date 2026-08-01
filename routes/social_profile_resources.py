"""Credentials, devices, vault, relationships, and attachments."""

from functools import wraps


def register_social_profile_resource_routes(app, context_provider):
    globals().update(context_provider())

    def _refresh_context(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            globals().update(context_provider())
            return view(*args, **kwargs)
        return wrapped

    @app.route('/social-engineering/profiles/<profile_id>/credentials', methods=['POST'])
    @social_login_required({'credential_manager', 'admin'})
    @_refresh_context
    def add_social_profile_credential(profile_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        try:
            social_profile_service.add_credential(profile_id, request.form, social_profiles, social_profiles_lock)
        except KeyError:
            return json_error('Profile not found', 404)
        except ValueError as exc:
            return json_error(str(exc))
        record_social_audit('credential.create', profile_id)
        save_runtime_state('social-profile-credential-create')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route('/social-engineering/profiles/<profile_id>/credentials/<credential_id>/delete', methods=['POST'])
    @social_login_required({'credential_manager', 'admin'})
    @_refresh_context
    def delete_social_profile_credential(profile_id, credential_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        try:
            removed = social_profile_service.delete_credential(profile_id, credential_id, social_profiles, social_profiles_lock)
        except KeyError:
            return json_error('Profile not found', 404)
        if not removed:
            return json_error('Credential not found', 404)
        record_social_audit('credential.delete', profile_id)
        save_runtime_state('social-profile-credential-delete')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route('/social-engineering/profiles/<profile_id>/credentials/<credential_id>/update', methods=['POST'])
    @social_login_required({'credential_manager', 'admin'})
    @_refresh_context
    def update_social_profile_credential(profile_id, credential_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        try:
            social_profile_service.update_credential(
                profile_id, credential_id, request.form, social_profiles, social_profiles_lock,
            )
        except KeyError:
            return json_error('Credential not found', 404)
        except ValueError as exc:
            return json_error(str(exc))
        record_social_audit('credential.rotate' if request.form.get('secret_ciphertext') else 'credential.update', profile_id)
        save_runtime_state('social-profile-credential-update')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route('/social-engineering/profiles/<profile_id>/devices', methods=['POST'])
    @social_login_required({'editor', 'credential_manager', 'admin'})
    @_refresh_context
    def add_social_profile_device(profile_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        try:
            social_profile_service.add_device(
                profile_id, request.form, social_profiles, social_profiles_lock, normalize_mac,
            )
        except KeyError:
            return json_error('Profile not found', 404)
        except ValueError as exc:
            return json_error(str(exc))
        record_social_audit('device.create', profile_id)
        save_runtime_state('social-profile-device-create')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route('/social-engineering/profiles/<profile_id>/devices/<device_id>/delete', methods=['POST'])
    @social_login_required({'editor', 'credential_manager', 'admin'})
    @_refresh_context
    def delete_social_profile_device(profile_id, device_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        try:
            removed = social_profile_service.delete_device(profile_id, device_id, social_profiles, social_profiles_lock)
        except KeyError:
            return json_error('Profile not found', 404)
        if not removed:
            return json_error('Device not found', 404)
        record_social_audit('device.delete', profile_id)
        save_runtime_state('social-profile-device-delete')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route('/social-engineering/profiles/<profile_id>/devices/<device_id>/update', methods=['POST'])
    @social_login_required({'editor', 'credential_manager', 'admin'})
    @_refresh_context
    def update_social_profile_device(profile_id, device_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        try:
            social_profile_service.update_device(
                profile_id, device_id, request.form, social_profiles, social_profiles_lock, normalize_mac,
            )
        except KeyError:
            return json_error('Device not found', 404)
        except ValueError as exc:
            return json_error(str(exc))
        record_social_audit('device.update', profile_id)
        save_runtime_state('social-profile-device-update')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route('/vault-verifier', methods=['POST'])
    @social_login_required()
    @_refresh_context
    def save_vault_verifier():
        verifier = str(request.form.get('vault_verifier') or '')
        if not verifier.startswith('vault:v1:') or len(verifier) > 20000:
            return json_error('Invalid vault verifier.')
        username = current_app_user()['username']
        with social_users_lock:
            user = social_users.get(username)
            if not user:
                return json_error('User not found.', 404)
            if user.get('vault_verifier'):
                return json_error('Vault verifier is already configured.', 409)
            user['vault_verifier'] = verifier
        record_social_audit('vault.initialize')
        save_runtime_state('vault-verifier')
        return json_success()

    @app.route('/vault-rotate', methods=['POST'])
    @social_login_required({'credential_manager', 'admin'})
    @_refresh_context
    def rotate_vault():
        verifier = str(request.form.get('vault_verifier') or '')
        try:
            replacements = json.loads(request.form.get('credentials') or '{}')
        except json.JSONDecodeError:
            return json_error('Invalid credential rotation payload.')
        if not verifier.startswith('vault:v1:') or not isinstance(replacements, dict):
            return json_error('Invalid vault rotation payload.')
        username = current_app_user()['username']
        profiles = owned_social_profiles()
        expected = {item['id'] for profile in profiles for item in profile.get('credentials', []) if item.get('secret_ciphertext')}
        if set(replacements) != expected or any(not str(value).startswith('vault:v1:') for value in replacements.values()):
            return json_error('Every encrypted credential must be rotated together.')
        with social_profiles_lock:
            for profile in social_profiles.values():
                if profile.get('owner') != username:
                    continue
                for credential in profile.get('credentials', []):
                    if credential.get('id') in replacements:
                        credential['secret_ciphertext'] = replacements[credential['id']]
                        credential['rotated_at'] = time.time()
        with social_users_lock:
            social_users[username]['vault_verifier'] = verifier
        record_social_audit('vault.rotate')
        save_runtime_state('vault-rotate')
        return json_success()

    @app.route('/social-engineering/profiles/<profile_id>/relationships', methods=['POST'])
    @social_login_required({'editor', 'admin'})
    @_refresh_context
    def add_social_profile_relationship(profile_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        try:
            social_profile_service.add_relationship(profile_id, request.form, social_profiles, social_profiles_lock)
        except (KeyError, ValueError) as exc:
            return json_error(str(exc))
        record_social_audit('relationship.create', profile_id)
        save_runtime_state('relationship-create')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route('/social-engineering/profiles/<profile_id>/relationships/<relationship_id>/delete', methods=['POST'])
    @social_login_required({'editor', 'admin'})
    @_refresh_context
    def delete_social_profile_relationship(profile_id, relationship_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        social_profile_service.delete_relationship(profile_id, relationship_id, social_profiles, social_profiles_lock)
        record_social_audit('relationship.delete', profile_id)
        save_runtime_state('relationship-delete')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route('/social-engineering/profiles/merge', methods=['POST'])
    @social_login_required({'editor', 'admin'})
    @_refresh_context
    def merge_social_profiles():
        primary_id, duplicate_id = request.form.get('primary_id'), request.form.get('duplicate_id')
        if not owned_social_profile(primary_id) or not owned_social_profile(duplicate_id):
            return json_error('Profile not found', 404)
        try:
            social_profile_service.merge_profiles(primary_id, duplicate_id, social_profiles, social_profiles_lock)
        except (KeyError, ValueError) as exc:
            return json_error(str(exc))
        record_social_audit('profile.merge', primary_id, duplicate_id)
        save_runtime_state('profile-merge')
        return redirect(url_for('social_profile_detail', profile_id=primary_id))

    @app.route('/social-engineering/profiles/<profile_id>/attachments', methods=['POST'])
    @social_login_required({'editor', 'admin'})
    @_refresh_context
    def add_social_profile_attachment(profile_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        upload = request.files.get('attachment')
        if not upload or not upload.filename:
            return json_error('Choose a file to attach.')
        content = upload.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            return json_error('Attachments must be 10 MB or smaller.')
        safe_name = secure_filename(upload.filename) or 'attachment'
        filename = f'{profile_id}-{uuid.uuid4()}-{safe_name}'
        os.makedirs(SOCIAL_PROFILE_ATTACHMENT_DIR, exist_ok=True)
        with open(os.path.join(SOCIAL_PROFILE_ATTACHMENT_DIR, filename), 'wb') as handle:
            handle.write(content)
        social_profile_service.add_attachment(profile_id, {
            'filename': filename, 'original_name': safe_name, 'description': request.form.get('description'),
            'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content),
        }, social_profiles, social_profiles_lock)
        record_social_audit('attachment.create', profile_id, safe_name)
        save_runtime_state('attachment-create')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route('/social-engineering/profiles/<profile_id>/attachments/<attachment_id>')
    @social_login_required()
    @_refresh_context
    def download_social_profile_attachment(profile_id, attachment_id):
        profile = owned_social_profile(profile_id)
        item = next((entry for entry in (profile or {}).get('attachments', []) if entry.get('id') == attachment_id), None)
        if not item:
            return json_error('Attachment not found', 404)
        record_social_audit('attachment.download', profile_id, item['original_name'])
        return send_from_directory(SOCIAL_PROFILE_ATTACHMENT_DIR, item['filename'], as_attachment=True, download_name=item['original_name'])

    @app.route('/social-engineering/profiles/<profile_id>/attachments/<attachment_id>/delete', methods=['POST'])
    @social_login_required({'editor', 'admin'})
    @_refresh_context
    def delete_social_profile_attachment(profile_id, attachment_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        item = social_profile_service.delete_attachment(profile_id, attachment_id, social_profiles, social_profiles_lock)
        if not item:
            return json_error('Attachment not found', 404)
        path = os.path.join(SOCIAL_PROFILE_ATTACHMENT_DIR, item['filename'])
        if os.path.isfile(path):
            os.unlink(path)
        record_social_audit('attachment.delete', profile_id, item['original_name'])
        save_runtime_state('attachment-delete')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    return {
        'add_social_profile_credential': add_social_profile_credential,
        'delete_social_profile_credential': delete_social_profile_credential,
        'update_social_profile_credential': update_social_profile_credential,
        'add_social_profile_device': add_social_profile_device,
        'delete_social_profile_device': delete_social_profile_device,
        'update_social_profile_device': update_social_profile_device,
        'save_vault_verifier': save_vault_verifier,
        'rotate_vault': rotate_vault,
        'add_social_profile_relationship': add_social_profile_relationship,
        'delete_social_profile_relationship': delete_social_profile_relationship,
        'merge_social_profiles': merge_social_profiles,
        'add_social_profile_attachment': add_social_profile_attachment,
        'download_social_profile_attachment': download_social_profile_attachment,
        'delete_social_profile_attachment': delete_social_profile_attachment
    }
