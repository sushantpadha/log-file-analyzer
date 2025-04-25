import os
import subprocess

# ! only for creating unique file id's based on timestamps
import random
from time import time
import json

# import threading for spawning plot generation in bg thread
from threading import Thread

import numpy as np

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
import matplotlib as mpl
from matplotlib.dates import AutoDateLocator
from matplotlib.ticker import MaxNLocator, FuncFormatter

import pandas as pd

# CONFIGURATION
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FOLDER = os.path.join(BASE_DIR, "data")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROCESSED_FOLDER = os.path.join(BASE_DIR, "processed")
PLOT_FOLDER = os.path.join(BASE_DIR, "plots")
INSTANCE_FOLDER = os.path.join(BASE_DIR, "instance")

PARSE_SCRIPT_PATH = os.path.join(BASE_DIR, "bash", "validate_parse.sh")
FILTER_SCRIPT_PATH = os.path.join(BASE_DIR, "bash", "filter_by_date.sh")

ALLOWED_EXTENSIONS = {"log"}

PLOT_STATUS_FILENAME = "status.json"
FILE_METADATA_FILENAME = "metadata.json"

PLOT_STATUS_FILEPATH = os.path.join(INSTANCE_FOLDER, PLOT_STATUS_FILENAME)
FILE_METADATA_FILEPATH = os.path.join(INSTANCE_FOLDER, FILE_METADATA_FILENAME)

# ensure directories exist
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(PLOT_FOLDER, exist_ok=True)
os.makedirs(INSTANCE_FOLDER, exist_ok=True)

# ensure instance files exist
for f in [PLOT_STATUS_FILEPATH, FILE_METADATA_FILEPATH]:
    open(f, "a").close()

app = Flask(__name__)

# configure folder paths in app config
app.config["DATA_FOLDER"] = DATA_FOLDER
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER
app.config["PLOT_FOLDER"] = PLOT_FOLDER
app.config["INSTANCE_FOLDER"] = INSTANCE_FOLDER


################### DEFAULTS ###################

PLOT_TYPES = {
    "events_over_time",
    "level_distribution",
    "event_code_distribution",
    "custom",
}

EVENT_CODES = {
    "E1",
    "E2",
    "E3",
    "E4",
    "E5",
    "E6",
}

############## HELPER FUNCTIONS ################


def seconds_from_timestamp(timestamp):
    """Return number of seconds elapsed between `timestamp` wrt 0001-01-01 00:00:00"""
    timestamp = format_timestamp(timestamp)

    def to_seconds(tstmp):
        if not tstmp:
            return 0

        d, t = tstmp.split()
        yr, mo, day = map(int, d.split("-"))
        hr, mn, sc = map(int, t.split(":"))

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

        # 1) days from all years before this one (leaps = (N-1)//4 - (N-1)//100 + (N-1)//400)
        years_prior = yr - 1
        leaps_prior = years_prior // 4 - years_prior // 100 + years_prior // 400
        days_prior_years = years_prior * 365 + leaps_prior

        # 2) days from all months earlier in this year
        days_prior_months = sum(days_in_month[: mo - 1])

        # 3) days before the current day
        days_prior_days = day - 1

        total_days = days_prior_years + days_prior_months + days_prior_days

        # 4) convert to seconds
        total_seconds = total_days * 86400 + hr * 3600 + mn * 60 + sc

        return total_seconds

    return to_seconds(timestamp)


def timestamp_from_seconds(total_seconds, pos=None):
    """Convert seconds since 0001-01-01 00:00:00 to YYYY-mm-DD HH:MM:SS (`pos` arg is for usage with `matplotlib.ticker.FuncFormatter`)"""
    total_seconds = int(total_seconds)
    days = total_seconds // 86400
    rem = total_seconds % 86400
    hr = rem // 3600
    rem %= 3600
    mn = rem // 60
    sc = rem % 60

    # 2) convert total days into year / month / day
    # start from year 1 and add year lengths until remaining days is within the year
    year = 1
    while True:
        is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        days_in_year = 366 if is_leap else 365
        if days < days_in_year:
            break
        days -= days_in_year
        year += 1

    days_in_month = [
        31,
        28 + (1 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 0),
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
    month = 1
    for dim in days_in_month:
        if days < dim:
            break
        days -= dim
        month += 1

    day = days + 1

    return f"{year:04d}-{month:02d}-{day:02d} {hr:02d}:{mn:02d}:{sc:02d}"


def format_timestamp(csvTimestamp):
    _, mo, dt, t, yr = csvTimestamp.split(" ")

    month_map = {
        "Jan": "01",
        "Feb": "02",
        "Mar": "03",
        "Apr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Aug": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dec": "12",
    }
    month = month_map[mo]

    return f"{yr}-{month}-{dt} {t}"


def validate_filename(filename: str):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_processed_files():
    """Returns a dictionary of processed files {log_id: original_filename}. Note, files of form '*.processed.csv' are to be ignored."""

    # go through all files from processed folder and validate from metadata file
    processed = {}
    try:
        for filename in os.listdir(app.config["PROCESSED_FOLDER"]):
            if filename.endswith(".csv") and not filename.endswith(".processed.csv"):
                log_id = filename.rsplit(".", 1)[0]

                # read the metadata for original name
                original_name = f"Log {log_id}"  # placeholder name
                try:
                    md = get_csv_metadata(log_id)
                    original_name = (
                        md["original_name"] if md["original_name"] else original_name
                    )
                except Exception as e:
                    print(e)

                processed[log_id] = original_name

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
        elif field in [2, 3]:
            key = lambda x: x[field]

        elif field == 1:
            key = lambda x: format_timestamp(x[1])

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
        date, t = datetime.split()

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

        hr, mi, se = list(map(int, t.split(":")))

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


def parse_csv(filepath):
    """Parse CSV file (handles quoted fields and escaped double quotes)

    Assumes file exists. Assumes LF endings(?)

    Returns header (`List[str]`) and data (`List[List[str]]`).
    """

    data = []

    with open(filepath, "r") as f:
        row = []
        field = ""
        in_quotes = False
        # read char
        while True:
            char = f.read(1)
            # EOF
            if not char:
                # append current field and row if non-empty
                if field or row:
                    row.append(field)
                    data.append(row)
                break

            # quoting begins
            if char == '"':
                # this can be:
                # - start of escaped quote
                # - start of new quoted field
                # - end of a quoted field

                if in_quotes:
                    next_char = f.read(1)
                    # escaped quote
                    if next_char == '"':
                        field += '"'
                    else:
                        # end of quoted field
                        in_quotes = False
                        if next_char:
                            # end of non-final quoted field
                            if next_char == ",":
                                row.append(field)
                                field = ""
                            # end of final quoted field
                            elif next_char == "\n":
                                row.append(field)
                                data.append(row)
                                row = []
                                field = ""
                            # start of quoted field
                            else:
                                field += next_char
                # start of quoted field
                else:
                    in_quotes = True

            # read comma not in quotes
            elif char == "," and not in_quotes:
                row.append(field)
                field = ""

            # read EOL not in quotes
            elif char == "\n" and not in_quotes:
                row.append(field)
                data.append(row)
                row = []
                field = ""

            # any other case read literally
            else:
                field += char

    if not data:
        header, _data = [], []
    else:
        header = data[0]
        _data = data[1:] if len(data) > 1 else []

    return header, _data


def write_csv(fpath, header, data):
    """(Over)Writes to CSV at `fpath` with `header` and `data`. Does not do any validation!"""

    def _escape(field):
        field = str(field)
        if '"' in field:
            field = field.replace('"', '""')
        if "," in field or '"' in field or "\n" in field:
            field = f'"{field}"'
        return field

    with open(fpath, "w") as f:
        f.write(",".join(_escape(col) for col in header) + "\n")

        for row in data:
            f.write(",".join(_escape(cell) for cell in row) + "\n")


def validate_csv_data(header, data):
    """Given header and data, validates CSV data, and raises exceptions if any errors found."""

    if not header:
        raise Exception(f"Empty csv file/header")

    for row in data:
        if len(row) != len(header):  # basic check
            raise Exception(f"Malformed row in CSV file: {row}")

    return True


def get_csv_data(csv_fpath, sort_opts, filter_opts, for_download=False):
    """Return CSV data (as dict),
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
        # parse csv
        header, data = parse_csv(csv_fpath)

        # validate
        validate_csv_data(header, data)

        # sort data
        data = sort_data(data, sort_opts)

    except Exception as e:
        raise Exception(f"Error reading CSV {csv_fpath}: {e}")

    # if data is required
    if not for_download:
        return {"header": header, "data": data, "filtered": bool(filter_opts)}

    # otherwise, save sorted data into the file and pass that
    try:
        write_csv(csv_fpath, header, data)
    except Exception as e:
        raise Exception(f"Error writing sorted data to CSV {csv_fpath}: {e}")

    return csv_fpath


def get_csv_timestamps(csv_fpath):
    try:
        # get sorted data using `get_csv_data`
        # NOTE: +1 sorts by timestamps ascending!
        data = get_csv_data(
            csv_fpath=csv_fpath, sort_opts=("+1",), filter_opts=None, for_download=False
        )["data"]

        start = data[0][1]
        end = data[-1][1]

        return start, end
    except Exception as e:
        raise Exception(f"Error in reading timestamps of {csv_fpath}: {e}")


def get_csv_metadata(log_id):
    """Return metadata for `log_id` as dict of the form:
    ```
    {
        "original_name": "<original_log_name>",
        "start_timestamp": "<earliest_timestamp>",
        "end_timestamp": "<latest_timestamp>",
    }
    ```

    May raise exception."""

    # read metadata file

    try:
        # check if non-empty
        if not os.path.getsize(FILE_METADATA_FILEPATH) > 0:
            raise Exception("file empty.")

        # read
        with open(FILE_METADATA_FILEPATH, "r") as f:
            md = json.load(f)

        # check if metadata exists
        if log_id not in md:
            raise Exception(f"metadata not found for log_id {log_id}")

        # return metadata as a JSON response
        return {
            "original_name": md[log_id]["original_name"],
            "start_timestamp": md[log_id]["start_timestamp"],
            "end_timestamp": md[log_id]["end_timestamp"],
        }

    except Exception as e:
        raise Exception(
            f"Could not read file metadata from {FILE_METADATA_FILEPATH}: {e}"
        )


def parse_csv_request(log_id, request):
    """Returns (`csv_fpath (str)`, `sort_opts (List)`, `filter_opts (List)`)
    given an input `log_id` and `request` object.

    Raises exception."""

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


def set_plot_generation_status(status_str, plot_files=None, error_str=None):
    """Set the plot generation status in `PLOT_STATUS_FILEPATH` with `status_str` and `plot_files` if not `None`.

    Optionally, if error occurs, `error_str` may be passed.

    `status_str` can be one of `['processing','done','error']`

    Caution: This function may raise an exception but isn't handled!"""

    old_status = {}

    # check if file non-empty
    if os.path.getsize(PLOT_STATUS_FILEPATH) > 0:
        try:
            with open(PLOT_STATUS_FILEPATH, "r") as f:
                old_status = json.load(f)
        except Exception as e:
            raise Exception(
                f"Could not read plot generation status from {PLOT_STATUS_FILEPATH}: {e}"
            )

    new_status = {
        "status": status_str,
        "plot_files": (
            old_status.get("plot_files", {}) if plot_files is None else plot_files
        ),
        "error": error_str if error_str else "",
    }

    try:
        with open(PLOT_STATUS_FILEPATH, "w") as f:
            json.dump(new_status, f)
    except Exception as e:
        raise Exception(
            f"Could not write plot generation status to {PLOT_STATUS_FILEPATH}: {e}"
        )


def generate_plots(data, plot_opts, plot_files, custom_code=None):
    """Generate plots based on `data_df` (`List[List[str]]`), `plot_opts` (`List[str]`), `plot_files` (`Dict[str, str]`) and `custom_code` (`str`)"""
    ### set status to processing
    set_plot_generation_status(status_str="processing", plot_files=plot_files)

    def get_counts(data, key, sort_key=lambda x: x[0]):
        """Returns counts of items summed over all rows of `data`, where items are extracted using func `key`.
        Returns tuple of two lists: first list containing values, second containing counts, both sorted acc. to `sort_key` (applied to dict.items())
        """
        counts = {}
        for row in data:
            value = key(row)
            if value not in counts:
                counts[value] = 1
            else:
                counts[value] += 1
        values, counts = zip(*sorted(counts.items(), key=sort_key))
        return values, counts

    # `plot_opts` can contain one or more of:
    # [events_over_time, level_distribution, event_code_distribution]

    ### set plot style
    plt.style.use("petroff10")

    ### define fontdicts for title and labels
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

    # NOTE: Using
    # LineId, Time, Level, Content, EventId
    my_timestamp_formatter = FuncFormatter(timestamp_from_seconds)

    ### generate plots based on type

    try:
        if "events_over_time" in plot_opts:
            fig, ax = plt.subplots(figsize=(11, 4))

            fig.tight_layout()

            # convert timestamps to seconds
            seconds_series = np.array([seconds_from_timestamp(row[1]) for row in data])

            # make all seconds values 0-referenced
            # ! so that they can be used as index
            ref_point = seconds_series.min().item()
            seconds_series -= ref_point
            size = seconds_series.max().item() + 1

            # generate full range of secondses from start to end with step = 1s
            secondses_range = np.arange(0, size, 1) + ref_point

            # count occurrences of each seconds
            unique_secondses, seconds_counts = np.unique(
                seconds_series, return_counts=True
            )

            # create full counts array
            counts = np.zeros_like(secondses_range)
            counts[unique_secondses] = seconds_counts

            # plot the line graph
            ax.plot(
                secondses_range,
                counts,
                linewidth=1.5,
            )

            ### set labels and title
            ax.set_xlabel("Time", fontdict=label_font)
            ax.set_ylabel("Number of events per second", fontdict=label_font)
            ax.set_title("Events logged with time (Line Graph)", fontdict=title_font)

            # set auto locator for x-axis
            ax.xaxis.set_major_locator(
                MaxNLocator(min_n_ticks=5, nbins="auto", integer=True)
            )

            # format timestamps to original format
            ax.xaxis.set_major_formatter(my_timestamp_formatter)

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

            # Save the plot
            fig.savefig(
                os.path.join(app.config["PLOT_FOLDER"], plot_files["events_over_time"]),
                format="png",
                bbox_inches="tight",
            )
            plt.close(fig)

        if "level_distribution" in plot_opts:
            # square figure
            fig, ax = plt.subplots(figsize=(8, 8))

            # get level counts
            levels, level_counts = get_counts(data, lambda row: row[2])

            # create the pie chart
            wedges, texts, autotexts = ax.pie(
                level_counts,
                labels=levels,
                autopct=lambda p: f"{p:.2f}%",
                startangle=0,
                textprops=label_font,
                pctdistance=0.85,
            )
            # style percentage text
            plt.setp(autotexts, size=12, weight="bold", color="#eee")

            ax.set_title("Level State Distribution", fontdict=title_font, pad=30)

            # ax.axis("equal")

            fig.savefig(
                os.path.join(
                    app.config["PLOT_FOLDER"], plot_files["level_distribution"]
                ),
                format="png",
                bbox_inches="tight",
            )
            plt.close(fig)

        if "event_code_distribution" in plot_opts:
            fig, ax = plt.subplots(figsize=(10, 6))

            # get event code wise counts
            event_codes, event_code_counts = get_counts(data, lambda row: row[4])

            # only keep valid labels
            for i, key in enumerate(event_codes):
                if key not in EVENT_CODES:
                    del event_codes[i]
                    del event_code_counts[i]

            # create the bar chart
            bars = ax.bar(event_codes, event_code_counts)

            ax.set_xlabel("Event ID", fontdict=label_font)
            ax.set_ylabel("Number of Occurrences", fontdict=label_font)
            ax.set_title("Event Code Distribution (E1-E6)", fontdict=title_font)

            # set axes ticks
            ax.tick_params(axis="x", rotation=0, labelsize=10, length=5, color="gray")

            # set integer spacing for ticks
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ax.tick_params(axis="y", labelsize=10, length=5, color="gray")

            # adjust label padding
            ax.yaxis.labelpad = 25
            ax.xaxis.labelpad = 25

            # add grid lines for yaxis only
            ax.yaxis.grid(True, linestyle="--", alpha=0.8)
            ax.xaxis.grid(False)

            fig.savefig(
                os.path.join(
                    app.config["PLOT_FOLDER"], plot_files["event_code_distribution"]
                ),
                format="png",
                bbox_inches="tight",
            )
            plt.close(fig)

    except Exception as e:
        print(e)
        set_plot_generation_status(status_str="error", plot_files={}, error_str=f"{e}")
        # ensure all figure are closed
        plt.close('all')
        return

    # ! doing basic error handling for this part separately
    try:
        if "custom" in plot_opts:
            # create df from data
            data_df = pd.DataFrame(
                data=data, columns=["LineId", "Time", "Level", "Content", "EventId"]
            )

            # change type to datetime for Time column
            data_df["Time"] = pd.to_datetime(
                data_df["Time"], format="%a %b %d %H:%M:%S %Y"
            )

            # define a very limited set of variables to export for user-submitted code
            user_locals = {
                "data_df": data_df,
                "plt": plt,
                "mpl": matplotlib,
                "np": np,
                "pd": pd,
            }

            # block all builtins
            safe_globals = {
                "__builtins__": {},
            }

            # execute the code
            # ! ensure more checks, time out check...
            exec(custom_code, safe_globals, user_locals)

            fig = plt.gcf()
            fig.savefig(
                os.path.join(app.config["PLOT_FOLDER"], plot_files["custom"]),
                format="png",
                bbox_inches="tight",
            )
            plt.close(fig)

    except Exception as e:
        print(e)
        # NOTE: if custom code fails, status is still "done" in case other plots were generated (but remove "custom" plot)
        del plot_files["custom"]
        set_plot_generation_status(status_str="done", plot_files=plot_files, error_str=f"[error in user submitted code]: {e}")
        # ensure all figure are closed
        plt.close('all')
        return
        
    ### set status to done
    set_plot_generation_status(status_str="done", plot_files=plot_files)



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
    """Handles file uploads."""
    # error handling
    if "log_file" not in request.files:
        return jsonify({"success": False, "message": "No file part in request"}), 400

    file = request.files["log_file"]

    if file.filename == "":
        return jsonify({"success": False, "message": "No file selected"}), 400

    if file and validate_filename(file.filename):
        original_filename = file.filename

        # generate unique ID

        # log_id = str(uuid.uuid4())
        log_id = str(time() * 10**6)[:15] + f"{(random.random()):0.5f}"[2:]

        log_filename = f"{log_id}.log"
        csv_filename = f"{log_id}.csv"

        log_filepath = os.path.join(app.config["UPLOAD_FOLDER"], log_filename)
        csv_filepath = os.path.join(app.config["PROCESSED_FOLDER"], csv_filename)

        try:
            file.save(log_filepath)

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

                # if validation and processing completed, add metadata entry

                # check if file non-empty
                if os.path.getsize(FILE_METADATA_FILEPATH) > 0:
                    try:
                        with open(FILE_METADATA_FILEPATH, "r") as f:
                            old_md = json.load(f)
                    except Exception as e:
                        raise Exception(
                            f"Could not read (metadata file) {FILE_METADATA_FILEPATH}: {e}"
                        )
                else:
                    old_md = {}

                # add entry for newly processed file
                start, end = get_csv_timestamps(csv_filepath)

                new_md_entry = {
                    log_id: {
                        "original_name": original_filename,
                        "start_timestamp": start,
                        "end_timestamp": end,
                    }
                }

                old_md.update(new_md_entry)

                try:
                    with open(FILE_METADATA_FILEPATH, "w") as f:
                        json.dump(old_md, f)
                except Exception as e:
                    raise Exception(
                        f"Could not write file metadata to {FILE_METADATA_FILEPATH}: {e}"
                    )

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

    # return jsonify({"error": f"ggez"})
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
        target=generate_plots, args=(data["data"], plot_opts, plot_files, custom_code)
    ).start()

    ### return response containing file containing the status
    return jsonify({"status_file": PLOT_STATUS_FILEPATH})


@app.route("/status")
def get_status():
    try:
        if os.path.getsize(PLOT_STATUS_FILEPATH) > 0:
            with open(PLOT_STATUS_FILEPATH, "r") as f:
                return jsonify(json.load(f))
        else:
            return jsonify({"status": "idle"})
    except Exception as e:
        return jsonify({"status": "error", "message": "Status file unreadable."}), 500


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
        original_name = md["original_name"] if md["original_name"] else original_name
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
