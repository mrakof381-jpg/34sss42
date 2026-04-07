import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super-secret-key-12345"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

users = {
    "admin": {"password": generate_password_hash("admin1233422"), "id": "1", "role": "admin"},
    "fisher1337":  {"password": generate_password_hash("fisher943992@28438438"), "id": "2", "role": "OWNER"}
}

@login_manager.user_loader
def load_user(user_id):
    for username, data in users.items():
        if data["id"] == user_id:
            return User(user_id, username, data["role"])
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_data = users.get(username)
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data['id'], username, user_data['role'])
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
            mtime = os.path.getmtime(filepath)
            files.append({
                'name': filename,
                'size': f"{size / 1024:.1f} KB",
                'upload_time_short': datetime.fromtimestamp(mtime).strftime('%d.%m %H:%M')
            })
    files.sort(key=lambda x: x['upload_time_short'], reverse=True)
    
    is_admin = getattr(current_user, 'role', None) == 'admin'
    
    return render_template('dashboard.html', files=files, is_admin=is_admin)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if getattr(current_user, 'role', None) != 'admin':
        flash('Нет прав на загрузку файлов', 'danger')
        return redirect(url_for('dashboard'))
    
    file = request.files.get('file')
    if not file or not file.filename:
        flash('Файл не выбран', 'danger')
        return redirect(url_for('dashboard'))
    
    filename = secure_filename(file.filename)
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    flash('Файл успешно загружен!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/delete/<filename>')
@login_required
def delete_file(filename):
    if getattr(current_user, 'role', None) != 'admin':
        flash('Нет прав на удаление', 'danger')
        return redirect(url_for('dashboard'))
    try:
        os.remove(os.path.join(UPLOAD_FOLDER, filename))
        flash('Файл удалён', 'success')
    except:
        flash('Ошибка удаления файла', 'danger')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)