from flask import Flask, request, render_template, redirect, url_for
import os  # Import os module here
from processing_script import process_txt, get_image_for_key

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            result = process_txt(file_path)
            return render_template('results.html', result=result, file_path=file_path, get_image_for_key=get_image_for_key, os=os)  # Pass 'os' module explicitly

    # Provide a list of file names without extensions for the sidebar
    file_paths = [os.path.join(app.config['UPLOAD_FOLDER'], f) for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.endswith('.txt')]
    return render_template('index.html', file_paths=file_paths, os=os)  # Pass 'os' module explicitly

@app.route('/results/<file_name>')
def results(file_name):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
    result = process_txt(file_path)  # Assuming this function processes the text file and returns results
    return render_template('results.html', result=result, file_path=file_path, get_image_for_key=get_image_for_key, os=os)  # Pass 'os' module explicitly

if __name__ == '__main__':
    app.run(debug=True)
