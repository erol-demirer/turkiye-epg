#!/usr/bin/env python3
"""Run upstream IPTV-ORG scraper individually per Turkish site; never fail the whole guide."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / '_upstream_epg'
OUT = ROOT / 'generated' / 'iptv-org'
SITES = ('tvplus.com.tr', 'digiturk.com.tr', 'dsmart.com.tr', 'turksatkablo.com.tr')


def collect(repo=UPSTREAM, output=OUT, runner=subprocess.run, proxy=None):
    output.mkdir(parents=True, exist_ok=True)
    # Never reuse stale generated site feeds from a previous run.
    for site in SITES:
        (output / (site + '.xml')).unlink(missing_ok=True)
    results = []
    for site in SITES:
        dest = output / (site + '.xml')
        cmd = ['npm', 'run', 'grab', '---', '--sites=' + site, '--days=3',
               '--maxConnections=2', '--timeout=20000', '--output=' + str(dest)]
        if proxy:
            cmd.append('--proxy=' + proxy)
        try:
            done = runner(cmd, cwd=repo, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=270, check=False)
            if done.returncode != 0:
                raise RuntimeError('grab command exit code ' + str(done.returncode))
            if not dest.is_file() or dest.stat().st_size < 80:
                raise RuntimeError('no XMLTV produced')
            tree = ET.parse(dest)
            root = tree.getroot()
            if root.tag != 'tv':
                raise RuntimeError('not an XMLTV document')
            programs = sum(1 for p in root.findall('programme') if p.findtext('title') and p.findtext('title').strip().casefold() not in ('no data', 'no information'))
            if not programs:
                raise RuntimeError('no usable programme entries')
            results.append({'site':site,'ok':True,'programmes':programs,'bytes':dest.stat().st_size})
            print(f'[OK] {site}: {programs} programmes', flush=True)
        except (OSError, subprocess.TimeoutExpired, RuntimeError, ET.ParseError) as e:
            dest.unlink(missing_ok=True)
            # The proxy URL may contain credentials; never print it or subprocess output.
            results.append({'site':site,'ok':False,'error':type(e).__name__ if proxy else str(e)[:160]})
            print(f'[FAIL] {site}: {type(e).__name__}', flush=True)
    report={'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'sites':results,
            'proxy_enabled':bool(proxy)}
    (output/'collection.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    return report


if __name__=='__main__':
    collect(proxy=os.environ.get('TR_EPG_PROXY') or None)
