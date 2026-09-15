#!/usr/bin/env python3
"""Package an already checked image; emit the manifest bundled into its installer."""
import hashlib
import json
import pathlib
import re
import subprocess
import sys

out = pathlib.Path(sys.argv[1])
release = sys.argv[2]
assert re.fullmatch(r'v[0-9][A-Za-z0-9.-]*', release)
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()
manifest = dict(schema=1, ubuntu='24.04', arch='amd64', release=release,
                image_bytes=(out / 'root.disk').stat().st_size,
                minimum_disk_bytes=32 * 1024**3, image_sha256=sha(out / 'root.disk'), parts=[])
archive = out / 'ubuntu-noble-amd64.tar.gz'
subprocess.run(['tar', '-czf', str(archive), '-C', str(out), 'root.disk'], check=True)
with archive.open('rb') as f:
    index = 0
    while True:
        block = f.read(1024**3)
        if not block:
            break
        part = out / (archive.name + '.part%03d' % index)
        part.write_bytes(block)
        manifest['parts'].append(dict(name=part.name, bytes=len(block), sha256=sha(part)))
        index += 1
(out / 'image.json').write_text(json.dumps(manifest, indent=2) + '\n')
archive.unlink()
(out / 'root.disk').unlink()
