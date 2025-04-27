from flask import render_template, request, jsonify, Flask
from app.utils import validate_filename, get_csv_timestamps, get_processed_files

from time import time
import os, subprocess, random, json


def register_upload_routes(app: Flask):
    PARSE_SCRIPT_PATH = app.config["PARSE_SCRIPT_PATH"]
    FILE_METADATA_FILE = app.config["FILE_METADATA_FILE"]

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
                    if os.path.getsize(FILE_METADATA_FILE) > 0:
                        try:
                            with open(FILE_METADATA_FILE, "r") as f:
                                old_md = json.load(f)
                        except Exception as e:
                            raise Exception(
                                f"Could not read (metadata file) {FILE_METADATA_FILE}: {e}"
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
                        with open(FILE_METADATA_FILE, "w") as f:
                            json.dump(old_md, f)
                    except Exception as e:
                        raise Exception(
                            f"Could not write file metadata to {FILE_METADATA_FILE}: {e}"
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

