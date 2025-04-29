from flask import current_app
from app.utils.timestamps import format_timestamp

import os

def parse_opts(opts: str):
    """Return `None` if `opts` is empty or all ','-seperated fields are empty, else, return list of strings by splitting at ','."""
    if not opts:
        return None

    opts = opts.split(",")

    for o in opts:
        if o:
            return opts
    return None


def sort_data(data, opts):
    """Sorts parsed csv data based on options"""
    if not opts:
        return data

    # start sorting from minor
    for o in reversed(opts):
        # o is string where 1st char = +/-, 2nd char is int [0, 5]

        field = int(o[1])
        reverse = True if o[0] == "-" else False

        # sort by lineid
        if field == 0:
            key = lambda x: int(x[0])

        # sort by timestamp/level/content/template
        elif field in [2, 3, 5]:
            key = lambda x: x[field]

        elif field == 1:
            key = lambda x: format_timestamp(x[1])

        # sort by eventid
        # NOTE: assign empty/undefined eventid as last (in asc order)
        elif field == 4:
            key = lambda x: 7 if not x[4] else int(x[4][1])

        else:
            raise ValueError("opt[1] must be one of '012345'.")

        data = sorted(data, key=key, reverse=reverse)

    return data


def parse_csv_request(log_id, request):
    """Returns (`csv_fpath (str)`, `sort_opts (List)`, `filter_opts (List)`)
    given an input `log_id` and `request` object.

    Raises exception."""

    # check for csv
    csv_fname = f"{log_id}.csv"
    csv_fpath = os.path.join(current_app.config["PROCESSED_FOLDER"], csv_fname)

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
