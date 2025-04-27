from flask import render_template, request, jsonify, Flask, send_from_directory
from app.utils import get_processed_files, get_csv_data, parse_csv_request, get_csv_metadata

import os

def register_display_routes(app: Flask):
    @app.route("/display")
    def display_page():
        """Serves the page to display processed logs."""
        available_files = get_processed_files()
        return render_template("display.html", available_files=available_files)


    @app.route("/get_csv/<log_id>")
    def get_csv(log_id):
        """Endpoint for serving CSV data for table on display page."""
        try:
            csv_fpath, sort_opts, filter_opts = parse_csv_request(log_id, request)
        except Exception as e:
            # error is FileNotFound
            return jsonify({"error": f"{e}"}), 404

        # get csv data as response
        try:
            response = jsonify(
                get_csv_data(csv_fpath, sort_opts, filter_opts, for_download=False)
            )
        except Exception as e:
            # error is server error
            return jsonify({"error": f"{e}"}), 500

        return response


    @app.route("/get_metadata/<log_id>")
    def serve_metadata(log_id):
        """Endpoint for serving metadata for given log id."""
        log_fpath = os.path.join(app.config["UPLOAD_FOLDER"], f"{log_id}.log")
        csv_fpath = os.path.join(app.config["PROCESSED_FOLDER"], f"{log_id}.csv")

        if not os.path.exists(log_fpath):
            return jsonify({"error": f"log file with id {log_id} does not exist."}), 404

        if not os.path.exists(csv_fpath):
            return jsonify({"error": f"CSV file with id {log_id} does not exist."}), 404

        # get metadata as response
        try:
            response = jsonify(get_csv_metadata(log_id))
        except Exception as e:
            # error is server error
            return jsonify({"error": f"{e}"}), 500

        return response


    @app.route("/download_csv/<log_id>")
    def download_csv(log_id):
        """Endpoint for serving CSV data for download"""

        # retrieve original filename for download suggestion
        original_name = "download"  # default
        try:
            md = get_csv_metadata(log_id)
            original_name = md["original_name"] if md["original_name"] else original_name
        except Exception as e:
            print(e)
            pass

        original_name = original_name.rsplit(".", 1)[0]  # remove ext

        download_filename = f"{original_name}.csv"

        # parse csv request
        try:
            csv_fpath, sort_opts, filter_opts = parse_csv_request(log_id, request)
        except Exception as e:
            # error is FileNotFound
            return jsonify({"error": f"{e}"}), 404

        # get csv fpath
        try:
            fpath = get_csv_data(csv_fpath, sort_opts, filter_opts, for_download=True)
        except Exception as e:
            # error is server error
            return jsonify({"error": f"{e}"}), 500

        fname = os.path.split(fpath)[1]

        try:
            # https://flask.palletsprojects.com/en/stable/api/#flask.send_from_directory
            # using `send_from_directory` for safety
            return send_from_directory(
                app.config["PROCESSED_FOLDER"],
                fname,
                as_attachment=True,
                download_name=download_filename,
            )
        except Exception as e:
            return jsonify({"error": f"Processed CSV file not found."}), 500

