from flask import Blueprint, current_app, jsonify, render_template, request

from scripts.minecraft_attack import (
    MinecraftAttackError,
    load_mob_mappings,
    run_status_load_test,
    send_mob_toggle,
)


def create_minecraft_blueprint(context_provider):
    blueprint = Blueprint("minecraft", __name__)

    @blueprint.route('/minecraft-attack')
    def minecraft_attack_page():
        context = context_provider()
        return render_template(
            'minecraft_attack.html',
            title='Minecraft Attack',
            mobs=load_mob_mappings(),
            **context,
        )

    @blueprint.route('/minecraft-attack', methods=['POST'])
    def minecraft_attack_route():
        data = request.form
        if data.get('authorized') != 'true':
            return jsonify({'status': 'error', 'message': 'Authorization confirmation is required'}), 400

        host = data.get('host')
        try:
            port = int(data.get('port', 25565))
            requests_count = int(data.get('requests', 25))
            concurrency = int(data.get('concurrency', 5))
            timeout = float(data.get('timeout', 1.5))
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Port, requests, concurrency, and timeout must be numeric'}), 400

        try:
            result = run_status_load_test(host, port, requests_count, concurrency, timeout)
        except MinecraftAttackError as e:
            current_app.logger.info("Minecraft status lab validation failed: %s", e)
            return jsonify({'status': 'error', 'message': str(e)}), 400

        current_app.logger.info(
            "Minecraft status lab completed for host=%s port=%s attempted=%s successful=%s failed=%s",
            host,
            port,
            result.attempted,
            result.successful,
            result.failed,
        )
        return jsonify({'status': 'success', 'result': result.to_dict()})

    @blueprint.route('/minecraft-attack/mobs/<mob_id>/toggle', methods=['POST'])
    def minecraft_mob_toggle_route(mob_id):
        data = request.form
        if data.get('authorized') != 'true':
            return jsonify({'status': 'error', 'message': 'Authorization confirmation is required'}), 400

        host = data.get('host')
        state = data.get('state')
        try:
            timeout = float(data.get('timeout', 1.5))
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Timeout must be numeric'}), 400

        try:
            result = send_mob_toggle(host, mob_id, state, timeout)
        except MinecraftAttackError as e:
            current_app.logger.info("Minecraft mob toggle validation failed for mob=%s: %s", mob_id, e)
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except OSError as e:
            current_app.logger.warning("Minecraft mob toggle connection failed for mob=%s host=%s: %s", mob_id, host, e)
            return jsonify({'status': 'error', 'message': f'Mob toggle connection failed: {str(e)}'}), 502

        current_app.logger.info("Minecraft mob toggled host=%s mob=%s state=%s", host, mob_id, result['state'])
        return jsonify({'status': 'success', 'result': result})

    return blueprint
