import os
import subprocess
import uuid

# Using csv module *only* for reading the generated CSV for display/plotting
import csv

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
    abort,
    url_for,
)

import matplotlib

# set non-interactive backend, ideal for this use case
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# CONFIGURATION
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FOLDER = os.path.join(BASE_DIR, "data")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROCESSED_FOLDER = os.path.join(BASE_DIR, "processed")
PLOT_FOLDER = os.path.join(BASE_DIR, "plots")

PARSE_SCRIPT_PATH = os.path.join(BASE_DIR, "bash", "validate_parse.sh")
FILTER_SCRIPT_PATH = os.path.join(BASE_DIR, "bash", "filter_by_date.sh")

ALLOWED_EXTENSIONS = {"log"}

# Ensure directories exist
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(PLOT_FOLDER, exist_ok=True)

app = Flask(__name__)

app.config["DATA_FOLDER"] = DATA_FOLDER
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER
app.config["PLOT_FOLDER"] = PLOT_FOLDER

############## HELPER FUNCTIONS ################


def check_filename(filename: str):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_processed_files():
    """Returns a dictionary of processed files {log_id: original_filename}. Note, files of form '*.processed.csv' are to be ignored."""
    processed = {}
    try:
        for filename in os.listdir(app.config["PROCESSED_FOLDER"]):
            if filename.endswith(".csv") and not filename.endswith(".processed.csv"):
                log_id = filename.rsplit(".", 1)[0]
                # find the corressponding metadata file and read it to get original log file name
                original_name = f"Log {log_id}"  # placeholder name
                try:
                    with open(
                        os.path.join(app.config["PROCESSED_FOLDER"], f"{log_id}.info"),
                        "r",
                    ) as f:
                        original_name = f.read().strip()
                except FileNotFoundError:
                    pass  # keep placeholder

                processed[log_id] = original_name
    # if directory doesn't exist
    except FileNotFoundError:
        print(
            f"Warning: Processed folder not found at {app.config['PROCESSED_FOLDER']}"
        )
        return {}
    # any other errors
    except Exception as e:
        print(f"Error scanning processed folder: {e}")
        return {}
    return processed


def sort_data(data, opts):
    """Sorts parsed csv data based on options"""
    if not opts:
        return data

    # start sorting from minor
    for o in reversed(opts):
        # o is string where 1st char = +/-, 2nd char is int [0, 4]

        field = int(o[1])
        reverse = True if o[0] == "-" else False

        # sort by lineid
        if field == 0:
            key = lambda x: int(x[0])

        # sort by timestamp/level/content
        # NOTE: timestamp comparison can be done lexicographically
        elif field in [1, 2, 3]:
            key = lambda x: x[field]

        # sort by eventid
        # NOTE: assign empty/undefined eventid as last (in asc order)
        elif field == 4:
            key = lambda x: 7 if not x[4] else int(x[4][1])

        else:
            raise ValueError("opt[1] must be one of '01234'.")

        data = sorted(data, key=key, reverse=reverse)

    return data


# check if dates are in correct format: YYYY-mm-DD HH:MM:SS
def validate_datetime_str(datetime):
    try:
        date, time = datetime.split()

        yr, mo, dy = date.split("-")
        yr, mo, dy = int(yr), int(mo), int(dy)

        if not (1 <= mo <= 12):
            return False

        days_in_month = [
            31,
            28 + (1 if (yr % 4 == 0 and (yr % 100 != 0 or yr % 400 == 0)) else 0),
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ]

        if not (1 <= dy <= days_in_month[mo - 1]):
            return False

        hr, mi, se = list(map(int, time.split(":")))

        if not (0 <= hr < 24 and 0 <= mi < 60 and 0 <= se < 60):
            return False

        return True

    except Exception:
        return False


def filter_csv(csv_fpath: str, opts: str):
    """Given an input csv fpath and filterings options, produces a filtered file.
    Returns `(out_fpath, exception)`.

    In case of an exception, `out_fpath` defaults to `csv_fpath`."""

    start_dt, end_dt = opts

    # assuming file at `csv_fpath` exists

    # assuming `opts` are not empty

    # validate date strings
    if not (validate_datetime_str(start_dt) and validate_datetime_str(end_dt)):
        print(f"start: {start_dt} end: {end_dt}")
        raise Exception(
            "Error: Filtering options - start date, end date - not in correct format."
        )

    # filename for filtered csv
    # {basename_wo_extension}.processed.csv
    out_fpath = csv_fpath.rsplit(".", 1)[0] + ".processed.csv"

    try:
        # pass to script with proper args
        print(
            f"Running script: {FILTER_SCRIPT_PATH} {csv_fpath} {out_fpath} {start_dt} {end_dt}"
        )
        result = subprocess.run(
            [FILTER_SCRIPT_PATH, csv_fpath, out_fpath, start_dt, end_dt],
            capture_output=True,
            text=True,
            check=False,
        )
        # print debug output
        if result.returncode == 0:

            # basic check (num_lines > 1)
            if not os.path.exists(out_fpath):
                raise Exception(
                    "Error: Filtering script did not produce file at desired location."
                )
            else:
                if sum(1 for _ in open(out_fpath, "r")) <= 1:
                    raise Exception(
                        "Error: Filtering script produced empty filtered csv."
                    )

            print(f"SUCCESS stdout: {result.stdout}")
            print(f"SUCCESS stderr: {result.stderr}")

            # return fpath of output file if valid
            return out_fpath

        else:
            print(f"FAILURE stdout: {result.stdout}")
            print(f"FAILURE stderr (code {result.returncode}): {result.stderr}")

            # create error message from stderr if possible
            err = (
                result.stderr.strip().split("\n")[-1]
                if result.stderr
                else "Error: Filtering failed."
            )

            raise Exception(err)

    # error handling
    except Exception as e:
        # cleanup
        if os.path.exists(out_fpath):
            os.remove(out_fpath)

        raise e


def parse_opts(opts: str):
    """Return `None` if `opts` is empty or all ','-seperated fields are empty, else, return list of strings by splitting at ','."""
    if not opts:
        return None

    opts = opts.split(",")

    for o in opts:
        if o:
            return opts
    return None


def get_csv_data(csv_fpath, sort_opts, filter_opts, for_download=False):
    """Return CSV data (as `flask.Response` via `jsonify`),
    or, path (`str`) to filtered csv (if `for_download=True`) for given `log_id` with sort and filter opts.

    - Assumes the caller is passing valid `csv_fpath`,
      and `filter/sort_opts` are in a format suitable to
      pass as args to suitable functions.
    - Can raise exceptions!.

    *Notes:*
    - Filtering must be done within every `get_csv_data` call to ensure
      complete freedom for users to filter data
    - This also means filtering is "on-the-fly" only
    """

    if filter_opts:
        try:
            # returns new path
            out_fpath = filter_csv(csv_fpath, filter_opts)

            # both equivalent to an exception, but still check both
            if out_fpath == csv_fpath:
                raise Exception(f"Could not produce filtered CSV.")

        except Exception as e:
            raise Exception(f"Error filtering CSV {csv_fpath}: {e}")

        csv_fpath = out_fpath

    # in case download is required without sorting, send fpath as is
    if for_download and not sort_opts:
        return csv_fpath

    # otherwise, either data is required or fpath is (with sorted data)
    try:
        header = []
        data = []
        # read csv data
        with open(csv_fpath, "r") as csvfile:
            csv_reader = csv.reader(csvfile)
            header = next(csv_reader, None)
            if not header:
                raise Exception(f"Empty csv file/header")

            for row in csv_reader:
                if len(row) != len(header):  # basic check
                    raise Exception(f"Malformed row in CSV file: {row}")
                data.append(row)

        # sort data
        data = sort_data(data, sort_opts)

    except Exception as e:
        raise Exception(f"Error reading CSV {csv_fpath}: {e}")

    # if data is required
    if not for_download:
        return jsonify({"header": header, "data": data, "filtered": bool(filter_opts)})

    # otherwise, save sorted data into the file and pass that
    try:
        with open(csv_fpath, "w") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(header)
            csv_writer.writerows(data)
    except Exception as e:
        raise Exception(f"Error writing sorted data to CSV {csv_fpath}: {e}")

    return csv_fpath


def parse_csv_request(log_id, request):
    """Returns (`csv_fpath (str)`, `sort_opts (List)`, `filter_opts (List)`) 
    given an input `log_id` and `request` object.
    
    Can raise exception."""

    # check for csv
    csv_fname = f"{log_id}.csv"
    csv_fpath = os.path.join(app.config["PROCESSED_FOLDER"], csv_fname)

    if not os.path.exists(csv_fpath):
        raise Exception(f"CSV file {csv_fpath} for log id {log_id} not found.")

    # parse sort args of the form +/-N,+/-M,... from major to minor with 0<=N,M<=4
    # default to None if empty or undefined
    sort_opts = parse_opts(request.args.get("sort", None))

    # parse filter args of the form start_date_str,end_date_str
    # ! assumes date strs dont have commas
    # default to None if empty or undefined
    filter_opts = parse_opts(request.args.get("filter", None))

    return csv_fpath, sort_opts, filter_opts


################## ROUTES #####################


@app.route("/")
@app.route("/upload")
def upload_page():
    """Serves the main upload page."""
    # main upload page is where users can upload log files
    # via a drag and drop interface
    # existing uploaded files are also shown here
    existing_files = get_processed_files()
    return render_template("upload.html", existing_files=existing_files)


@app.route("/upload", methods=["POST"])
def handle_upload():
    """Handles file uploads via AJAX."""
    if "log_file" not in request.files:
        return jsonify({"success": False, "message": "No file part in request"}), 400

    file = request.files["log_file"]

    if file.filename == "":
        return jsonify({"success": False, "message": "No file selected"}), 400

    if file and check_filename(file.filename):
        original_filename = file.filename  # Keep original name for potential display
        log_id = str(uuid.uuid4())  # Generate unique ID
        log_filename = f"{log_id}.log"
        csv_filename = f"{log_id}.csv"
        info_filename = f"{log_id}.info"  # File to store original name

        log_filepath = os.path.join(app.config["UPLOAD_FOLDER"], log_filename)
        csv_filepath = os.path.join(app.config["PROCESSED_FOLDER"], csv_filename)
        info_filepath = os.path.join(app.config["PROCESSED_FOLDER"], info_filename)

        try:
            file.save(log_filepath)

            # store info
            with open(info_filepath, "w") as f:
                f.write(original_filename)

            # run bash script with proper args
            print(f"Running script: {PARSE_SCRIPT_PATH} {log_filepath} {csv_filepath}")
            result = subprocess.run(
                [PARSE_SCRIPT_PATH, log_filepath, csv_filepath],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                print(f"SUCCESS stdout:\n{result.stdout}")
                print(f"SUCCESS stderr:\n{result.stderr}")
                # return data in case of success
                return jsonify(
                    {
                        "success": True,
                        "message": "File validated and processed successfully.",
                        "log_id": log_id,
                        "filename": original_filename,
                    }
                )
            else:
                print(f"FAILURE stdout: {result.stdout}")
                print(f"FAILURE stderr (code {result.returncode}): {result.stderr}")

                # cleanup if validation failed
                if os.path.exists(csv_filepath):
                    os.remove(csv_filepath)
                if os.path.exists(info_filepath):
                    os.remove(info_filepath)

                # keep log file for debugging currently

                # if os.path.exists(log_filepath):
                #     os.remove(log_filepath)

                # create error message from stderr if possible
                error_message = (
                    result.stderr.strip().split("\n")[-1]
                    if result.stderr
                    else "Validation failed."
                )

                # return response in case of failure
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": error_message,
                            "log_id": log_id,
                            "filename": original_filename,
                        }
                    ),
                    400,
                )

        # if server error was caught
        except Exception as e:
            print(f"Error during file processing: {e}")
            # clean
            if os.path.exists(log_filepath):
                os.remove(log_filepath)
            if os.path.exists(csv_filepath):
                os.remove(csv_filepath)
            if os.path.exists(info_filepath):
                os.remove(info_filepath)

            return jsonify({"success": False, "message": f"Server error: {e}"}), 500
    # if file type was invalid
    else:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid file type. Only .log files allowed",
                }
            ),
            400,
        )


@app.route("/display")
def display_page():
    """Serves the page to display processed logs."""
    available_files = get_processed_files()
    return render_template("display.html", available_files=available_files)


@app.route("/get_csv/<log_id>")
def get_csv_endpoint(log_id):
    """Endpoint for serving CSV data for table on display page."""
    try:
        csv_fpath, sort_opts, filter_opts = parse_csv_request(log_id, request)
    except Exception as e:
        # error is FileNotFound
        return jsonify({"error": f"{e}"}), 404
    
    # get csv data as response
    try:
        response = get_csv_data(csv_fpath, sort_opts, filter_opts, for_download=False)
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
        with open(
            os.path.join(app.config["PROCESSED_FOLDER"], f"{log_id}.info"), "r"
        ) as f:
            original_name = f.read().strip().rsplit(".", 1)[0]  # use log name part
    except FileNotFoundError:
        pass

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


@app.route("/plots")
def plots_page():
    """Serves the page for generating plots."""
    available_files = get_processed_files()
    return render_template("plots.html", available_files=available_files)


@app.route("/generate_plots", methods=["POST"])
def generate_plots():
    """Generates selected plots for a given log file (via AJAX)."""
    data = request.get_json()
    log_id = data.get("log_id")
    plot_types = data.get("plot_types", [])
    # TODO: Get date range filters from 'data' later

    if not log_id or not plot_types:
        return jsonify({"success": False, "error": "Missing log_id or plot_types"}), 400

    csv_filename = f"{log_id}.csv"
    csv_filepath = os.path.join(app.config["PROCESSED_FOLDER"], csv_filename)

    if not os.path.exists(csv_filepath):
        return (
            jsonify({"success": False, "error": "CSV data not found for this log ID"}),
            404,
        )

    plot_results = []

    try:
        # --- Read CSV Data using Python (as allowed per requirements) ---
        # This is where filtering by date range (using Python) would happen
        # before passing data to plotting functions.
        # For now, read all data. Later, add date filtering logic here.

        # Example: Reading into a list of dicts might be convenient
        # Note: Use pandas here ONLY if customization is allowed (as per instructions)
        # For basic task, use standard csv module or basic parsing.
        log_data = []
        header = []
        with open(csv_filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                raise ValueError("CSV file is empty or has no header")
            # Assuming standard Apache log CSV columns: Timestamp, Level, EventID, Message etc.
            # Adjust indices based on your ACTUAL bash script output CSV format!
            # Let's assume: 0=Timestamp, 1=Level, 2=EventID
            for row in reader:
                if len(row) >= 3:  # Basic check
                    log_data.append(
                        {
                            "Timestamp": row[
                                0
                            ],  # Keep as string for now, parse later if needed
                            "Level": row[1],
                            "EventID": row[2],
                            # Add other fields if needed
                        }
                    )

        # --- Generate Requested Plots ---
        for plot_type in plot_types:
            fig = None
            plot_title = "Plot"
            try:
                if plot_type == "events_over_time":
                    # TODO: Implement logic for "Events logged with time (Line Plot)"
                    # - Parse timestamps
                    # - Aggregate events per second/minute/hour
                    # - Create line plot using matplotlib
                    fig, ax = plt.subplots()
                    ax.set_title("Events Over Time (Placeholder)")
                    ax.set_xlabel("Time")
                    ax.set_ylabel("Number of Events")
                    # Dummy data:
                    timestamps = np.arange(len(log_data))  # Replace with real time data
                    event_counts = np.random.randint(
                        1, 10, size=len(log_data)
                    )  # Replace with real counts
                    ax.plot(timestamps, event_counts)
                    plot_title = "Events Over Time"

                elif plot_type == "level_distribution":
                    # TODO: Implement logic for "Level State Distribution (Pie Chart)"
                    # - Count occurrences of each Level (e.g., 'notice', 'error')
                    # - Create pie chart
                    fig, ax = plt.subplots()
                    levels = [entry["Level"] for entry in log_data]
                    level_counts = {}
                    for level in levels:
                        level_counts[level] = level_counts.get(level, 0) + 1

                    if level_counts:
                        ax.pie(
                            level_counts.values(),
                            labels=level_counts.keys(),
                            autopct="%1.1f%%",
                        )
                        ax.set_title("Level State Distribution")
                    else:
                        ax.text(
                            0.5, 0.5, "No Level data found", ha="center", va="center"
                        )
                        ax.set_title("Level State Distribution")
                    plot_title = "Level State Distribution"

                elif plot_type == "event_code_distribution":
                    # TODO: Implement logic for "Event Code Distribution (Bar Plot)" (E1-E6)
                    # - Count occurrences of each EventID (E1-E6)
                    # - Create bar chart
                    fig, ax = plt.subplots()
                    event_ids = [
                        entry["EventID"] for entry in log_data if entry.get("EventID")
                    ]  # Filter out blank IDs if any
                    event_counts = {}
                    # Specific codes E1-E6 mentioned in requirement
                    target_events = {f"E{i}" for i in range(1, 7)}
                    for eid in event_ids:
                        if eid in target_events:
                            event_counts[eid] = event_counts.get(eid, 0) + 1

                    if event_counts:
                        # Ensure consistent order even if some codes are missing
                        sorted_events = sorted(
                            [e for e in event_counts.keys() if e in target_events],
                            key=lambda x: int(x[1:]),
                        )
                        counts = [event_counts[e] for e in sorted_events]
                        ax.bar(sorted_events, counts)
                        ax.set_title("Event Code Distribution (E1-E6)")
                        ax.set_xlabel("Event ID")
                        ax.set_ylabel("Number of Occurrences")
                    else:
                        ax.text(
                            0.5,
                            0.5,
                            "No EventID data (E1-E6) found",
                            ha="center",
                            va="center",
                        )
                        ax.set_title("Event Code Distribution (E1-E6)")
                    plot_title = "Event Code Distribution"

                else:
                    print(f"Warning: Unknown plot type requested: {plot_type}")
                    continue  # Skip unknown types

                # --- Save plot to a file ---
                if fig:
                    plot_filename = f"{log_id}_{plot_type}_{uuid.uuid4()}.png"
                    plot_filepath = os.path.join(
                        app.config["PLOT_FOLDER"], plot_filename
                    )
                    fig.tight_layout()  # Adjust layout
                    fig.savefig(plot_filepath, format="png")
                    plt.close(fig)  # Close the figure to free memory

                    plot_results.append(
                        {
                            "type": plot_type,
                            "title": plot_title,
                            "url": url_for("get_plot", plot_filename=plot_filename),
                            "download_url": url_for(
                                "download_plot", plot_filename=plot_filename
                            ),
                        }
                    )

            except Exception as plot_error:
                print(f"Error generating plot '{plot_type}' for {log_id}: {plot_error}")
                # Optionally add error info to response if needed, for now just skip the plot
                if fig:
                    plt.close(fig)  # Ensure figure is closed on error too

        return jsonify({"success": True, "plots": plot_results})

    except FileNotFoundError:
        return (
            jsonify({"success": False, "error": "CSV data not found for this log ID"}),
            404,
        )
    except ValueError as ve:  # Catch specific errors like empty CSV
        print(f"Value error processing {csv_filepath}: {ve}")
        return jsonify({"success": False, "error": f"Data error: {ve}"}), 400
    except Exception as e:
        print(f"Error during plot generation for {log_id}: {e}")
        # Ensure any open figures are closed if a general error occurs
        plt.close("all")
        return (
            jsonify(
                {"success": False, "error": f"Server error during plot generation: {e}"}
            ),
            500,
        )


@app.route("/plots/<plot_filename>")
def get_plot(plot_filename):
    """Serves a generated plot image."""
    try:
        return send_from_directory(app.config["PLOT_FOLDER"], plot_filename)
    except FileNotFoundError:
        abort(404, description="Plot image not found.")


@app.route("/download_plot/<plot_filename>")
def download_plot(plot_filename):
    """Provides a generated plot image for download."""
    try:
        return send_from_directory(
            app.config["PLOT_FOLDER"],
            plot_filename,
            as_attachment=True,
            # download_name can be set here if desired, e.g., based on log_id/type
        )
    except FileNotFoundError:
        abort(404, description="Plot image not found.")
