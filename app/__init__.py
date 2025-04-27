import os
from flask import Flask
from .config import Config


def create_app():
    # set base path as one folder above (project root) instead of app root
    BASE = os.path.abspath(os.path.dirname(__file__) + "/..")
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE, "templates"),
        static_folder=os.path.join(BASE, "static"),
    )
    app.config.from_object(Config(BASE))

    # ensure runtime folders exist
    for key in (
        "UPLOAD_FOLDER",
        "PROCESSED_FOLDER",
        "PLOT_FOLDER",
        "INSTANCE_FOLDER",
    ):
        os.makedirs(app.config[key], exist_ok=True)

    # ensure instance files exist
    for key in ("PLOT_STATUS_FILE", "FILE_METADATA_FILE"):
        open(app.config[key], "a").close()

    # import and register each route-module
    from .routes.upload import register_upload_routes
    from .routes.display import register_display_routes
    from .routes.plots import register_plots_routes

    register_upload_routes(app)
    register_display_routes(app)
    register_plots_routes(app)

    return app
