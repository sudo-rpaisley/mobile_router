"""Administrator-only guided setup routes."""

from flask import redirect, render_template, request

from app_support.context import bind_context
from services import setup_wizard as setup_wizard_service


def register_setup_wizard_routes(app, context_provider):
    _refresh_context = bind_context(globals(), context_provider)

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

    return {
        'setup_wizard_page': setup_wizard_page,
        'install_setup_component': install_setup_component,
        'complete_setup_wizard': complete_setup_wizard,
    }
