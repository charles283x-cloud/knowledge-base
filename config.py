import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DATA_DIR = os.environ.get('DATA_DIR', os.path.join(BASE_DIR, 'uploads'))

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(DATA_DIR, 'knowledge.db')}"

UPLOAD_FOLDER = os.path.join(DATA_DIR, 'files')

MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

ALLOWED_EXTENSIONS = {'docx', 'xlsx', 'xls', 'pdf', 'pptx', 'ppt'}

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
