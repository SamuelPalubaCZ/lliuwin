#!/usr/bin/env python3
"""wixl package for the launcher. Ubuntu itself is removed using its uninstaller."""
import pathlib
import subprocess
import uuid
import xml.etree.ElementTree as E
ns = 'http://schemas.microsoft.com/wix/2006/wi'
E.register_namespace('', ns)
def add(parent, tag, **attrs):
    return E.SubElement(parent, '{%s}%s' % (ns, tag), attrs)
root = E.Element('{%s}Wix' % ns)
p = add(root, 'Product', Id=str(uuid.uuid4()), Name='LLiuWin Ubuntu Installer', Language='1033', Version='24.4.0', Manufacturer='LLiuWin contributors', UpgradeCode='4DDC206B-B635-4FA2-9ACF-A4C8BD8A9F20')
add(p, 'Package', InstallerVersion='200', Compressed='yes', InstallScope='perMachine')
add(p, 'Media', Id='1', Cabinet='installer.cab', EmbedCab='yes')
d = add(p, 'Directory', Id='TARGETDIR', Name='SourceDir')
d = add(d, 'Directory', Id='ProgramFilesFolder')
d = add(d, 'Directory', Id='INSTALLDIR', Name='LLiuWin')
c = add(d, 'Component', Id='Launcher', Guid='97573A36-1D77-4B62-BB4E-D7489C3BDC10')
add(c, 'File', Id='Installer', Name='lliuwin.exe', Source='build/lliuwin.exe', KeyPath='yes')
f = add(p, 'Feature', Id='Main', Title='LLiuWin', Level='1')
add(f, 'ComponentRef', Id='Launcher')
E.ElementTree(root).write('build/lliuwin.wxs', encoding='utf-8', xml_declaration=True)
subprocess.run(['wixl', '-o', 'build/lliuwin.msi', 'build/lliuwin.wxs'], check=True)
