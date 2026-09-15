#!/usr/bin/env python
#
# Copyright (c) 2008 Agostino Russo
#
# Written by Agostino Russo <agostino.russo@gmail.com>
#
# This file is part of Wubi the Win32 Ubuntu Installer.
#
# Wubi is free software; you can redistribute it and/or modify
# it under 5the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 2.1 of
# the License, or (at your option) any later version.
#
# Wubi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# once compiled and packaged by pypack,
# all dependencies will be in ./lib,
# so let's add ./lib to the path
import sys
import os
root_dir = os.path.abspath(os.path.dirname(__file__))
lib_dir = os.path.join(root_dir, 'lib')
sys.path.insert(0, lib_dir)

from wubi.application import Wubi

try:
    from version import application_name, version, revision
except:
    application_name = "wubi"
    version = "0.0"
    revision = "0"

if '--self-test' in sys.argv:
    import ssl
    from wubi.backends.common import image
    from wubi.backends.win32 import ubuntu
    if sys.version_info[:3] != (2, 7, 18):
        raise RuntimeError('Unexpected packaged Python runtime')
    ssl.create_default_context()
    if not os.path.isfile(os.path.join(root_dir, 'data', 'image.json')):
        raise RuntimeError('Missing bundled image manifest')
    with open(os.path.join(root_dir, 'self-test.ok'), 'w') as stream:
        stream.write('Python 2.7.18, application imports, TLS and bundled manifest OK\n')
    sys.exit(0)

application = Wubi(application_name, version, revision, root_dir)
application.run()
