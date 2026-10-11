import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release_publisher', Path(__file__).resolve().parents[1] / 'scripts/publish_releases.py')
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)


class ReleaseChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apk = self.root / 'sothis-0.7.1.apk'
        with zipfile.ZipFile(self.apk, 'w') as z:
            z.writestr('AndroidManifest.xml', b'manifest')
            z.writestr('classes.dex', b'dex')
            z.writestr('assets/index.html', b'public interface')
        self.sha = p.digest(self.apk.read_bytes())
        self.commit = 'a' * 40
        self.manifest = {'schema': 1, 'latest': '0.7.1', 'releases': [
            {'version': '0.7.1', 'commit': self.commit, 'notes': '0.7.1.md'}]}
        self.write_manifest()
        (self.root / '0.7.1.md').write_text('Tested release notes')
        (self.root / 'SHA256SUMS').write_text(f'{self.sha}  {self.apk.name}\n')
        self.objects = {'sothis/releases/' + self.apk.name: self.apk.read_bytes(),
                        'sothis/android/app/build.gradle': b'versionName "0.7.1"',
                        'sothis/android/app/src/main/assets/index.html': b'public interface'}

    def write_manifest(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest))

    def plan(self):
        return p.plan(self.root, lambda commit, path: self.objects[path])

    def test_verified_plan_and_namespaced_tag(self):
        r = self.plan()[0]
        self.assertEqual((r.tag, r.sha256, r.latest), ('sothis-v0.7.1', self.sha, True))

    def test_corrupted_apk_stops_before_publishing(self):
        self.apk.write_bytes(self.apk.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            self.plan()

    def test_committed_apk_must_match(self):
        self.objects['sothis/releases/' + self.apk.name] = b'different binary'
        with self.assertRaisesRegex(ValueError, 'source commit'):
            self.plan()

    def test_packaged_assets_must_match(self):
        self.objects['sothis/android/app/src/main/assets/index.html'] = b'different source'
        with self.assertRaisesRegex(ValueError, 'Packaged asset'):
            self.plan()

    def test_unregistered_future_version_is_rejected(self):
        (self.root / 'sothis-0.8.0.apk').write_bytes(b'unregistered')
        with self.assertRaisesRegex(ValueError, 'Unregistered APK'):
            self.plan()

    def test_invalid_notes_and_duplicate_versions(self):
        self.manifest['releases'][0]['notes'] = '../secrets.txt'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'versioned local'):
            self.plan()
        self.manifest['releases'][0]['notes'] = '0.7.1.md'
        self.manifest['releases'] *= 2
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'duplicate release version'):
            self.plan()

    def test_tag_collision_aborts(self):
        release = self.plan()[0]
        with patch.object(p, 'api', return_value={'object': {'type': 'commit', 'sha': 'b' * 40}}):
            with self.assertRaisesRegex(ValueError, 'different source'):
                p.verify_tag('owner/repo', release)

    def publisher(self, existing=False, corrupt=False):
        release = self.plan()[0]
        names = [self.apk.name, 'sothis-0.7.1-SHA256SUMS.txt']
        initial = {'assets': [{'name': n} for n in names], 'draft': not existing, 'html_url': 'release-url'}
        final = {**initial, 'draft': False}
        calls = []

        def execute(*args):
            calls.append(args)
            if args[1:3] == ('release', 'download'):
                name = args[args.index('--pattern') + 1]
                target = Path(args[args.index('--dir') + 1]) / name
                target.write_bytes((b'corrupt' if corrupt else self.apk.read_bytes()) if name.endswith('.apk')
                                   else f'{self.sha}  {self.apk.name}\n'.encode())
            return ''

        sequence = [initial, final] if existing else [None, initial, final]
        with patch.object(p, 'verify_tag'), patch.object(p, 'find_release', side_effect=sequence), patch.object(p, 'run', side_effect=execute):
            p.publish('owner/repo', release)
        return calls

    def test_verified_assets_are_published_after_download(self):
        calls = self.publisher()
        create = next(a for a in calls if a[1:3] == ('release', 'create'))
        self.assertIn('--draft', create)
        self.assertEqual(create[create.index('--target') + 1], self.commit)
        self.assertEqual(calls[-1][1:3], ('release', 'edit'))
        self.assertIn('--draft=false', calls[-1])

    def test_repeated_run_keeps_published_assets(self):
        self.assertTrue(all(a[1:3] == ('release', 'download') for a in self.publisher(existing=True)))

    def test_bad_download_never_publishes_draft(self):
        with self.assertRaisesRegex(ValueError, 'Uploaded asset differs'):
            self.publisher(corrupt=True)


if __name__ == '__main__':
    unittest.main()
