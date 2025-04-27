from flask import current_app
from app.utils.timestamps import timestamp_from_seconds, seconds_from_timestamp

import os, json
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, FuncFormatter

# set non-interactive backend, ideal for this use case
mpl.use("Agg")


def set_plot_generation_status(status_str, plot_files=None, error_str=None):
    """Set the plot generation status in `PLOT_STATUS_FILE` with `status_str` and `plot_files` if not `None`.

    Optionally, if error occurs, `error_str` may be passed.

    `status_str` can be one of `['processing','done','error']`

    Caution: This function may raise an exception but isn't handled!"""
    PLOT_STATUS_FILE = current_app.config["PLOT_STATUS_FILE"]

    old_status = {}

    # check if file non-empty
    if os.path.getsize(PLOT_STATUS_FILE) > 0:
        try:
            with open(PLOT_STATUS_FILE, "r") as f:
                old_status = json.load(f)
        except Exception as e:
            raise Exception(
                f"Could not read plot generation status from {PLOT_STATUS_FILE}: {e}"
            )

    new_status = {
        "status": status_str,
        "plot_files": (
            old_status.get("plot_files", {}) if plot_files is None else plot_files
        ),
        "error": error_str if error_str else "",
    }

    try:
        with open(PLOT_STATUS_FILE, "w") as f:
            json.dump(new_status, f)
    except Exception as e:
        raise Exception(
            f"Could not write plot generation status to {PLOT_STATUS_FILE}: {e}"
        )


def generate_plots(_app, data, plot_opts, plot_files, custom_code=None):
    """Generate plots based on `data: List[List[str]]`, `plot_opts: List[str]`, `plot_files: Dict[str, str]` and `custom_code: str`

    NOTE: since this code is only called inside a `Thread`, application context is not inherited properly, so pass the `Flask` object as `_app`
    """

    # Ref: https://flask.palletsprojects.com/en/stable/appcontext/

    with _app.app_context():
        PLOT_FOLDER = current_app.config["PLOT_FOLDER"]

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
                seconds_series = np.array(
                    [seconds_from_timestamp(row[1]) for row in data]
                )

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
                ax.set_title(
                    "Events logged with time (Line Graph)", fontdict=title_font
                )

                # set auto locator for x-axis
                ax.xaxis.set_major_locator(
                    MaxNLocator(min_n_ticks=5, nbins="auto", integer=True)
                )

                # format timestamps to original format
                ax.xaxis.set_major_formatter(my_timestamp_formatter)

                # set y-axis to have only integer ticks
                ax.yaxis.set_major_locator(MaxNLocator(integer=True))

                # properly align x-tick labels (rotation + alignment)
                ax.tick_params(
                    axis="x", rotation=30, labelsize=10, length=5, color="gray"
                )
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
                    os.path.join(PLOT_FOLDER, plot_files["events_over_time"]),
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
                    os.path.join(PLOT_FOLDER, plot_files["level_distribution"]),
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
                    if key not in current_app.config["EVENT_CODES"]:
                        del event_codes[i]
                        del event_code_counts[i]

                # create the bar chart
                bars = ax.bar(event_codes, event_code_counts)

                ax.set_xlabel("Event ID", fontdict=label_font)
                ax.set_ylabel("Number of Occurrences", fontdict=label_font)
                ax.set_title("Event Code Distribution (E1-E6)", fontdict=title_font)

                # set axes ticks
                ax.tick_params(
                    axis="x", rotation=0, labelsize=10, length=5, color="gray"
                )

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
                    os.path.join(PLOT_FOLDER, plot_files["event_code_distribution"]),
                    format="png",
                    bbox_inches="tight",
                )
                plt.close(fig)

        except Exception as e:
            print(e)
            set_plot_generation_status(
                status_str="error", plot_files={}, error_str=f"{e}"
            )
            # ensure all figure are closed
            plt.close("all")
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
                    "mpl": mpl,
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
                    os.path.join(PLOT_FOLDER, plot_files["custom"]),
                    format="png",
                    bbox_inches="tight",
                )
                plt.close(fig)

        except Exception as e:
            print(e)
            # NOTE: if custom code fails, status is still "done" in case other plots were generated (but remove "custom" plot)
            del plot_files["custom"]
            set_plot_generation_status(
                status_str="done",
                plot_files=plot_files,
                error_str=f"[error in user submitted code]: {e}",
            )
            # ensure all figure are closed
            plt.close("all")
            return

        ### set status to done
        set_plot_generation_status(status_str="done", plot_files=plot_files)
