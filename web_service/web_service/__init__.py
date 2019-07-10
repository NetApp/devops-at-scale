import os
from flask import Flask, jsonify
from flasgger import Swagger


# Factory function that "generates" our flask application

def create_app():

    # instantiate the app
    app = Flask(__name__)

    # set config
    app_settings = os.getenv('APP_SETTINGS') or 'config.ProductionConfig'
    app.config.from_object(app_settings)

    # register blueprints
    from web_service.backend.views import backend_blueprint
    from web_service.frontend.views import frontend_blueprint
    app.register_blueprint(backend_blueprint)
    app.register_blueprint(frontend_blueprint)

    # Setup swagger documentation for our app
    app.config['SWAGGER'] = {
        'title': 'DevOps@Scale API',
        'uiversion': 3
    }
    Swagger(app)

    # Return our app
    return app
