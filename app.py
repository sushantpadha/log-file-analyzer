import os
import subprocess
import uuid

# Using csv and pandas module because customizations are enabled
import csv
import pandas as pd

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
    abort,
    url_for,
)
import flask

import matplotlib

# set non-interactive backend, ideal for this use case
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.dates import AutoDateLocator
from matplotlib.ticker import MaxNLocator

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


@app.route("/generate_plots/<log_id>")
def generate_plots(log_id):
    """Endpoint for generating plots. Returns response containing plot filename(s)"""

    ### get csv data for plotting
    try:
        csv_fpath, sort_opts, filter_opts = parse_csv_request(log_id, request)
    except Exception as e:
        # error is FileNotFound
        return jsonify({"error": f"{e}"}), 404

    try:
        response: flask.Response = get_csv_data(
            csv_fpath, sort_opts, filter_opts, for_download=False
        )
    except Exception as e:
        # error is server error
        return jsonify({"error": f"{e}"}), 500

    ### pandas for processing
    data = response.get_json()
    data_df = pd.DataFrame(data=data["data"], columns=data["header"])

    ### make desired plot
    plot_opts = parse_opts(request.args.get("plot", None))

    # `plot_opts` can contain one or more of:
    # - time
    # - level
    # - event

    # set plot style
    plt.style.use("petroff10")

    # define fontdicts for title and labels
    title_font = {
        "family": "serif",
        "color": "black",
        "weight": "normal",
        "size": 18,
    }
    label_font = {
        "family": "serif",
        "color": "black",
        "weight": "normal",
        "size": 14,
    }

    if "time" in plot_opts:
        fig, ax = plt.subplots(figsize=(10, 6))

        fig.tight_layout()

        # `pd.to_datetime`: https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html
        # strptime format: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior
        timestamps = data_df.sort_values(
            axis=0,
            by="Time",
            key=lambda x: pd.to_datetime(x, format="%a %b %d %H:%M:%S %Y"),
        ).value_counts("Time", sort=False)

        ax.plot(
            timestamps.index,
            timestamps.values,
            marker=".",
            linestyle="-",
            markersize=5,
            linewidth=1.5,
        )

        ### set labels and title
        ax.set_xlabel("Time", fontdict=label_font)
        ax.set_ylabel("Number of events per second", fontdict=label_font)
        ax.set_title("Events logged with time", fontdict=title_font)

        # set auto locator for x-axis with 5 to 10 ticks
        locator = AutoDateLocator(minticks=5, maxticks=10)
        ax.xaxis.set_major_locator(locator)

        # set y-axis to have only integer ticks
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))

        # properly align x-tick labels (rotation + alignment)
        ax.tick_params(axis="x", rotation=30, labelsize=10, length=5, color="gray")
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")
            label.set_verticalalignment("top")

        # adjust y-tick label size
        ax.tick_params(axis="y", labelsize=10, length=5, color="gray")

        # increase spacing between axes labels and ticks
        ax.yaxis.labelpad = 30
        ax.xaxis.labelpad = 30

        ax.grid(True, linestyle="--", alpha=0.8)

        fig.savefig("a.png", format="png", bbox_inches="tight")
        plt.close(fig)

    if "level" in plot_opts:
        # square figure
        fig, ax = plt.subplots(figsize=(8, 8))

        event_counts = data_df.sort_values(axis=0, by="Level").value_counts(
            "Level", sort=False
        )

        # create the pie chart
        wedges, texts, autotexts = ax.pie(
            event_counts.values,
            labels=event_counts.index,
            autopct="%1.1f%%",
            startangle=0,
            textprops=label_font,
            pctdistance=0.85,
        )
        # style percentage text
        plt.setp(autotexts, size=12, weight="bold", color="#eee")

        ax.set_title("Level State Distribution", fontdict=title_font, pad=30)

        # ax.axis("equal")

        fig.savefig("b.png", format="png", bbox_inches="tight")
        plt.close(fig)

    if "event" in plot_opts:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        event_counts = data_df.sort_values(axis=0, by="EventId").value_counts(
            "EventId", sort=False
        ).drop(labels="")

        # create the bar chart
        bars = ax.bar(event_counts.index, event_counts.values)

        ax.set_xlabel("Event ID", fontdict=label_font)
        ax.set_ylabel("Number of Occurrences", fontdict=label_font)
        ax.set_title("Event Code Distribution (E1-E6)", fontdict=title_font)

        # set axes ticks
        ax.tick_params(axis="x", rotation=0, labelsize=10, length=5, color='gray')

        # set integer spacing for ticks
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.tick_params(axis="y", labelsize=10, length=5, color='gray')

        # adjust label padding
        ax.yaxis.labelpad = 25
        ax.xaxis.labelpad = 25

        # add grid lines for yaxis only
        ax.yaxis.grid(True, linestyle="--", alpha=0.8)
        ax.xaxis.grid(False)

        fig.savefig("c.png", format="png", bbox_inches="tight")
        plt.close(fig)

    return response


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
