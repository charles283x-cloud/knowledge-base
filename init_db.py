"""Initialize the database and create the admin account."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from config import SQLALCHEMY_DATABASE_URI, ADMIN_USERNAME, ADMIN_PASSWORD, UPLOAD_FOLDER
from models import Database, User


def init():
    db_path = SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    db = Database(db_path)
    db.init_db()

    if not User.get_by_username(db, ADMIN_USERNAME):
        User.create(db, ADMIN_USERNAME, ADMIN_PASSWORD, is_admin=True)
        print(f"Admin account created: {ADMIN_USERNAME}")
    else:
        print(f"Admin account already exists: {ADMIN_USERNAME}")

    print("Database initialized successfully.")


if __name__ == '__main__':
    init()
