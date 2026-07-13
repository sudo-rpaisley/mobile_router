from flask import Blueprint, render_template

from scripts.capabilities import build_capabilities


def create_capabilities_blueprint(context_provider):
    blueprint = Blueprint("capabilities", __name__)

    @blueprint.route('/capabilities')
    def capabilities_page():
        context = context_provider()
        return render_template(
            'capabilities.html',
            title='Capabilities',
            capabilities=build_capabilities(),
            **context,
        )

    return blueprint
