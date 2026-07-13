from .capabilities import create_capabilities_blueprint
from .minecraft import create_minecraft_blueprint


def register_blueprints(app, context_provider):
    app.register_blueprint(create_capabilities_blueprint(context_provider))
    app.register_blueprint(create_minecraft_blueprint(context_provider))
