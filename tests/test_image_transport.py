"""Run with Python 2.7 or 3: python -m unittest discover -s tests -p test_image_transport.py"""
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0, os.path.abspath('src/wubi/backends/common'))
import image

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.payload = b'root filesystem'
        self.part = dict(name='ubuntu-noble-amd64.tar.gz.part000', bytes=len(self.payload), sha256=hashlib.sha256(self.payload).hexdigest())
        self.manifest = dict(schema=1, ubuntu='24.04', arch='amd64', release='v24.04.1', image_bytes=len(self.payload), image_sha256=self.part['sha256'], minimum_disk_bytes=32*image.GIB, parts=[self.part])
    def tearDown(self):
        shutil.rmtree(self.directory)
    def path(self, name):
        return os.path.join(self.directory, name)
    def response(self, content):
        response = io.BytesIO(content)
        response.geturl = lambda: 'https://example.com/image'
        return response
    def test_manifest_large_integers_and_validation(self):
        path = self.path('image.json')
        with open(path, 'w') as f:
            json.dump(self.manifest, f)
        self.assertEqual(image.load_manifest(path), self.manifest)
        self.manifest['parts'][0]['name'] = '../root.disk'
        with open(path, 'w') as f:
            json.dump(self.manifest, f)
        self.assertRaises(ValueError, image.load_manifest, path)
    def test_download_short_corrupt_and_success(self):
        path = self.path('part')
        for content in (b'', self.payload[:-1], b'X'*len(self.payload)):
            self.assertRaises(ValueError, image.download_part, 'https://example.com', path, self.part, opener=lambda _: self.response(content))
            self.assertFalse(os.path.exists(path + '.partial'))
            self.assertFalse(os.path.exists(path))
        image.download_part('https://example.com', path, self.part, opener=lambda _: self.response(self.payload))
        self.assertEqual(image.digest(path), self.part['sha256'])
    def test_interruption_cleans_partial(self):
        def cancel(*args):
            raise RuntimeError('cancelled')
        self.assertRaises(RuntimeError, image.download_part, 'https://example.com', self.path('part'), self.part, cancel, lambda _: self.response(self.payload))
        self.assertFalse(os.path.exists(self.path('part.partial')))
    def archive(self, name='root.disk', extra=False):
        path = self.path('root.tar.gz')
        with tarfile.open(path, 'w:gz') as tar:
            member = tarfile.TarInfo(name)
            member.size = len(self.payload)
            tar.addfile(member, io.BytesIO(self.payload))
            if extra:
                tar.addfile(tarfile.TarInfo('extra'))
        return path
    def test_extract_and_reject_paths_extra_members_corruption(self):
        target = self.path('root.disk')
        image.extract_image(self.archive(), target, self.manifest)
        self.assertEqual(image.digest(target), self.part['sha256'])
        for name, extra in (('../root.disk', False), ('root.disk', True)):
            self.assertRaises(ValueError, image.extract_image, self.archive(name, extra), target, self.manifest)
            self.assertFalse(os.path.exists(target))
        self.manifest['image_sha256'] = '0'*64
        self.assertRaises(ValueError, image.extract_image, self.archive(), target, self.manifest)
        self.assertFalse(os.path.exists(target))
    def test_space_includes_parts_archive_and_reserve(self):
        self.assertEqual(image.required_space(self.manifest, 32*image.GIB), 33*image.GIB+2*len(self.payload))
        self.assertRaises(ValueError, image.required_space, self.manifest, 31*image.GIB)

if __name__ == '__main__':
    unittest.main()
