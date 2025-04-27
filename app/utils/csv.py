from flask import current_app
from app.utils.timestamps import validate_datetime_str
from app.utils.parse import sort_data

import subprocess, json, os

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
            f"Running script: {current_app.config['FILTER_SCRIPT_PATH']} {csv_fpath} {out_fpath} {start_dt} {end_dt}"
        )
        result = subprocess.run(
            [current_app.config["FILTER_SCRIPT_PATH"], csv_fpath, out_fpath, start_dt, end_dt],
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
        if not os.path.getsize(current_app.config["FILE_METADATA_FILE"]) > 0:
            raise Exception("file empty.")

        # read
        with open(current_app.config["FILE_METADATA_FILE"], "r") as f:
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
            f"Could not read file metadata from {current_app.config['FILE_METADATA_FILE']}: {e}"
        )
