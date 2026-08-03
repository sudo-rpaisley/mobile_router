from .bluetooth_phone import create_bluetooth_phone_blueprint
from .capabilities import create_capabilities_blueprint
from .minecraft import create_minecraft_blueprint
from .train_controller import create_train_controller_blueprint
from .automotive import create_automotive_blueprint
from .deauth_control import create_deauth_control_blueprint
from .device_identification import create_device_identification_blueprint
from .port_knowledge import create_port_knowledge_blueprint
from .model_profiles import create_model_profiles_blueprint
from .service_records import create_service_records_blueprint
from .host_facts import create_host_facts_blueprint


def register_blueprints(app, context_provider):
    app.register_blueprint(create_bluetooth_phone_blueprint(context_provider))
    app.register_blueprint(create_capabilities_blueprint(context_provider))
    app.register_blueprint(create_minecraft_blueprint(context_provider))
    app.register_blueprint(create_train_controller_blueprint(context_provider))
    app.register_blueprint(create_automotive_blueprint(context_provider))
    app.register_blueprint(create_deauth_control_blueprint(context_provider))
    app.register_blueprint(create_device_identification_blueprint(context_provider))
    app.register_blueprint(create_port_knowledge_blueprint(context_provider))
    app.register_blueprint(create_model_profiles_blueprint(context_provider))
    app.register_blueprint(create_service_records_blueprint(context_provider))
    app.register_blueprint(create_host_facts_blueprint(context_provider))
