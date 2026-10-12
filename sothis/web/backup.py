"""Write SQLite online backups and immutable originals to stdout."""
import os
import sqlite3
import sys
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path


def make_backup(root, output):
    root = Path(root)
    if not (root / 'lens.sqlite3').is_file():
        raise ValueError('Research database not found.')
    with tempfile.TemporaryDirectory() as temporary, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('lens.sqlite3', 'auth.sqlite3'):
            source = root / name
            if not source.is_file():
                continue
            copy = Path(temporary) / name
            with closing(sqlite3.connect(f'file:{source}?mode=ro', uri=True)) as origin, closing(sqlite3.connect(copy)) as destination:
                with destination:
                    origin.backup(destination)
            archive.write(copy, name)
        for file in sorted((root / 'archive').glob('*')):
            if file.is_file() and not file.is_symlink():
                archive.write(file, 'archive/' + file.name)


def main():
    make_backup(os.environ.get('SOTHIS_DATA', 'data'), sys.stdout.buffer)


if __name__ == '__main__':
    main()
