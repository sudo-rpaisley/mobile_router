"""Profile listing, detail, creation, update, and deletion routes."""

from app_support.context import bind_context


def register_social_profile_routes(app, context_provider):
    _refresh_context = bind_context(globals(), context_provider)

    @app.route('/social-engineering')
    @social_login_required()
    @_refresh_context
    def social_engineering_page():
        profiles = owned_social_profiles()
        query = request.args.get('q', '')
        status = request.args.get('status', '')
        tag = request.args.get('tag', '')
        filtered_profiles = social_profile_service.search_profiles(profiles, query, status, tag)
        available_tags = sorted({item for profile in profiles for item in profile.get('tags', [])}, key=str.casefold)
        summary = social_profile_service.dashboard_summary(profiles)
        duplicates = social_profile_service.duplicate_candidates(profiles)
        return render_template(
            'social_engineering.html',
            title='Social Engineering',
            profiles=filtered_profiles, total_profiles=len(profiles), available_tags=available_tags,
            search_query=query, selected_status=status, selected_tag=tag,
            social_user=session.get('social_user'), csrf_token=social_csrf_token(),
            social_audit=recent_social_audit(), summary=summary, duplicates=duplicates,
            **current_context(),
        )

    @app.route('/social-engineering/profiles', methods=['POST'])
    @social_login_required({'editor', 'credential_manager', 'admin'})
    @_refresh_context
    def create_social_profile():
        try:
            profile = social_profile_service.create_profile(request.form, social_profiles, social_profiles_lock)
        except ValueError as exc:
            profiles = owned_social_profiles()
            return render_template(
                'social_engineering.html', title='Social Engineering',
                profiles=profiles, total_profiles=len(profiles), available_tags=[], search_query='', selected_status='', selected_tag='',
                summary=social_profile_service.dashboard_summary(profiles), duplicates=social_profile_service.duplicate_candidates(profiles), social_audit=recent_social_audit(),
                form_values=request.form, error=str(exc), social_user=session.get('social_user'),
                csrf_token=social_csrf_token(), **current_context(),
            ), 400
        with social_profiles_lock:
            social_profiles[profile['id']]['owner'] = current_app_user()['username']
            profile['owner'] = current_app_user()['username']
        try:
            save_social_profile_photo(profile['id'], request.files.get('profile_photo'))
        except ValueError as exc:
            social_profile_service.delete_profile(profile['id'], social_profiles, social_profiles_lock)
            profiles = owned_social_profiles()
            return render_template(
                'social_engineering.html', title='Social Engineering', profiles=profiles, total_profiles=len(profiles), available_tags=[], search_query='', selected_status='', selected_tag='',
                summary=social_profile_service.dashboard_summary(profiles), duplicates=social_profile_service.duplicate_candidates(profiles), social_audit=recent_social_audit(),
                form_values=request.form, error=str(exc), social_user=session.get('social_user'),
                csrf_token=social_csrf_token(), **current_context(),
            ), 400
        record_social_audit('profile.create', profile['id'])
        save_runtime_state('social-profile-create')
        return redirect(url_for('social_profile_detail', profile_id=profile['id']))

    @app.route('/social-engineering/profiles/<profile_id>')
    @social_login_required()
    @_refresh_context
    def social_profile_detail(profile_id):
        profile = owned_social_profile(profile_id)
        if not profile:
            return render_template('social_profile_detail.html', title='Profile not found', profile=None, **current_context()), 404
        for device in profile.get('devices', []):
            device['inventory_match'] = find_inventory_device(device.get('mac')) if device.get('mac') else None
        contact_refs = {
            **{f"email:{email['id']}": {'label': f"{email['label']} email", 'value': email['value'], 'status': email.get('status')} for email in profile.get('emails', [])},
            **({'phone': {'label': 'Phone', 'value': profile['phone'], 'status': profile.get('phone_status')}} if profile.get('phone') else {}),
        }
        for link in profile.get('social_links', []):
            link['recovery_contacts'] = [contact_refs[ref] for ref in link.get('recovery_refs', []) if ref in contact_refs]
        inventory_choices = [
            item for item in inventory_records()
            if (item.get('mac') or item.get('address')) and not item.get('is_control_traffic')
        ]
        user_record = current_user_record() or {}
        owned_profiles = owned_social_profiles()
        vault_credentials = [
            {'id': credential['id'], 'ciphertext': credential.get('secret_ciphertext', '')}
            for owned_profile in owned_profiles for credential in owned_profile.get('credentials', [])
            if credential.get('secret_ciphertext')
        ]
        profile_by_id = {item['id']: item for item in owned_profiles}
        for relationship in profile.get('relationships', []):
            relationship['target'] = profile_by_id.get(relationship.get('target_profile_id'))
        return render_template(
            'social_profile_detail.html', title=profile['full_name'], profile=profile,
            contact_refs=contact_refs, inventory_choices=inventory_choices,
            vault_verifier=user_record.get('vault_verifier', ''), vault_credentials=vault_credentials,
            relationship_choices=[item for item in owned_profiles if item['id'] != profile_id],
            social_user=session.get('social_user'), csrf_token=social_csrf_token(), **current_context(),
        )

    @app.route('/social-engineering/profiles/<profile_id>/photo')
    @social_login_required()
    @_refresh_context
    def social_profile_photo(profile_id):
        profile = owned_social_profile(profile_id)
        if not profile or not profile.get('photo_filename'):
            return '', 404
        return send_from_directory(SOCIAL_PROFILE_PHOTO_DIR, profile['photo_filename'])

    @app.route('/social-engineering/profiles/<profile_id>/update', methods=['POST'])
    @social_login_required({'editor', 'credential_manager', 'admin'})
    @_refresh_context
    def update_social_profile(profile_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        try:
            profile = social_profile_service.update_profile(
                profile_id, request.form, social_profiles, social_profiles_lock,
            )
        except KeyError:
            return json_error('Profile not found', 404)
        except ValueError as exc:
            current = social_profile_service.get_profile(profile_id, social_profiles, social_profiles_lock)
            return render_template(
                'social_profile_detail.html', title=(current or {}).get('full_name', 'Profile'),
                profile={**(current or {}), **request.form}, error=str(exc), social_user=session.get('social_user'),
                csrf_token=social_csrf_token(), contact_refs={}, inventory_choices=[],
                vault_verifier=(current_user_record() or {}).get('vault_verifier', ''), **current_context(),
            ), 400
        try:
            save_social_profile_photo(profile_id, request.files.get('profile_photo'))
        except ValueError as exc:
            return json_error(str(exc))
        record_social_audit('profile.update', profile_id)
        save_runtime_state('social-profile-update')
        return redirect(url_for('social_profile_detail', profile_id=profile['id']))

    @app.route('/social-engineering/profiles/<profile_id>/delete', methods=['POST'])
    @social_login_required({'admin'})
    @_refresh_context
    def delete_social_profile(profile_id):
        profile = owned_social_profile(profile_id)
        if not profile:
            return json_error('Profile not found', 404)
        if not social_profile_service.delete_profile(profile_id, social_profiles, social_profiles_lock):
            return json_error('Profile not found', 404)
        if profile.get('photo_filename'):
            photo_path = os.path.join(SOCIAL_PROFILE_PHOTO_DIR, profile['photo_filename'])
            if os.path.exists(photo_path):
                os.unlink(photo_path)
        for attachment in profile.get('attachments', []):
            attachment_path = os.path.join(SOCIAL_PROFILE_ATTACHMENT_DIR, attachment.get('filename', ''))
            if os.path.isfile(attachment_path):
                os.unlink(attachment_path)
        for collection, directory in (
            (profile.get('identity_documents', []), SOCIAL_PROFILE_ID_DIR),
            (profile.get('signatures', []), SOCIAL_PROFILE_SIGNATURE_DIR),
        ):
            for item in collection:
                path = os.path.join(directory, item.get('filename', ''))
                if os.path.isfile(path):
                    os.unlink(path)
        record_social_audit('profile.delete', profile_id)
        save_runtime_state('social-profile-delete')
        return redirect(url_for('social_engineering_page'))

    return {
        'social_engineering_page': social_engineering_page,
        'create_social_profile': create_social_profile,
        'social_profile_detail': social_profile_detail,
        'social_profile_photo': social_profile_photo,
        'update_social_profile': update_social_profile,
        'delete_social_profile': delete_social_profile
    }
