import sqlite3
import os
from datetime import datetime

import bcrypt
from flask_login import UserMixin


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_db(self):
        conn = self.get_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                uploaded_by INTEGER NOT NULL,
                uploaded_at TEXT DEFAULT (datetime('now')),
                description TEXT DEFAULT '',
                FOREIGN KEY (uploaded_by) REFERENCES users(id)
            );
        """)
        conn.commit()
        conn.close()


class User(UserMixin):
    def __init__(self, id, username, password_hash, is_admin=False):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.is_admin = bool(is_admin)

    @staticmethod
    def create(db, username, password, is_admin=False):
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn = db.get_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                (username, password_hash, int(is_admin))
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    @staticmethod
    def get_by_id(db, user_id):
        conn = db.get_connection()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['password_hash'], row['is_admin'])
        return None

    @staticmethod
    def get_by_username(db, username):
        conn = db.get_connection()
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['password_hash'], row['is_admin'])
        return None

    @staticmethod
    def get_all(db):
        conn = db.get_connection()
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        conn.close()
        return [User(r['id'], r['username'], r['password_hash'], r['is_admin']) for r in rows]

    @staticmethod
    def delete(db, user_id):
        conn = db.get_connection()
        conn.execute("DELETE FROM users WHERE id = ? AND is_admin = 0", (user_id,))
        conn.commit()
        conn.close()

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))


class Document:
    def __init__(self, id, filename, original_name, file_type, file_size, uploaded_by, uploaded_at, description=''):
        self.id = id
        self.filename = filename
        self.original_name = original_name
        self.file_type = file_type
        self.file_size = file_size
        self.uploaded_by = uploaded_by
        self.uploaded_at = uploaded_at
        self.description = description

    @property
    def size_display(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"

    @staticmethod
    def create(db, filename, original_name, file_type, file_size, uploaded_by, description=''):
        conn = db.get_connection()
        cursor = conn.execute(
            "INSERT INTO documents (filename, original_name, file_type, file_size, uploaded_by, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (filename, original_name, file_type, file_size, uploaded_by, description)
        )
        doc_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return doc_id

    @staticmethod
    def get_by_id(db, doc_id):
        conn = db.get_connection()
        row = conn.execute(
            "SELECT d.*, u.username as uploader_name FROM documents d "
            "JOIN users u ON d.uploaded_by = u.id WHERE d.id = ?",
            (doc_id,)
        ).fetchone()
        conn.close()
        if row:
            doc = Document(
                row['id'], row['filename'], row['original_name'], row['file_type'],
                row['file_size'], row['uploaded_by'], row['uploaded_at'], row['description']
            )
            doc.uploader_name = row['uploader_name']
            return doc
        return None

    @staticmethod
    def get_all(db, search=None):
        conn = db.get_connection()
        if search:
            rows = conn.execute(
                "SELECT d.*, u.username as uploader_name FROM documents d "
                "JOIN users u ON d.uploaded_by = u.id "
                "WHERE d.original_name LIKE ? OR d.description LIKE ? "
                "ORDER BY d.uploaded_at DESC",
                (f'%{search}%', f'%{search}%')
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT d.*, u.username as uploader_name FROM documents d "
                "JOIN users u ON d.uploaded_by = u.id "
                "ORDER BY d.uploaded_at DESC"
            ).fetchall()
        conn.close()
        docs = []
        for r in rows:
            doc = Document(
                r['id'], r['filename'], r['original_name'], r['file_type'],
                r['file_size'], r['uploaded_by'], r['uploaded_at'], r['description']
            )
            doc.uploader_name = r['uploader_name']
            docs.append(doc)
        return docs

    @staticmethod
    def delete(db, doc_id):
        conn = db.get_connection()
        row = conn.execute("SELECT filename FROM documents WHERE id = ?", (doc_id,)).fetchone()
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
        return row['filename'] if row else None
