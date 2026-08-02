"""Authentication, first-run setup, and local application-user routes."""

from app_support import navigation as navigation_service
from app_support.context import bind_context
from services import setup_wizard as setup_wizard_service


def register_social_auth_routes(app, context_provider):
    _refresh_context = bind_context(globals(), context_provider)

    @app.context_processor
    def inject_navigation_context():
        context = context_provider()
        record = current_user_record()
        app_user = (
            social_auth_service.public_user(record)
            if record else current_app_user()
        )

        def app_navigation(title=''):
            return navigation_service.build_navigation_context(
                request.path,
                title,
                request.endpoint,
                app_user,
                context.get('networkTechnologies', ()),
                context.get('network_interfaces', ()),
            )

        return {'app_user': app_user, 'app_navigation': app_navigation}

    def account_page_response(error=None, status=200):
        record = current_user_record() or {}
        user = social_auth_service.public_user(record) or {}
        created_at = user.get('created_at')
        password_changed_at = user.get('password_changed_at')
        response = render_template(
            'account_profile.html',
            title='My Account',
            user=user,
            landing_pages=social_auth_service.LANDING_PAGES,
            error=error,
            saved=request.args.get('saved'),
            created_at_label=(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_at))
                if created_at else 'Unknown'
            ),
            password_changed_at_label=(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(password_changed_at))
                if password_changed_at else 'Not recorded'
            ),
            csrf_token=social_csrf_token(),
            **current_context(),
        )
        return (response, status) if status != 200 else response

    def setup_wizard_response(error=None, status=200):
        record = current_user_record() or {}
        state = setup_wizard_service.setup_state(record)
        response = render_template(
            'setup_wizard.html',
            title='Setup Wizard',
            components=setup_wizard_service.component_catalog(),
            setup_state=state,
            first_run=setup_wizard_service.setup_required(record),
            error=error,
            csrf_token=social_csrf_token(),
            **current_context(),
        )
        return (response, status) if status != 200 else response

    @app.route('/setup', methods=['GET', 'POST'])
    @_refresh_context
    def social_auth_setup():
        next_url = request.form.get('next') or request.args.get('next', '')
        if social_users:
            return redirect(url_for('social_auth_login', next=next_url))
        if request.method == 'POST':
            if not secrets.compare_digest(
                str(request.form.get('csrf_token') or ''), social_csrf_token()
            ):
                return json_error('Invalid or expired form token.', 400)
            try:
                user = social_auth_service.create_user(
                    request.form.get('username'),
                    request.form.get('password'),
                    'admin',
                    social_users,
                    social_users_lock,
                )
                setup_wizard_service.begin_setup(
                    user['username'], social_users, social_users_lock
                )
            except ValueError as exc:
                return render_template(
                    'social_auth.html',
                    title='Social Profile Setup',
                    mode='setup',
                    error=str(exc),
                    next_url=next_url,
                    csrf_token=social_csrf_token(),
                    **current_context(),
                ), 400
            session['social_user'] = {
                'username': user['username'],
                'role': user['role'],
            }
            with social_profiles_lock:
                for profile in social_profiles.values():
                    profile.setdefault('owner', user['username'])
            record_social_audit('auth.setup')
            save_runtime_state('social-auth-setup')
            return redirect(url_for('setup_wizard_page'))
        return render_template(
            'social_auth.html',
            title='Social Profile Setup',
            mode='setup',
            next_url=next_url,
            csrf_token=social_csrf_token(),
            **current_context(),
        )

    @app.route('/login', methods=['GET', 'POST'])
    @_refresh_context
    def social_auth_login():
        next_url = request.form.get('next') or request.args.get('next', '')
        if not social_users:
            return redirect(url_for('social_auth_setup', next=next_url))
        if request.method == 'POST':
            if not secrets.compare_digest(
                str(request.form.get('csrf_token') or ''), social_csrf_token()
            ):
                return json_error('Invalid or expired form token.', 400)
            user = social_auth_service.authenticate(
                request.form.get('username'),
                request.form.get('password'),
                social_users,
                social_users_lock,
            )
            if not user:
                return render_template(
                    'social_auth.html',
                    title='Social Profile Login',
                    mode='login',
                    error='Invalid username or password.',
                    next_url=next_url,
                    csrf_token=social_csrf_token(),
                    **current_context(),
                ), 401
            session['social_user'] = {
                'username': user['username'],
                'role': user['role'],
            }
            record_social_audit('auth.login')
            save_runtime_state('social-auth-login')
            if setup_wizard_service.setup_required(user):
                return redirect(url_for('setup_wizard_page'))
            destination = (
                login_destination(next_url)
                if next_url else social_auth_service.default_landing_page(user)
            )
            return redirect(destination)
        return render_template(
            'social_auth.html',
            title='Social Profile Login',
            mode='login',
            next_url=next_url,
            csrf_token=social_csrf_token(),
            **current_context(),
        )

    @app.route('/logout', methods=['POST'])
    @social_login_required()
    @_refresh_context
    def social_auth_logout():
        record_social_audit('auth.logout')
        save_runtime_state('social-auth-logout')
        session.pop('social_user', None)
        return redirect(url_for('social_auth_login'))

    @app.route('/setup-wizard')
    @social_login_required({'admin'})
    @_refresh_context
    def setup_wizard_page():
        return setup_wizard_response()

    @app.route('/setup-wizard/install', methods=['POST'])
    @social_login_required({'admin'})
    @_refresh_context
    def install_setup_component():
        username = (current_app_user() or {}).get('username')
        component_id = request.form.get('component')
        if not component_id:
            return json_error('Choose a setup component.', 400)
        try:
            result = setup_wizard_service.install_component(component_id)
            setup_wizard_service.record_component_result(
                username,
                component_id,
                'installed' if result.get('installed') else 'warning',
                result.get('message'),
                result,
                social_users,
                social_users_lock,
            )
        except ValueError as exc:
            return json_error(str(exc), 400)
        except Exception as exc:
            setup_wizard_service.record_component_result(
                username,
                component_id,
                'failed',
                str(exc),
                {},
                social_users,
                social_users_lock,
            )
            record_social_audit(
                'setup.component.failed', detail=f'{component_id}:{exc}'
            )
            save_runtime_state('setup-component-failed')
            return json_error(str(exc), 500)
        record_social_audit('setup.component.install', detail=component_id)
        save_runtime_state('setup-component-install')
        return json_success(result=result)

    @app.route('/setup-wizard/complete', methods=['POST'])
    @social_login_required({'admin'})
    @_refresh_context
    def complete_setup_wizard():
        username = (current_app_user() or {}).get('username')
        mode = request.form.get('mode') or 'completed'
        try:
            state = setup_wizard_service.complete_setup(
                username, mode, social_users, social_users_lock
            )
        except ValueError as exc:
            return json_error(str(exc), 400)
        record_social_audit('setup.complete', detail=mode)
        save_runtime_state('setup-wizard-complete')
        record = current_user_record() or {}
        destination = social_auth_service.default_landing_page(record)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_success(state=state, redirect=destination)
        return redirect(destination)

    @app.route('/account')
    @social_login_required()
    @_refresh_context
    def application_account_page():
        return account_page_response()

    @app.route('/account/profile', methods=['POST'])
    @social_login_required()
    @_refresh_context
    def update_application_account():
        username = (current_app_user() or {}).get('username')
        try:
            social_auth_service.update_user_profile(
                username,
                request.form.get('display_name'),
                request.form.get('email'),
                request.form.get('default_landing_page'),
                request.form.get('compact_layout'),
                request.form.get('reduced_motion'),
                social_users,
                social_users_lock,
            )
        except ValueError as exc:
            return account_page_response(str(exc), 400)
        record_social_audit('account.profile.update')
        save_runtime_state('account-profile-update')
        return redirect(url_for('application_account_page', saved='profile'))

    @app.route('/account/password', methods=['POST'])
    @social_login_required()
    @_refresh_context
    def change_application_password():
        username = (current_app_user() or {}).get('username')
        try:
            social_auth_service.change_password(
                username,
                request.form.get('current_password'),
                request.form.get('new_password'),
                request.form.get('confirm_password'),
                social_users,
                social_users_lock,
            )
        except ValueError as exc:
            return account_page_response(str(exc), 400)
        record_social_audit('account.password.change')
        save_runtime_state('account-password-change')
        return redirect(url_for('application_account_page', saved='password'))

    @app.route('/account/favourites', methods=['POST'])
    @social_login_required()
    @_refresh_context
    def update_application_favourites():
        username = (current_app_user() or {}).get('username')
        requested_url = request.form.get('url') or '/'
        safe_url = login_destination(requested_url)
        try:
            favourites = social_auth_service.update_favourite(
                username,
                safe_url,
                request.form.get('label'),
                request.form.get('action'),
                social_users,
                social_users_lock,
            )
        except ValueError as exc:
            return json_error(str(exc), 400)
        record_social_audit(
            'account.favourite.update',
            detail=f"{request.form.get('action') or 'add'}:{safe_url}",
        )
        save_runtime_state('account-favourite-update')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_success(favourites=favourites)
        return redirect(url_for('application_account_page', saved='favourites'))

    @app.route('/social-engineering/setup')
    @_refresh_context
    def legacy_social_auth_setup():
        return redirect(
            url_for('social_auth_setup', next=request.args.get('next', ''))
        )

    @app.route('/social-engineering/login')
    @_refresh_context
    def legacy_social_auth_login():
        return redirect(
            url_for('social_auth_login', next=request.args.get('next', ''))
        )

    @app.route('/users')
    @social_login_required({'admin'})
    @_refresh_context
    def application_users_page():
        with social_users_lock:
            users = [social_auth_service.public_user(user) for user in social_users.values()]
        return render_template(
            'application_users.html',
            title='User Management',
            users=users,
            csrf_token=social_csrf_token(),
            **current_context(),
        )

    @app.route('/users', methods=['POST'])
    @social_login_required({'admin'})
    @_refresh_context
    def create_application_user():
        try:
            user = social_auth_service.create_user(
                request.form.get('username'),
                request.form.get('password'),
                request.form.get('role'),
                social_users,
                social_users_lock,
            )
        except ValueError as exc:
            with social_users_lock:
                users = [
                    social_auth_service.public_user(item)
                    for item in social_users.values()
                ]
            return render_template(
                'application_users.html',
                title='User Management',
                users=users,
                error=str(exc),
                csrf_token=social_csrf_token(),
                **current_context(),
            ), 400
        record_social_audit(
            'user.create', detail=f"{user['username']}:{user['role']}"
        )
        save_runtime_state('application-user-create')
        return redirect(url_for('application_users_page'))

    return {
        'social_auth_setup': social_auth_setup,
        'social_auth_login': social_auth_login,
        'social_auth_logout': social_auth_logout,
        'setup_wizard_page': setup_wizard_page,
        'install_setup_component': install_setup_component,
        'complete_setup_wizard': complete_setup_wizard,
        'application_account_page': application_account_page,
        'update_application_account': update_application_account,
        'change_application_password': change_application_password,
        'update_application_favourites': update_application_favourites,
        'legacy_social_auth_setup': legacy_social_auth_setup,
        'legacy_social_auth_login': legacy_social_auth_login,
        'application_users_page': application_users_page,
        'create_application_user': create_application_user,
    }