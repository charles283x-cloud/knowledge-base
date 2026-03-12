import os
import uuid
from datetime import datetime

import mammoth
import openpyxl
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_from_directory, abort, jsonify
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)

from config import (
    SECRET_KEY, SQLALCHEMY_DATABASE_URI, UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH, ALLOWED_EXTENSIONS
)
from models import Database, User, Document

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

db_path = SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
db = Database(db_path)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录'


@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(db, int(user_id))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext == 'docx':
        return 'word'
    elif ext in ('xlsx', 'xls'):
        return 'excel'
    return 'unknown'


# ---------- Auth Routes ----------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.get_by_username(db, username)
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))

        flash('用户名或密码错误', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------- Main Routes ----------

@app.route('/')
@login_required
def index():
    search = request.args.get('q', '').strip()
    documents = Document.get_all(db, search=search if search else None)
    return render_template('index.html', documents=documents, search=search)


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('没有选择文件', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('没有选择文件', 'error')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('不支持的文件格式，仅允许 .docx / .xlsx / .xls', 'error')
            return redirect(request.url)

        original_name = file.filename
        ext = original_name.rsplit('.', 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_name)
        file.save(file_path)

        file_size = os.path.getsize(file_path)
        file_type = get_file_type(original_name)
        description = request.form.get('description', '').strip()

        Document.create(db, unique_name, original_name, file_type, file_size, current_user.id, description)
        flash('文件上传成功', 'success')
        return redirect(url_for('index'))

    return render_template('upload.html')


# ---------- Document Preview ----------

@app.route('/doc/<int:doc_id>')
@login_required
def preview(doc_id):
    doc = Document.get_by_id(db, doc_id)
    if not doc:
        abort(404)

    file_path = os.path.join(UPLOAD_FOLDER, doc.filename)
    if not os.path.exists(file_path):
        abort(404)

    preview_content = ''
    sheets_data = None

    if doc.file_type == 'word':
        try:
            with open(file_path, 'rb') as f:
                result = mammoth.convert_to_html(f)
                preview_content = result.value
        except Exception as e:
            preview_content = f'<p class="text-red-500">文档预览失败: {str(e)}</p>'

    elif doc.file_type == 'excel':
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            sheets_data = {}
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = []
                for row in ws.iter_rows(values_only=True):
                    rows.append([str(cell) if cell is not None else '' for cell in row])
                sheets_data[sheet_name] = rows
            wb.close()
        except Exception as e:
            preview_content = f'<p class="text-red-500">文档预览失败: {str(e)}</p>'

    return render_template('preview.html', doc=doc, preview_content=preview_content, sheets_data=sheets_data)


@app.route('/download/<int:doc_id>')
@login_required
def download(doc_id):
    doc = Document.get_by_id(db, doc_id)
    if not doc:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, doc.filename, as_attachment=True, download_name=doc.original_name)


@app.route('/delete/<int:doc_id>', methods=['POST'])
@login_required
def delete_doc(doc_id):
    doc = Document.get_by_id(db, doc_id)
    if not doc:
        abort(404)

    if not current_user.is_admin and current_user.id != doc.uploaded_by:
        flash('没有权限删除此文件', 'error')
        return redirect(url_for('index'))

    filename = Document.delete(db, doc_id)
    if filename:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    flash('文件已删除', 'success')
    return redirect(url_for('index'))


# ---------- Admin Routes ----------

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))

    users = User.get_all(db)
    return render_template('admin.html', users=users)


@app.route('/admin/add_user', methods=['POST'])
@login_required
def add_user():
    if not current_user.is_admin:
        abort(403)

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    is_admin = request.form.get('is_admin') == '1'

    if not username or not password:
        flash('用户名和密码不能为空', 'error')
        return redirect(url_for('admin'))

    if len(password) < 4:
        flash('密码长度至少4位', 'error')
        return redirect(url_for('admin'))

    if User.create(db, username, password, is_admin):
        flash(f'用户 {username} 创建成功', 'success')
    else:
        flash(f'用户名 {username} 已存在', 'error')

    return redirect(url_for('admin'))


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        abort(403)

    if user_id == current_user.id:
        flash('不能删除自己的账号', 'error')
        return redirect(url_for('admin'))

    User.delete(db, user_id)
    flash('用户已删除', 'success')
    return redirect(url_for('admin'))


# ---------- Startup ----------

with app.app_context():
    db.init_db()
    from config import ADMIN_USERNAME, ADMIN_PASSWORD
    if not User.get_by_username(db, ADMIN_USERNAME):
        User.create(db, ADMIN_USERNAME, ADMIN_PASSWORD, is_admin=True)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
