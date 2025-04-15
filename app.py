from flask import Flask, render_template, request, redirect, url_for, send_file
import subprocess
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_log():
    uploaded_file = request.files['logfile']
    if not uploaded_file or uploaded_file.filename == '':
        return "No file selected.", 400

    log_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
    uploaded_file.save(log_path)

    csv_name = uploaded_file.filename[:-4] + '.csv'
    csv_path = os.path.join(PROCESSED_FOLDER, csv_name)

    # TODO: ensure filenames are valid and files exist?

    # TODO: deal with the case of file existing

    # TODO: deal with the case of invalid file name

    result = subprocess.run(
        ['bash/validate_parse.sh', log_path, csv_path],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return f"Error processing file: {result.stdout}", 400

    return redirect(url_for('display_csv', filename=csv_name))

@app.route('/display')
def display_csv():
    filename = request.args.get('filename')
    path = os.path.join(PROCESSED_FOLDER, filename)

    if not os.path.exists(path):
        return "File not found", 404

    with open(path) as f:
        rows = [line.strip().split(',') for line in f.readlines()]

    headers = rows[0] if rows else []
    data = rows[1:] if len(rows) > 1 else []
    return render_template('display.html', headers=headers, rows=data, filename=filename)

@app.route('/download/<filename>')
def download_csv(filename):
    path = os.path.join(PROCESSED_FOLDER, filename)
    return send_file(path, as_attachment=True)

@app.route('/plots')
def show_plots():
    filename = request.args.get('filename')
    return render_template('plots.html', filename=filename)

if __name__ == '__main__':
    app.run(debug=True)
