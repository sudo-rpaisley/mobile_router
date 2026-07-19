from flask import Blueprint, jsonify, render_template, request

from scripts.capabilities import build_capabilities, install_host_dependency, install_optional_package


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

    @blueprint.route('/capabilities/registry.json')
    def capability_registry_json():
        return jsonify({'registry': build_capabilities().get('registry', [])})

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


    @blueprint.route('/capabilities/install-host-dependency', methods=['POST'])
    def install_host_dependency_route():
        dependency = request.form.get('dependency')
        confirm = request.form.get('confirm') == 'install'
        if not dependency:
            return jsonify({'status': 'error', 'message': 'Missing dependency'}), 400
        if not confirm:
            return jsonify({'status': 'error', 'message': 'Confirm host package installation before continuing.'}), 400

        try:
            result = install_host_dependency(dependency)
            return jsonify({'status': 'success', **result})
        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return blueprint
