# Log File Analyzer

A final project for the CS104 course (Spr 2025).

> A Flask app, that allows users to upload multiple log files (currently only supports apache event logs) and validate them.
> 
> Validated log files are then parsed into CSV files which can be viewed on the web interface, with various sorting and filtering options (CSV data can be downloaded).
> 
> Plots may be generated with some basic pre-defined plot types or via a code editor for writing custom plot generating code in python.

## Usage

The project is a [Flask](https://flask.palletsprojects.com/en/stable/) app with entry-point script `run.py`. run as

```bash
python3 run.py
```

To clear previously loaded log files, processed CSVs and plots and server state run the cleanup script:

```bash
bash cleanup.sh
```

## Features
Following features have been implemented:
- Drop-down menu for choosing logs
- Drag and drop functionality for uploading logs
- Validation of log files against Apache event log format
- Modularized validation and parsing code
- Web interface for viewing CSV data as a scrollable table
- Sorting implemented across all fields
- Filtering implemented according to timestamps
- Processed CSV files can be downloaded easily
- Generating plots from the data with filtering
- Threaded plot generation call so as to not block main server thread
- Pre-defined plot types as well as custom plots via a code editor
- Generated plots can be downloaded as well.
- Utilizing AJAX requests to dynamically update web pages
- Responsive and intuitive web interface
- Extensive error handling
- Modular code