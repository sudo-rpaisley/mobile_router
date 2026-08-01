"""Authentication and local application-user routes."""

from functools import wraps


def register_social_auth_routes(app, context_provider):
    globals().update(context_provider())

    def _refresh_context(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            globals().update(context_provider())
            return view(*args, **kwargs)
        return wrapped

    @app.route('/setup', methods=['GET', 'POST'])
    @_refresh_context
    def social_auth_setup():
        if social_users:
            return redirect(url_for('social_auth_login'))
        if request.method == 'POST':
            if not secrets.compare_digest(str(request.form.get('csrf_token') or ''), social_csrf_token()):
                return json_error('Invalid or expired form token.', 400)
            try:
                user = social_auth_service.create_user(
                    request.form.get('username'), request.form.get('password'), 'admin',
                    social_users, social_users_lock,
                )
            except ValueError as exc:
                return render_template('social_auth.html', title='Social Profile Setup', mode='setup', error=str(exc), csrf_token=social_csrf_token(), **current_context()), 400
            session['social_user'] = {'username': user['username'], 'role': user['role']}
            with social_profiles_lock:
                for profile in social_profiles.values():
                    profile.setdefault('owner', user['username'])
            record_social_audit('auth.setup')
            save_runtime_state('social-auth-setup')
            return redirect(url_for('social_engineering_page'))
        return render_template('social_auth.html', title='Social Profile Setup', mode='setup', csrf_token=social_csrf_token(), **current_context())

    @app.route('/login', methods=['GET', 'POST'])
    @_refresh_context
    def social_auth_login():
        if not social_users:
            return redirect(url_for('social_auth_setup'))
        if request.method == 'POST':
            if not secrets.compare_digest(str(request.form.get('csrf_token') or ''), social_csrf_token()):
                return json_error('Invalid or expired form token.', 400)
            user = social_auth_service.authenticate(
                request.form.get('username'), request.form.get('password'), social_users, social_users_lock,
            )
            if not user:
                return render_template('social_auth.html', title='Social Profile Login', mode='login', error='Invalid username or password.', csrf_token=social_csrf_token(), **current_context()), 401
            session['social_user'] = {'username': user['username'], 'role': user['role']}
            record_social_audit('auth.login')
            save_runtime_state('social-auth-login')
            return redirect(url_for('social_engineering_page'))
        return render_template('social_auth.html', title='Social Profile Login', mode='login', csrf_token=social_csrf_token(), **current_context())

    @app.route('/logout', methods=['POST'])
    @social_login_required()
    @_refresh_context
    def social_auth_logout():
        record_social_audit('auth.logout')
        save_runtime_state('social-auth-logout')
        session.pop('social_user', None)
        return redirect(url_for('social_auth_login'))

    @app.route('/social-engineering/setup')
    @_refresh_context
    def legacy_social_auth_setup():
        return redirect(url_for('social_auth_setup'))

    @app.route('/social-engineering/login')
    @_refresh_context
    def legacy_social_auth_login():
        return redirect(url_for('social_auth_login'))

    @app.route('/users')
    @social_login_required({'admin'})
    @_refresh_context
    def application_users_page():
        with social_users_lock:
            users = [dict(user) for user in social_users.values()]
        return render_template('application_users.html', title='User Management', users=users, csrf_token=social_csrf_token(), **current_context())

    @app.route('/users', methods=['POST'])
    @social_login_required({'admin'})
    @_refresh_context
    def create_application_user():
        try:
            user = social_auth_service.create_user(
                request.form.get('username'), request.form.get('password'), request.form.get('role'),
                social_users, social_users_lock,
            )
        except ValueError as exc:
            with social_users_lock:
                users = [dict(item) for item in social_users.values()]
            return render_template('application_users.html', title='User Management', users=users, error=str(exc), csrf_token=social_csrf_token(), **current_context()), 400
        record_social_audit('user.create', detail=f"{user['username']}:{user['role']}")
        save_runtime_state('application-user-create')
        return redirect(url_for('application_users_page'))

    return {
        'social_auth_setup': social_auth_setup,
        'social_auth_login': social_auth_login,
        'social_auth_logout': social_auth_logout,
        'legacy_social_auth_setup': legacy_social_auth_setup,
        'legacy_social_auth_login': legacy_social_auth_login,
        'application_users_page': application_users_page,
        'create_application_user': create_application_user
    }
