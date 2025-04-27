from flask import current_app
from app.utils.csv import get_csv_metadata
import os

def validate_filename(filename: str):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


def get_processed_files():
    """Returns a dictionary of processed files {log_id: original_filename}. Note, files of form '*.processed.csv' are to be ignored."""

    # go through all files from processed folder and validate from metadata file
    processed = {}
    try:
        for filename in os.listdir(current_app.config["PROCESSED_FOLDER"]):
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
