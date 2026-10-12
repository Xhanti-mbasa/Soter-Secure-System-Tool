"""Opaque, revocable sessions. Passwords and session tokens never enter logs."""
import hashlib
import hmac
import secrets
import sqlite3
import time
from pathlib import Path

from engine.core import ClosingConnection


def password_hash(password):
    if not 12 <= len(password) <= 1024:
        raise ValueError('Use a password between 12 and 1024 characters.')
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return 'scrypt:' + salt.hex() + ':' + key.hex()


def valid_hash(encoded):
    parts = encoded.split(':')
    try:
        return len(parts) == 3 and parts[0] == 'scrypt' and len(bytes.fromhex(parts[1])) == 16 and len(bytes.fromhex(parts[2])) == 64
    except ValueError:
        return False


def verify_password(password, encoded):
    if not isinstance(password, str) or len(password) > 1024 or not valid_hash(encoded):
        return False
    _, salt, expected = encoded.split(':')
    key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return hmac.compare_digest(key.hex(), expected)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Auth:
    def __init__(self, root, username, encoded_password, hours=12):
        self.path = Path(root) / 'auth.sqlite3'
        self.username, self.password = username, encoded_password
        self.lifetime = hours * 3600
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, csrf TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS attempts(bucket TEXT, at REAL);
                CREATE INDEX IF NOT EXISTS attempts_time ON attempts(at);
            ''')
            stamp = token_hash(username + ':' + encoded_password)
            old = db.execute("SELECT value FROM config WHERE key='credential'").fetchone()
            if not old or old[0] != stamp:
                db.execute('DELETE FROM sessions')
                db.execute("INSERT OR REPLACE INTO config VALUES ('credential',?)", (stamp,))

    def connect(self):
        return sqlite3.connect(self.path, timeout=30, factory=ClosingConnection)

    def allow_login(self, address):
        # The socket peer is used; untrusted forwarded/client-IP headers are ignored.
        # A shared proxy therefore shares this conservative limit.
        now = time.time()
        bucket = token_hash(address or 'unknown')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM attempts WHERE at < ?', (now - 600,))
            total = db.execute('SELECT count(*) FROM attempts').fetchone()[0]
            peer = db.execute('SELECT count(*) FROM attempts WHERE bucket=?', (bucket,)).fetchone()[0]
            if total >= 100 or peer >= 20:
                return False
            db.execute('INSERT INTO attempts VALUES (?,?)', (bucket, now))
        return True

    def login(self, username, password):
        # Still run the password hash for a wrong username.
        good = verify_password(password, self.password)
        if not isinstance(username, str) or not hmac.compare_digest(username.encode(), self.username.encode()) or not good:
            return None
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires <= ?', (now,))
            db.execute('INSERT INTO sessions VALUES (?,?,?)', (token_hash(token), csrf, now + self.lifetime))
        return token, csrf

    def session(self, token):
        if not token or len(token) > 128:
            return None
        with self.connect() as db:
            row = db.execute('SELECT csrf,expires FROM sessions WHERE token_hash=?', (token_hash(token),)).fetchone()
        if row and row[1] > time.time():
            return {'username': self.username, 'csrf': row[0], 'expires_at': row[1]}
        return None

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(token),))
