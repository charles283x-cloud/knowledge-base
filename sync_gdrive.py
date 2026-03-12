"""
Google Drive → Knowledge Base sync script.

Syncs specified Google Drive folders via rclone, then imports
new/updated files into the knowledge base database.

Usage:
    python3 sync_gdrive.py

Designed to run as a cron job (e.g. every hour).
"""
import os
import sys
import subprocess
import shutil
import uuid
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SQLALCHEMY_DATABASE_URI, UPLOAD_FOLDER, ALLOWED_EXTENSIONS
from models import Database, Document, Folder, User

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SYNC] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(
            os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), 'uploads')),
            'sync.log'
        ))
    ]
)
log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────

RCLONE_REMOTE = os.environ.get('RCLONE_REMOTE', 'gdrive')

GDRIVE_FOLDERS = [
    '1、日本储能项目',
]

SYNC_DIR = os.path.join(
    os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), 'uploads')),
    'gdrive_sync'
)

SYNC_USER = 'gdrive-sync'


# ── Helpers ────────────────────────────────────────────────

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    type_map = {
        'docx': 'word', 'xlsx': 'excel', 'xls': 'excel',
        'pdf': 'pdf', 'pptx': 'ppt', 'ppt': 'ppt',
    }
    return type_map.get(ext, 'unknown')


def is_allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def run_rclone_sync():
    """Sync each configured Google Drive folder to local SYNC_DIR."""
    os.makedirs(SYNC_DIR, exist_ok=True)

    for folder_name in GDRIVE_FOLDERS:
        remote_path = f'{RCLONE_REMOTE}:{folder_name}'
        local_path = os.path.join(SYNC_DIR, folder_name)
        os.makedirs(local_path, exist_ok=True)

        log.info(f'Syncing: {remote_path} -> {local_path}')
        try:
            result = subprocess.run(
                ['rclone', 'sync', remote_path, local_path,
                 '--transfers', '4', '--checkers', '8', '-v'],
                capture_output=True, text=True, timeout=1800
            )
            if result.returncode == 0:
                log.info(f'Sync OK: {folder_name}')
            else:
                log.error(f'Sync failed for {folder_name}: {result.stderr}')
        except subprocess.TimeoutExpired:
            log.error(f'Sync timed out for {folder_name}')
        except FileNotFoundError:
            log.error('rclone not found. Please install rclone first.')
            sys.exit(1)


def ensure_sync_user(db):
    """Get or create the special sync user account."""
    user = User.get_by_username(db, SYNC_USER)
    if user:
        return user.id
    conn = db.get_connection()
    import bcrypt
    pw_hash = bcrypt.hashpw(uuid.uuid4().hex.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 0)",
        (SYNC_USER, pw_hash)
    )
    conn.commit()
    user_id = conn.execute(
        "SELECT id FROM users WHERE username = ?", (SYNC_USER,)
    ).fetchone()['id']
    conn.close()
    log.info(f'Created sync user: {SYNC_USER} (id={user_id})')
    return user_id


def get_or_create_folder(db, name, parent_id, user_id):
    """Find an existing folder or create it."""
    conn = db.get_connection()
    if parent_id is None:
        row = conn.execute(
            "SELECT * FROM folders WHERE name = ? AND parent_id IS NULL", (name,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM folders WHERE name = ? AND parent_id = ?", (name, parent_id)
        ).fetchone()
    conn.close()

    if row:
        return row['id']

    return Folder.create(db, name, user_id, parent_id)


def get_existing_files(db):
    """Return set of (original_name, folder_id) for all synced documents."""
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT original_name, folder_id, file_size FROM documents d "
        "JOIN users u ON d.uploaded_by = u.id WHERE u.username = ?",
        (SYNC_USER,)
    ).fetchall()
    conn.close()
    return {(r['original_name'], r['folder_id']): r['file_size'] for r in rows}


def import_files(db):
    """Walk the sync directory and import new/updated files into the DB."""
    user_id = ensure_sync_user(db)
    existing = get_existing_files(db)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    imported = 0
    updated = 0
    skipped = 0

    for gdrive_folder in GDRIVE_FOLDERS:
        folder_root = os.path.join(SYNC_DIR, gdrive_folder)
        if not os.path.isdir(folder_root):
            continue

        root_folder_id = get_or_create_folder(db, gdrive_folder, None, user_id)

        for dirpath, dirnames, filenames in os.walk(folder_root):
            rel_dir = os.path.relpath(dirpath, folder_root)
            if rel_dir == '.':
                current_folder_id = root_folder_id
            else:
                parts = rel_dir.replace('\\', '/').split('/')
                current_folder_id = root_folder_id
                for part in parts:
                    current_folder_id = get_or_create_folder(db, part, current_folder_id, user_id)

            for fname in filenames:
                if not is_allowed(fname):
                    continue

                src_path = os.path.join(dirpath, fname)
                file_size = os.path.getsize(src_path)
                key = (fname, current_folder_id)

                if key in existing:
                    if existing[key] == file_size:
                        skipped += 1
                        continue
                    # File changed, delete old and re-import
                    conn = db.get_connection()
                    row = conn.execute(
                        "SELECT id, filename FROM documents WHERE original_name = ? AND folder_id = ? "
                        "AND uploaded_by = ?",
                        (fname, current_folder_id, user_id)
                    ).fetchone()
                    if row:
                        old_path = os.path.join(UPLOAD_FOLDER, row['filename'])
                        if os.path.exists(old_path):
                            os.remove(old_path)
                        conn.execute("DELETE FROM documents WHERE id = ?", (row['id'],))
                        conn.commit()
                    conn.close()
                    updated += 1
                else:
                    imported += 1

                ext = fname.rsplit('.', 1)[1].lower()
                unique_name = f"{uuid.uuid4().hex}.{ext}"
                dst_path = os.path.join(UPLOAD_FOLDER, unique_name)
                shutil.copy2(src_path, dst_path)

                file_type = get_file_type(fname)
                Document.create(db, unique_name, fname, file_type, file_size,
                                user_id, 'Google Drive 同步', current_folder_id)

    log.info(f'Import done: {imported} new, {updated} updated, {skipped} unchanged')


# ── Main ───────────────────────────────────────────────────

def main():
    db_path = SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
    db = Database(db_path)
    db.init_db()

    log.info('=== Google Drive Sync Started ===')

    run_rclone_sync()
    import_files(db)

    log.info('=== Google Drive Sync Completed ===')


if __name__ == '__main__':
    main()
