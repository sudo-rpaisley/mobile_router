"""Identity-document and signature routes for social profiles."""

from app_support.context import bind_context


def register_social_profile_identity_routes(app, context_provider):
    _refresh_context = bind_context(globals(), context_provider)

    @app.route('/social-engineering/profiles/<profile_id>/identity-documents', methods=['POST'])
    @social_login_required({'editor', 'admin'})
    @_refresh_context
    def add_identity_document(profile_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        try:
            image = save_profile_image(
                request.files.get('identity_image'),
                SOCIAL_PROFILE_ID_DIR,
                f'{profile_id}-id',
            )
        except ValueError as exc:
            return json_error(str(exc))
        path = os.path.join(SOCIAL_PROFILE_ID_DIR, image['filename'])
        ocr_text, ocr_status = identity_image_ocr(path)
        detected = identity_ocr_fields(ocr_text)
        document = {
            'id': str(uuid.uuid4()),
            **image,
            'document_type': str(request.form.get('document_type') or 'other')[:100],
            'document_number': str(
                request.form.get('document_number') or detected['document_number']
            )[:200],
            'issuing_country': str(request.form.get('issuing_country') or '')[:100],
            'date_of_birth': str(
                request.form.get('date_of_birth') or detected['date_of_birth']
            )[:100],
            'issue_date': str(request.form.get('issue_date') or '')[:100],
            'expiry_date': str(
                request.form.get('expiry_date') or detected['expiry_date']
            )[:100],
            'address': str(request.form.get('address') or '')[:1000],
            'notes': str(request.form.get('notes') or '')[:2000],
            'ocr_text': ocr_text[:20000],
            'ocr_status': ocr_status,
            'detected_dates': detected['detected_dates'],
            'created_at': time.time(),
            'updated_at': time.time(),
        }
        with social_profiles_lock:
            social_profiles[profile_id].setdefault('identity_documents', []).append(document)
        record_social_audit(
            'identity-document.create', profile_id, document['document_type']
        )
        save_runtime_state('identity-document-create')
        return redirect(
            url_for(
                'identity_document_detail',
                profile_id=profile_id,
                document_id=document['id'],
            )
        )

    @app.route(
        '/social-engineering/profiles/<profile_id>/identity-documents/<document_id>',
        methods=['GET', 'POST'],
    )
    @social_login_required()
    @_refresh_context
    def identity_document_detail(profile_id, document_id):
        profile = owned_social_profile(profile_id)
        document = next(
            (
                item
                for item in (profile or {}).get('identity_documents', [])
                if item.get('id') == document_id
            ),
            None,
        )
        if not document:
            return render_template(
                'identity_document.html',
                title='Identity document not found',
                profile=profile,
                document=None,
                **current_context(),
            ), 404
        if request.method == 'POST':
            if current_app_user().get('role') not in {'editor', 'admin'}:
                return json_error('You do not have permission for this action.', 403)
            fields = (
                'document_type',
                'document_number',
                'issuing_country',
                'date_of_birth',
                'issue_date',
                'expiry_date',
                'address',
                'notes',
            )
            with social_profiles_lock:
                stored = next(
                    item
                    for item in social_profiles[profile_id].setdefault(
                        'identity_documents', []
                    )
                    if item.get('id') == document_id
                )
                for field in fields:
                    limit = 2000 if field in {'address', 'notes'} else 200
                    stored[field] = str(request.form.get(field) or '').strip()[:limit]
                stored['updated_at'] = time.time()
            record_social_audit('identity-document.update', profile_id, document_id)
            save_runtime_state('identity-document-update')
            return redirect(
                url_for(
                    'identity_document_detail',
                    profile_id=profile_id,
                    document_id=document_id,
                    saved=1,
                )
            )
        return render_template(
            'identity_document.html',
            title=f"{profile['full_name']} identity document",
            profile=profile,
            document=document,
            csrf_token=social_csrf_token(),
            **current_context(),
        )

    @app.route(
        '/social-engineering/profiles/<profile_id>/identity-documents/<document_id>/image'
    )
    @social_login_required()
    @_refresh_context
    def identity_document_image(profile_id, document_id):
        profile = owned_social_profile(profile_id)
        document = next(
            (
                item
                for item in (profile or {}).get('identity_documents', [])
                if item.get('id') == document_id
            ),
            None,
        )
        if not document:
            return json_error('Identity document not found', 404)
        return send_from_directory(SOCIAL_PROFILE_ID_DIR, document['filename'])

    @app.route(
        '/social-engineering/profiles/<profile_id>/identity-documents/<document_id>/delete',
        methods=['POST'],
    )
    @social_login_required({'editor', 'admin'})
    @_refresh_context
    def delete_identity_document(profile_id, document_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        with social_profiles_lock:
            items = social_profiles[profile_id].setdefault('identity_documents', [])
            document = next(
                (item for item in items if item.get('id') == document_id), None
            )
            if document:
                social_profiles[profile_id]['identity_documents'] = [
                    item for item in items if item.get('id') != document_id
                ]
        if not document:
            return json_error('Identity document not found', 404)
        path = os.path.join(SOCIAL_PROFILE_ID_DIR, document['filename'])
        if os.path.isfile(path):
            os.unlink(path)
        record_social_audit('identity-document.delete', profile_id, document_id)
        save_runtime_state('identity-document-delete')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route('/social-engineering/profiles/<profile_id>/signatures', methods=['POST'])
    @social_login_required({'editor', 'admin'})
    @_refresh_context
    def add_profile_signature(profile_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        try:
            image = save_profile_image(
                request.files.get('signature_image'),
                SOCIAL_PROFILE_SIGNATURE_DIR,
                f'{profile_id}-signature',
            )
        except ValueError as exc:
            return json_error(str(exc))
        signature = {
            'id': str(uuid.uuid4()),
            **image,
            'label': str(request.form.get('label') or 'Signature')[:200],
            'signed_at': str(request.form.get('signed_at') or '')[:100],
            'notes': str(request.form.get('notes') or '')[:2000],
            'created_at': time.time(),
        }
        with social_profiles_lock:
            social_profiles[profile_id].setdefault('signatures', []).append(signature)
        record_social_audit('signature.create', profile_id, signature['label'])
        save_runtime_state('signature-create')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    @app.route(
        '/social-engineering/profiles/<profile_id>/signatures/<signature_id>/image'
    )
    @social_login_required()
    @_refresh_context
    def profile_signature_image(profile_id, signature_id):
        profile = owned_social_profile(profile_id)
        signature = next(
            (
                item
                for item in (profile or {}).get('signatures', [])
                if item.get('id') == signature_id
            ),
            None,
        )
        if not signature:
            return json_error('Signature not found', 404)
        return send_from_directory(SOCIAL_PROFILE_SIGNATURE_DIR, signature['filename'])

    @app.route(
        '/social-engineering/profiles/<profile_id>/signatures/<signature_id>/delete',
        methods=['POST'],
    )
    @social_login_required({'editor', 'admin'})
    @_refresh_context
    def delete_profile_signature(profile_id, signature_id):
        if not owned_social_profile(profile_id):
            return json_error('Profile not found', 404)
        with social_profiles_lock:
            items = social_profiles[profile_id].setdefault('signatures', [])
            signature = next(
                (item for item in items if item.get('id') == signature_id), None
            )
            if signature:
                social_profiles[profile_id]['signatures'] = [
                    item for item in items if item.get('id') != signature_id
                ]
        if not signature:
            return json_error('Signature not found', 404)
        path = os.path.join(SOCIAL_PROFILE_SIGNATURE_DIR, signature['filename'])
        if os.path.isfile(path):
            os.unlink(path)
        record_social_audit('signature.delete', profile_id, signature_id)
        save_runtime_state('signature-delete')
        return redirect(url_for('social_profile_detail', profile_id=profile_id))

    return {
        'add_identity_document': add_identity_document,
        'identity_document_detail': identity_document_detail,
        'identity_document_image': identity_document_image,
        'delete_identity_document': delete_identity_document,
        'add_profile_signature': add_profile_signature,
        'profile_signature_image': profile_signature_image,
        'delete_profile_signature': delete_profile_signature,
    }
