import sqlite3
import json
import time
from pathlib import Path
from typing import List, Optional
from api.common.models import CloudFile

DB_PATH = Path.home() / '.cloudmanager_cache.db'

class FolderCache:
    def __init__(self):
        # При инициализации просто проверяем, что таблицы существуют
        self._init_db()

    def _get_conn(self):
        """Создаёт новое соединение с базой для текущего потока."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA journal_mode=WAL")  # улучшает параллельный доступ
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.execute('''CREATE TABLE IF NOT EXISTS folder_cache
                 (path TEXT, provider_type TEXT, data TEXT, updated REAL)''')
            conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_folder 
                 ON folder_cache(path, provider_type)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS file_hashes
                 (file_path TEXT PRIMARY KEY, remote_hash TEXT, local_hash TEXT)''')
            conn.commit()
        finally:
            conn.close()

    # ---------- кеш папок ----------
    def save(self, path: str, provider_type: str, files: List[CloudFile]):
        conn = self._get_conn()
        try:
            data = json.dumps([{
                'name': f.name,
                'path': f.path,
                'is_dir': f.is_dir,
                'size': f.size,
                'mime_type': f.mime_type,
                'file_id': f.file_id,
                'is_downloaded': getattr(f, 'is_downloaded', False),
                'is_synced': getattr(f, 'is_synced', False)
            } for f in files])
            conn.execute(
                'INSERT OR REPLACE INTO folder_cache VALUES (?, ?, ?, ?)',
                (path, provider_type, data, time.time())
            )
            conn.commit()
        finally:
            conn.close()

    def load(self, path: str, provider_type: str) -> Optional[List[CloudFile]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                'SELECT data FROM folder_cache WHERE path=? AND provider_type=?',
                (path, provider_type)
            ).fetchone()
            if row:
                items_dicts = json.loads(row[0])
                for d in items_dicts:
                    d['modified_at'] = None
                return [CloudFile(**d) for d in items_dicts]
            return None
        finally:
            conn.close()

    def get_mtime(self, path: str) -> Optional[float]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                'SELECT updated FROM folder_cache WHERE path=? AND provider_type=?',
                (path, 'local')
            ).fetchone()
            if row:
                return row[0]
            return None
        finally:
            conn.close()

    # ---------- кеш хешей ----------
    def save_hashes(self, remote_path: str, remote_hash: Optional[str], local_hash: Optional[str]):
        conn = self._get_conn()
        try:
            conn.execute(
                'INSERT OR REPLACE INTO file_hashes VALUES (?, ?, ?)',
                (remote_path, remote_hash, local_hash)
            )
            conn.commit()
        finally:
            conn.close()

    def get_hashes(self, remote_path: str) -> dict:
        conn = self._get_conn()
        try:
            row = conn.execute(
                'SELECT remote_hash, local_hash FROM file_hashes WHERE file_path=?',
                (remote_path,)
            ).fetchone()
            if row:
                return {'remote_hash': row[0], 'local_hash': row[1]}
            return {}
        finally:
            conn.close()