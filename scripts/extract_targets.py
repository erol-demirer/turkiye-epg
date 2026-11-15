#!/usr/bin/env python3
"""Export only safe channel metadata from M3U: NEVER export stream URLs or credentials."""
import argparse,collections,json,re
from pathlib import Path

def extract(src):
    channels=collections.OrderedDict(); missing=[]; counts=collections.Counter()
    # A playlist may be huge; streaming parse avoids exposing or storing stream URLs.
    with Path(src).open('r',encoding='utf-8-sig',errors='replace') as f:
        for line in f:
            if not line.startswith('#EXTINF:'): continue
            name=line.rstrip('\n').rsplit(',',1)[-1].strip()
            grp=re.search(r'group-title="([^"]*)"',line)
            group=grp.group(1) if grp else ''
            # Only channels explicitly prefixed TR: or categorized as Turkish live channels.
            if not name.upper().startswith('TR:'):continue
            m=re.search(r'tvg-id="([^"]*)"',line)
            cid=m.group(1).strip() if m else ''
            counts['tv_entries']+=1
            if not cid:
                missing.append({'name':name,'group':group});continue
            if cid not in channels: channels[cid]={'id':cid,'names':[]}
            if name not in channels[cid]['names']:channels[cid]['names'].append(name)
    return {'channels':list(channels.values())},missing,dict(counts)

def main():
    a=argparse.ArgumentParser();a.add_argument('m3u');a.add_argument('--out',default='config/targets.json');a.add_argument('--missing-out',default='config/unnamed_channels.json');x=a.parse_args()
    targets,missing,stats=extract(x.m3u)
    for path,data in ((x.out,targets),(x.missing_out,missing)):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"TR entries: {stats['tv_entries']}; distinct nonempty IDs: {len(targets['channels'])}; empty IDs: {len(missing)}")
if __name__=='__main__':main()
