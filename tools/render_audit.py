#!/usr/bin/env python3
"""Render the captured evidence; classifications are triage, not claimed reproductions."""
import json
import pathlib
import subprocess
root = pathlib.Path(__file__).resolve().parents[1]
d = json.loads((root / 'docs/upstream-snapshot.json').read_text())
def clean(s):
    return s.replace('|', '/').replace('\n', ' ')
lines = ['# Upstream audit', '', 'Snapshot: '+d['date'], '',
'Wubi → hakuna-m/wubiuefi → lliurex/lliuwin → SamuelPalubaCZ/lliuwin. Common ancestor: `'+d['lliurex']['merge_base_commit']['sha']+'`. LliureX is 118 commits ahead and 3 behind the captured upstream master. Original authors and license headers remain in Git history.', '',
'Per the revised scope, the 172 discovered forks are inventoried but not all are reviewed in depth. Branch names and SHAs, release notes and the five latest CI results per fork are retained in [the snapshot](docs/upstream-snapshot.json). An absent CI run is not proof of failure or success. Branch-only experiments require separate review.', '',
'## Relevant forks', '',
'| Fork / branch | Relevant change | Decision |', '|---|---|---|',
'| [litmount](https://github.com/litmount/wubiuefi) | Headless Wine32/Xvfb and MinGW builds; [successful CI](https://github.com/litmount/wubiuefi/actions/runs/27163766443) | Use the platform approach. Reject Python DLL / compressor fallbacks from unrelated repositories. Our Python MSI is downloaded from python.org and pinned by SHA-256. A built EXE does not demonstrate Ubuntu installation. |',
'| [CalinGH/modernize](https://github.com/CalinGH/wubiuefi/tree/modernize) | Python 3, modern Windows checks, modern installer; commit `a8465ab407d8` uses explicit loop allocation in a persistent initramfs hook | Keep Python 3 in roadmap. Adapt the loop allocation approach into a smaller image hook with attribution; do not copy the partition installer or provider abstraction. |',
'| [BellezaEmporium/rework](https://github.com/BellezaEmporium/wubiuefi/tree/rework) | Python 3/Nuitka/Tkinter and boot changes; release describes phase 2 as unfinished | Roadmap reference, not a verified replacement. |',
'| [aurelienjsureau/spike-loopboot-2604](https://github.com/aurelienjsureau/wubiuefi/tree/spike-loopboot-2604) | Ubuntu 26.04 loop boot and QEMU experiment | Future proof-of-concept input; no binaries or unverified boot recipes imported. |', '',
'## LliureX commits', '',
'Each row identifies the original purpose by its commit subject and affected paths. Decisions describe the selected Noble path, not deletion of historical source. `Replace` means its runtime behavior is superseded by the manifest/image transaction. Merge rows preserve ancestry.', '',
'| SHA | Original purpose | Affected behavior / paths | Decision |', '|---|---|---|---|']
for c in d['lliurex']['commits']:
    sha=c['sha']; title=c['commit']['message'].splitlines()[0]
    files=subprocess.check_output(['git','show','--format=','--name-only',sha],cwd=root,text=True).splitlines()
    files=sorted(set(f for f in files if f))
    joined=' '.join(files)
    if title.startswith('Merge'):
        decision='Preserve ancestry; no independent runtime behavior.'
    elif 'sig_enforce' in title:
        decision='Remove from active path: never disable signature enforcement.'
    elif any(x in joined for x in ('generate_','isolist','custom-installation','preseed')):
        decision='Replace LliureX-specific image/build settings with official Noble image and first-boot setup.'
    elif any(x in joined for x in ('backend','installation_page','downloader')):
        decision='Replace active image/download/boot behavior; retain reusable UI and platform utilities, with regression checks.'
    elif any(x in joined for x in ('Makefile','check_wine','pylauncher')):
        decision='Update supported build tooling; retain existing launcher.'
    elif any(x in joined for x in ('images','po/')):
        decision='Preserve artwork/translations and local icon bytes; fix filename case collision.'
    else:
        decision='Preserve history; update current release documentation/version separately.'
    lines.append('| `'+sha+'` | '+clean(title)+' | '+clean(', '.join(files) or 'Merge ancestry')+' | '+decision+' |')
lines += ['', '## Missing upstream commits', '', '| SHA | Purpose | Decision |', '|---|---|---|']
for c in d['missing']['commits']:
    lines.append('| `'+c['sha']+'` | '+clean(c['commit']['message'].splitlines()[0])+' | ISO version metadata is outside the Noble image path. Kernel enumeration fixes are superseded by package-maintained `/boot/vmlinuz` and `/boot/initrd.img` links. Preserve upstream reference; no wholesale cherry-pick. |')
lines += ['', '## Issues and pull requests', '',
'All '+str(len(d['issues']))+' captured open and closed records follow. Closed status alone does not establish a fix in this fork. Unless explicitly identified below, entries are roadmap/triage items and have not been reproduced. No blanket claim that every upstream issue is fixed.', '',
'New portable tests cover incomplete/corrupt downloads, cancellation cleanup, unsafe archive entries, insufficient disk size, invalid ownership records, and EFI/BCD cleanup failures. Actual Windows symptoms, Secure Boot behavior and kernel upgrade bootability remain unverified until the planned Windows validation.', '',
'| Item | State | Reported behavior | Classification / disposition |', '|---|---|---|---|']
for i in sorted(d['issues'], key=lambda i:i['number']):
    n=i['number'];title=i['title']; t=title.lower()
    if n in (341,342,345):
        status='Upstream repair reference; new boot path uses one loopw0 and current kernel symlinks. Hardware validation pending.'
    elif n in (347,351,356,365,367,369,336):
        status='In-scope regression target: manifest transport, safe disk selection or boot preflight. Original Windows report not yet reproduced.'
    elif any(x in t for x in ('32 bit','32-bit','arm64','windows 7','windows xp','bios','pop!','mint','kubuntu','lubuntu','xubuntu','26.04','25.10')):
        status='Outside v1 platform; roadmap where applicable.'
    else:
        status='Roadmap / triage; '+('closed upstream, fix applicability requires verification.' if i['state']=='closed' else 'unreproduced upstream report.')
    lines.append('| [#%s](%s) | %s%s | %s | %s |'%(n,i['html_url'],i['state'],' PR' if 'pull_request' in i else '',clean(title),status))
lines += ['', '## Fork inventory', '', '| Repository | Branches (head prefixes) | Releases | Latest CI |', '|---|---|---|---|']
for f in d['forks']:
    branches=', '.join(b['name']+' `'+b['commit']['sha'][:12]+'`' for b in f['branches'])
    releases=', '.join(r['tag_name'] for r in f['releases'])
    runs=', '.join(str(r['conclusion']) for r in f['runs'])
    lines.append('| [%s](https://github.com/%s) | %s | %s | %s |'%(f['repo'],f['repo'],clean(branches or str(f['error'] or 'No branches returned')),clean(releases or 'None returned'),clean(runs or 'None returned')))
(root/'UPSTREAM_AUDIT.md').write_text('\n'.join(lines)+'\n')
