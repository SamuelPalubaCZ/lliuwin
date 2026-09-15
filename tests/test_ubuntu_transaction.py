"""Portable failure injection for Windows ownership and rollback."""
import contextlib
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
sys.path.insert(0, os.path.abspath('src/wubi/backends/common'))
import image
# The transaction itself is portable; replace only platform imports.
for name in ('wubi', 'wubi.backends', 'wubi.backends.common', 'wubi.backends.common.utils'):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
sys.modules['wubi.backends.common'].image = image
sys.modules['wubi.backends.common.utils'].run_command = lambda command: ''
ubuntu = types.ModuleType('ubuntu_transaction')
with open('src/wubi/backends/win32/ubuntu.py') as source:
    eval(compile(source.read(), source.name, 'exec'), ubuntu.__dict__)

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.directory = os.path.join(self.base, 'lliuwin')
        os.mkdir(self.directory)
        self.state = dict(schema=1, id='a'*32, bcd='{11111111-1111-1111-1111-111111111111}', efi=True)
        self.original_esp = ubuntu.mounted_esp
        self.original_tool = ubuntu.system_tool
        ubuntu.system_tool = lambda name: name
        @contextlib.contextmanager
        def esp(run):
            yield self.base
        ubuntu.mounted_esp = esp
    def tearDown(self):
        ubuntu.mounted_esp = self.original_esp
        ubuntu.system_tool = self.original_tool
        shutil.rmtree(self.base)
    def test_journal_and_invalid_ownership(self):
        ubuntu.save_state(self.directory, self.state)
        self.assertEqual(ubuntu.read_state(self.directory), self.state)
        self.state['id'] = '../Microsoft'
        ubuntu.save_state(self.directory, self.state)
        self.assertRaises(ValueError, ubuntu.read_state, self.directory)
    def test_bcd_failure_preserves_recovery_files(self):
        calls = []
        def run(command):
            calls.append(command)
            if '/enum' in command:
                return self.state['bcd']
            raise RuntimeError('BCD deletion failed')
        self.assertRaises(RuntimeError, ubuntu.remove_boot, self.state, run)
        self.assertEqual(len(calls), 2)
        self.assertTrue(os.path.isdir(self.directory))
    def test_absent_bcd_entry_is_idempotent(self):
        self.state['efi'] = False
        calls = []
        ubuntu.remove_boot(self.state, lambda command: calls.append(command) or '')
        self.assertEqual(len(calls), 1)
    def test_efi_mount_failure_propagates(self):
        @contextlib.contextmanager
        def failing(run):
            raise RuntimeError('EFI unavailable')
            yield
        ubuntu.mounted_esp = failing
        self.state['bcd'] = None
        self.assertRaises(RuntimeError, ubuntu.remove_boot, self.state)

if __name__ == '__main__':
    unittest.main()
