#!/bin/bash

# just in case
if [[ ! ($# -eq 4) ]]; then
    echo "Usage: <script.sh> <input_csv_file_path> <output_csv_file_path> <start_date> <end_date>" >&2
    exit 1
fi

# args are IN_CSV_FILE, OUT_CSV_FILE, START_DATE, END_DATE
# ! assumes date str format is valid

# if file is CRLF terminated, we dont care :) convert to LF
sed -i.bck 's/\r$//' "$1"

# basic check
if [[ ! -s "$1" ]]; then
	echo "input file '$1' does not exist / is empty!" >&2
	exit 1
fi

# ! Assumes script is always called from project root
# TODO: ensure no issues with quoting
awk -v OUTFILE="$2" -v START_DATE="$3" -v END_DATE="$4" -f "bash/filter_by_date.awk" "$1"

err=$?

if [[ ! $err -eq 0 ]]; then
    exit $err
fi

# basic check for output file existence
# rest will be handled by python
if [[ ! -s "$2" ]]; then
    echo "Error: Failed to create or populate filtered CSV file '$2'." >&2
    # not deleting in this case
	# rm -f "$2"
    exit 1
fi