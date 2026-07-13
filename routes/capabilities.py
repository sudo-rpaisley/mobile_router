from flask import Blueprint, jsonify, render_template, request

from scripts.capabilities import build_capabilities, install_optional_package


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

    @blueprint.route('/capabilities/install-package', methods=['POST'])
    def install_package():
        package = request.form.get('package')
        if not package:
            return jsonify({'status': 'error', 'message': 'Missing package'}), 400

        try:
            result = install_optional_package(package)
            return jsonify({'status': 'success', **result})
        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return blueprint
