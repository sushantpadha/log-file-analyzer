from flask import render_template, request, jsonify, Flask, send_from_directory
from app.utils import (
    get_processed_files,
    get_csv_data,
    parse_csv_request,
    get_csv_metadata,
    parse_opts,
    generate_plots,
)

import os, json
from threading import Thread


def register_plots_routes(app: Flask):
    PLOT_STATUS_FILE = app.config["PLOT_STATUS_FILE"]
    PLOT_TYPES = app.config["PLOT_TYPES"]

    @app.route("/plots")
    def plots_page():
        """Serves the page for generating plots."""
        available_files = get_processed_files()
        return render_template("plots.html", available_files=available_files)

    @app.route("/generate_plots/", methods=["POST"])
    def handle_generate():
        """Endpoint for generating plots. Returns response containing name of file to query for status."""

        ### process request
        data = request.get_json()
        log_id = data.get("log_id")  # str
        plot_opts = data.get("plot_options")  # list -> set (later)
        filter_opts = data.get("filter_options")  # str
        custom_code = data.get("custom_code")  # str

        print(
            f"received request with\n\tlog_id: {log_id}\n\tplot_opts: {plot_opts}\n\tfilter_opts: {filter_opts}"
        )

        ### check `plot_opts` validity
        try:
            plot_opts = set(plot_opts)
            if not plot_opts.issubset(PLOT_TYPES):
                raise Exception("request contains invalid plot types")
        except Exception as e:
            # error is bad request
            return jsonify({"error": f"{e}"}), 400

        ### get csv data for plotting
        try:
            # only `csv_fpath` can be extracted here
            csv_fpath, _, _ = parse_csv_request(log_id, request)
            # `filter_opts` to be parsed here
            filter_opts = parse_opts(filter_opts)
        except Exception as e:
            # error is FileNotFound
            return jsonify({"error": f"{e}"}), 404

        try:
            data = get_csv_data(csv_fpath, None, filter_opts, for_download=False)
            # data_df = pd.DataFrame(data=data["data"], columns=data["header"])

        except Exception as e:
            # error is server error
            return jsonify({"error": f"{e}"}), 500

        # basic check on custom code
        if "custom" in plot_opts and not custom_code:
            return jsonify({"error": "Custom code not provided."}), 400

        if custom_code and len(custom_code) > 10_000:
            return (
                jsonify(
                    {"error": "Custom code too long (must be less than 10,000 chars)."}
                ),
                400,
            )

        ### generate plot file names here itself as `{plot_type}: {log_id}_{plot_type}.png`
        plot_files = {p: f"{log_id}_{p}.png" for p in plot_opts}

        ### spawn thread for generating plot
        # ref: https://docs.python.org/3/library/threading.html#threading.Thread
        Thread(
            target=generate_plots,
            args=(app, data["data"], plot_opts, plot_files, custom_code),
        ).start()

        ### return response containing file containing the status
        return jsonify({"status_file": PLOT_STATUS_FILE})

    @app.route("/status")
    def get_status():
        try:
            if os.path.getsize(PLOT_STATUS_FILE) > 0:
                with open(PLOT_STATUS_FILE, "r") as f:
                    return jsonify(json.load(f))
            else:
                return jsonify({"status": "idle"})
        except Exception as e:
            return (
                jsonify({"status": "error", "message": "Status file unreadable."}),
                500,
            )

    @app.route("/get_plot/<plot>")
    def get_plot(plot):
        """Endpoint for serving plot files"""
        try:
            return send_from_directory(
                app.config["PLOT_FOLDER"],
                plot,
            )
        except Exception as e:
            return jsonify({"error": f"Plot file {plot} not found."}), 500

    @app.route("/download_plot/<plot>")
    def download_plot(plot):
        """Endpoint for serving plot files for download"""

        log_id, plot_type_w_ext = plot.split("_", maxsplit=1)[:]

        # retrieve original filename for download suggestion
        original_name = "download"  # default
        try:
            md = get_csv_metadata(log_id)
            original_name = (
                md["original_name"] if md["original_name"] else original_name
            )
        except Exception:
            pass

        original_name = original_name.rsplit(".", 1)[0]  # remove ext

        download_filename = f"{original_name}_{plot_type_w_ext}"

        try:
            return send_from_directory(
                app.config["PLOT_FOLDER"],
                plot,
                as_attachment=True,
                download_name=download_filename,
            )
        except Exception as e:
            return jsonify({"error": f"Plot file {plot} not found."}), 500
