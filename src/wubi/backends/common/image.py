"""Versioned Ubuntu image transport. Compatible with Python 2.7 and 3."""
from __future__ import division
import hashlib
import json
import numbers
import os
import re
import ssl
import tarfile
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

GIB = 1024 ** 3


def load_manifest(path):
    with open(path) as stream:
        manifest = json.load(stream)
    if manifest.get('schema') != 1 or manifest.get('ubuntu') != '24.04' or manifest.get('arch') != 'amd64':
        raise ValueError('Unsupported image manifest')
    if not re.match(r'^v[0-9][A-Za-z0-9.-]*$', manifest.get('release', '')):
        raise ValueError('This development build has no released Ubuntu image')
    for field in ('image_bytes', 'minimum_disk_bytes'):
        if not isinstance(manifest.get(field), numbers.Integral) or not 0 < manifest[field] <= 1024 * GIB:
            raise ValueError('Invalid image size')
    if manifest['minimum_disk_bytes'] < manifest['image_bytes']:
        raise ValueError('Image cannot fit minimum disk')
    if not re.match(r'^[a-f0-9]{64}$', manifest.get('image_sha256', '')):
        raise ValueError('Invalid image digest')
    parts = manifest.get('parts', [])
    if not parts or len(parts) > 128:
        raise ValueError('Missing or excessive image parts')
    names = set()
    for part in parts:
        if not re.match(r'^ubuntu-noble-amd64\.tar\.gz\.part[0-9]{3}$', part.get('name', '')) or part['name'] in names:
            raise ValueError('Invalid or duplicate part name')
        names.add(part['name'])
        if not isinstance(part.get('bytes'), numbers.Integral) or not 0 < part['bytes'] <= GIB:
            raise ValueError('Invalid part size')
        if not re.match(r'^[a-f0-9]{64}$', part.get('sha256', '')):
            raise ValueError('Invalid part digest')
    if [p['name'] for p in parts] != ['ubuntu-noble-amd64.tar.gz.part%03d' % n for n in range(len(parts))]:
        raise ValueError('Image parts out of order')
    return manifest


def digest(path):
    checksum = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def required_space(manifest, disk_bytes):
    if disk_bytes < manifest['minimum_disk_bytes']:
        raise ValueError('Selected disk is smaller than the image minimum')
    # Downloaded parts plus assembled archive coexist until extraction completes.
    return disk_bytes + 2 * sum(p['bytes'] for p in manifest['parts']) + GIB


def download_part(url, path, part, progress=None, opener=None):
    if os.path.isfile(path) and os.path.getsize(path) == part['bytes'] and digest(path) == part['sha256']:
        return path
    temporary = path + '.partial'
    checksum = hashlib.sha256()
    count = 0
    response = None
    try:
        if opener is None:
            response = urlopen(url, timeout=60, context=ssl.create_default_context())
        else:
            response = opener(url)
        if not response.geturl().startswith('https://'):
            raise ValueError('Refusing an insecure download redirect')
        with open(temporary, 'wb') as stream:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > part['bytes']:
                    raise ValueError('Download exceeds expected size')
                stream.write(chunk)
                checksum.update(chunk)
                if progress:
                    progress(count, part['bytes'])
        if count != part['bytes'] or checksum.hexdigest() != part['sha256']:
            raise ValueError('Image part is incomplete or SHA-256 does not match')
        if os.path.exists(path):
            os.remove(path)
        os.rename(temporary, path)
        return path
    finally:
        if response is not None:
            response.close()
        if os.path.exists(temporary):
            os.remove(temporary)


def extract_image(archive, destination, manifest, progress=None):
    """Extract exactly one regular root.disk; never follow archive paths/links."""
    checksum = hashlib.sha256()
    count = 0
    try:
        with tarfile.open(archive, 'r|gz') as tar:
            member = tar.next()
            if member is None or member.name != 'root.disk' or not member.isfile() or member.size != manifest['image_bytes']:
                raise ValueError('Unexpected image archive member')
            source = tar.extractfile(member)
            with open(destination, 'wb') as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    count += len(chunk)
                    checksum.update(chunk)
                    target.write(chunk)
                    if progress:
                        progress(count, member.size)
            source.close()
            if tar.next() is not None:
                raise ValueError('Image archive contains extra members')
        if count != manifest['image_bytes'] or checksum.hexdigest() != manifest['image_sha256']:
            raise ValueError('Extracted image checksum mismatch')
    except BaseException:
        if os.path.exists(destination):
            os.remove(destination)
        raise
