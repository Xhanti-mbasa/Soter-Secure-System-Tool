#!/usr/bin/env python3
"""Publish registered, already-built APKs; never rebuild or replace a release."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / 'sothis/releases'


def run(*args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def blob(commit, path):
    return subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Release:
    version: str
    commit: str
    apk: Path
    notes: Path
    sha256: str
    latest: bool

    @property
    def tag(self):
        return f'sothis-v{self.version}'


def plan(directory=RELEASES, read_blob=blob):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported release manifest schema')
    sums = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        sha, name = line.split()
        if name in sums or not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError('Invalid/duplicate checksum entry')
        sums[name] = sha
    entries = []
    versions = set()
    for item in manifest['releases']:
        version, commit = item['version'], item['commit']
        if not re.fullmatch(r'\d+\.\d+\.\d+', version) or version in versions:
            raise ValueError('Invalid/duplicate release version')
        if not re.fullmatch('[0-9a-f]{40}', commit):
            raise ValueError('Release source must be a full commit SHA')
        if item['notes'] != version + '.md':
            raise ValueError('Release notes must be a versioned local Markdown file')
        versions.add(version)
        apk, notes = directory / f'sothis-{version}.apk', directory / item['notes']
        data = apk.read_bytes()
        sha = digest(data)
        if sha != sums.get(apk.name):
            raise ValueError(f'APK checksum mismatch: {apk.name}')
        if data != read_blob(commit, f'sothis/releases/{apk.name}'):
            raise ValueError(f'APK differs from its source commit: {apk.name}')
        gradle = read_blob(commit, 'sothis/android/app/build.gradle').decode()
        if not re.search(r'versionName\s+[\'\"]' + re.escape(version) + r'[\'\"]', gradle):
            raise ValueError('Version does not match the source build configuration')
        with zipfile.ZipFile(apk) as archive:
            if archive.testzip() or not {'AndroidManifest.xml', 'classes.dex'}.issubset(archive.namelist()):
                raise ValueError('APK is incomplete or corrupt')
            for name in archive.namelist():
                if name.startswith('assets/') and not name.endswith('/'):
                    if '..' in Path(name).parts or archive.read(name) != read_blob(commit, 'sothis/android/app/src/main/' + name):
                        raise ValueError(f'Packaged asset differs from source: {name}')
        if not notes.read_text().strip():
            raise ValueError('Release notes are empty')
        entries.append(Release(version, commit, apk, notes, sha, version == manifest['latest']))
    if manifest['latest'] not in versions:
        raise ValueError('Latest version is not registered')
    # Older tracked APKs predate this publishing policy; every new version must register.
    for apk in directory.glob('sothis-*.apk'):
        match = re.fullmatch(r'sothis-(\d+\.\d+\.\d+)\.apk', apk.name)
        if not match or (tuple(map(int, match[1].split('.'))) >= (0, 7, 0) and match[1] not in versions):
            raise ValueError(f'Unregistered APK: {apk.name}')
    return sorted(entries, key=lambda e: tuple(map(int, e.version.split('.'))))


def api(path):
    result = subprocess.run(['gh', 'api', path], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        if 'HTTP 404' in result.stderr:
            return None
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def verify_tag(repo, release):
    ref = api(f'repos/{repo}/git/ref/tags/{release.tag}')
    if ref is None:
        return
    obj = ref['object']
    for _ in range(5):
        if obj['type'] == 'commit':
            if obj['sha'] != release.commit:
                raise ValueError(f'Existing tag points to different source: {release.tag}')
            return
        if obj['type'] != 'tag':
            break
        tagged = api(f'repos/{repo}/git/tags/{obj["sha"]}')
        if tagged is None:
            break
        obj = tagged['object']
    raise ValueError('Unsupported or unresolved tag target')


def find_release(repo, tag):
    # CLI handles authenticated draft lookup as well as public releases.
    result = subprocess.run(['gh', 'release', 'view', tag, '--repo', repo,
                             '--json', 'assets,isDraft,url'], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        if 'release not found' in result.stderr.lower():
            return None
        raise RuntimeError(result.stderr.strip())
    value = json.loads(result.stdout)
    return {'assets': value['assets'], 'draft': value['isDraft'], 'html_url': value['url']}


def publish(repo, release):
    verify_tag(repo, release)
    current = find_release(repo, release.tag)
    with tempfile.TemporaryDirectory(prefix='sothis-release-') as temporary:
        directory = Path(temporary)
        checksum = directory / f'sothis-{release.version}-SHA256SUMS.txt'
        checksum.write_text(f'{release.sha256}  {release.apk.name}\n')
        files = [release.apk, checksum]
        if current is None:
            run('gh', 'release', 'create', release.tag, *(str(f) for f in files), '--repo', repo,
                '--target', release.commit, '--title', f'Sothis {release.version}',
                '--notes-file', str(release.notes), '--draft', '--latest=false')
            current = find_release(repo, release.tag)
            if current is None:
                raise RuntimeError('Created release could not be inspected')
        names = {asset['name'] for asset in current['assets']}
        for file in files:
            if file.name not in names:
                if not current['draft']:
                    raise ValueError('Published release is missing an asset; repair requires review')
                run('gh', 'release', 'upload', release.tag, str(file), '--repo', repo)
            downloads = directory / 'downloaded'
            downloads.mkdir(exist_ok=True)
            run('gh', 'release', 'download', release.tag, '--pattern', file.name,
                '--dir', str(downloads), '--repo', repo)
            if digest((downloads / file.name).read_bytes()) != digest(file.read_bytes()):
                raise ValueError(f'Uploaded asset differs: {file.name}')
        if current['draft']:
            run('gh', 'release', 'edit', release.tag, '--repo', repo, '--draft=false',
                '--latest=' + str(release.latest).lower())
        final = find_release(repo, release.tag)
        if final is None or final['draft']:
            raise RuntimeError('Release was not published')
        verify_tag(repo, release)
        print(final['html_url'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='Xhanti-mbasa/Soter-Secure-System-Tool')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
        parser.error('Expected owner/repository')
    releases = plan()  # Verify everything before any public mutation.
    for release in releases:
        if args.dry_run:
            print(f'{release.tag}: {release.apk.name} ({release.sha256}), source {release.commit}')
        else:
            publish(args.repo, release)


if __name__ == '__main__':
    main()
