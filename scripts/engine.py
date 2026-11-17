#!/usr/bin/env python3
"""Merge public XMLTV guides into an Xtream-friendly Turkish guide (stdlib only)."""
import argparse, collections, copy, csv, datetime as dt, gzip, hashlib, json, logging, re, sys, unicodedata, urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
LOG = logging.getLogger('epg')
MAX_BYTES = 90_000_000
USER_AGENT = 'TurkeyEPGAggregator/1.0 (personal-use; XMLTV)'


def norm(s):
    s = (s or '').casefold().replace('ı','i').replace('i̇','i')
    s = unicodedata.normalize('NFKD',s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'^(tr|turkiye|turkey|yerel)\s*[:|\-]\s*','',s)
    s = re.sub(r'\b(uhd|fhd|full\s*hd|hd|4k|8k|hevc|h265|h264|sd|raw|backup|yedek|fps|1080p?|720p?|576p?)\b',' ',s)
    s = re.sub(r'\b(\d{2,4})\s*(fps|p)\b',' ',s)
    s = re.sub(r'[^a-z0-9]+',' ',s)
    return ' '.join(s.split())


def parse_date(s):
    if not s: return None
    m = re.match(r'^(\d{14}|\d{12}|\d{8})(?:\s*([+-]\d{4}|Z))?',s.strip())
    if not m: return None
    stamp,z = m.groups()
    fmt = {14:'%Y%m%d%H%M%S',12:'%Y%m%d%H%M',8:'%Y%m%d'}[len(stamp)]
    d = dt.datetime.strptime(stamp,fmt)
    if z and z != 'Z':
        sign=1 if z[0]=='+' else -1
        off=dt.timedelta(hours=int(z[1:3]), minutes=int(z[3:])) * sign
        tz=dt.timezone(off)
    else: tz=UTC
    return d.replace(tzinfo=tz).astimezone(UTC)


def read_xml(raw):
    if len(raw)>MAX_BYTES: raise ValueError('XMLTV file too large')
    if raw[:2] == b'\x1f\x8b': raw=gzip.decompress(raw)
    if len(raw)>MAX_BYTES: raise ValueError('XMLTV decompressed file too large')
    # Do not permit embedded DTD/entity declarations in downloaded feeds.
    if re.search(rb'<!\s*(DOCTYPE|ENTITY)\b', raw[:8192], flags=re.I):
        raw=re.sub(rb'<!DOCTYPE\s+tv\s+SYSTEM\s+["\'][^"\']+["\']\s*>',b'',raw,count=1, flags=re.I)
    if re.search(rb'<!\s*(DOCTYPE|ENTITY)\b',raw[:8192],re.I): raise ValueError('DTD/entities not allowed')
    return ET.fromstring(raw)


def fetch(url):
    if not url.startswith('https://'): raise ValueError('Only HTTPS remote sources supported')
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':USER_AGENT}),timeout=50) as r:
        raw=r.read(MAX_BYTES+1)
    return read_xml(raw)


def load_targets(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    return data['channels']


def index_source(root):
    channels={}
    for c in root.findall('channel'):
        cid=c.get('id')
        if not cid: continue
        names=[x.text.strip() for x in c.findall('display-name') if x.text]
        names.append(cid.split('@')[0].rsplit('.',1)[0].replace('.',' '))
        channels.setdefault(cid,[])
        channels[cid].extend(names)
    programs=collections.defaultdict(list)
    for p in root.findall('programme'):
        cid=p.get('channel')
        start=parse_date(p.get('start')); stop=parse_date(p.get('stop'))
        if cid and start and stop and stop>start: programs[cid].append((start,stop,p))
    return channels,programs


def match(target, channels, overrides, programs=None):
    """Find the best usable channel. Never let an empty exact ID hide a populated alias."""
    tid=target['id']
    override=overrides.get(tid)
    options=[]
    if override:
        for v in (override if isinstance(override,list) else [override]):
            if v in channels: options.append((v,'override'))
    if tid in channels: options.append((tid,'exact-id'))
    tnames={norm(tid), *(norm(x) for x in target['names'])}
    for n in list(tnames):
        if n.endswith(' tr'): tnames.add(n[:-3])
    tnames.discard('')
    matches=[]
    for cid,names in channels.items():
        if cid==tid:continue
        cnames={norm(cid.split('@')[0]),*(norm(n) for n in names)}
        for n in list(cnames):
            if n.endswith(' tr'):cnames.add(n[:-3])
        if tnames & cnames: matches.append(cid)
    if len(matches)==1:options.append((matches[0],'exact-name'))
    elif len(matches)>1:
        stems={norm(x.split('@')[0]) for x in matches}
        if len(stems)==1:
            for cid in sorted(matches,key=lambda x:('@HD' not in x,'@SD' not in x,x)):
                options.append((cid,'variant'))
        else:
            # Multiple distinct IDs matched an alias. Don't guess without overrides.
            return (None,'ambiguous') if not options else _pick(options,programs)
    return _pick(options,programs) if options else (None,'missing')


def _pick(options,programs):
    # Explicit source mapping beats inferred names if it has programmes.
    for cid,kind in options:
        if programs is None or programs.get(cid): return cid,kind
    return options[0][0], 'matched-without-programmes'


def sources_config(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--targets',default=str(ROOT/'config/targets.json'))
    ap.add_argument('--sources',default=str(ROOT/'config/sources.json'))
    ap.add_argument('--overrides',default=str(ROOT/'config/overrides.json'))
    ap.add_argument('--out',default=str(ROOT/'public'))
    ap.add_argument('--offline-xml',help='Use local XMLTV as the only source (for testing)')
    ap.add_argument('--min-programmes',type=int,default=1)
    args=ap.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    targets=load_targets(args.targets)
    overrides=json.loads(Path(args.overrides).read_text(encoding='utf-8'))
    sources=([{'name':'local-test','path':args.offline_xml}] if args.offline_xml else sources_config(args.sources)['sources'])
    now=dt.datetime.now(UTC)
    start_limit=now-dt.timedelta(hours=5)
    end_limit=now+dt.timedelta(days=8)
    output=ET.Element('tv',{'generator-info-name':'TurkeyEPGAggregator'})
    report=[]; all_progs=collections.defaultdict(list); statuses=[]
    # We create one channel element for each unique nonempty ID, preserving Xtream identity.
    for t in targets:
        c=ET.SubElement(output,'channel',{'id':t['id']})
        ET.SubElement(c,'display-name').text=t['names'][0]
    for pri,src in enumerate(sources):
        try:
            root=read_xml(Path(src['path']).read_bytes()) if 'path' in src else fetch(src['url'])
            channel_idx,progs=index_source(root)
            matched=0
            for t in targets:
                source_id,kind=match(t,channel_idx,overrides.get(src['name'],{}),progs)
                if source_id and progs.get(source_id):
                    matched+=1
                    for st,ed,p in progs[source_id]:
                        if ed<=start_limit or st>=end_limit:continue
                        all_progs[t['id']].append((st,ed,pri,copy.deepcopy(p),src['name']))
                report.append({'target_id':t['id'],'target_name':t['names'][0], 'source':src['name'], 'matched_source_id':source_id or '', 'match_type':kind,'programme_count':len(progs.get(source_id,[])) if source_id else 0, 'current_programmes':sum(1 for st,ed,_ in progs.get(source_id,[]) if ed>now and st<now+dt.timedelta(hours=24)) if source_id else 0})
            statuses.append({'source':src['name'],'ok':True,'channels':len(channel_idx),'programmed_channels':len(progs),'matched_targets':matched})
            LOG.info('%s: %d channel IDs, matched %d targets',src['name'],len(channel_idx),matched)
        except Exception as e:
            statuses.append({'source':src['name'],'ok':False,'error':str(e)[:300]})
            LOG.warning('%s unavailable: %s',src['name'],e)
    retained=0; filled=0; coverage={}
    for t in targets:
        cid=t['id']; entries=sorted(all_progs[cid],key=lambda x:(x[2],x[0]))
        accepted=[]
        for st,ed,priority,p,sname in entries:
            # Higher priority wins on overlap. Lower priority can fill genuine gaps.
            if any(st<a_ed and ed>a_st for a_st,a_ed,*_ in accepted):continue
            title=p.findtext('title')
            if not title or not title.strip():continue
            p.set('channel',cid)
            accepted.append((st,ed,p,sname))
        accepted.sort(key=lambda x:x[0])
        if accepted:filled+=1
        coverage[cid]={'programmes':len(accepted),'next_24h':sum(1 for st,ed,*_ in accepted if ed>now and st<now+dt.timedelta(hours=24)), 'next_48h':sum(1 for st,ed,*_ in accepted if ed>now and st<now+dt.timedelta(hours=48)), 'sources':sorted({x[3] for x in accepted})}
        for st,ed,p,sname in accepted:
            output.append(p);retained+=1
    stat={'generated_at_utc':now.isoformat(),'total_target_ids':len(targets),'target_ids_with_programmes':filled,'programme_count':retained,'sources':statuses,'coverage':coverage}
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    # If all sources failed, or guide is empty, do not overwrite last good guide.
    if retained < args.min_programmes:
        (out/'last_attempt.json').write_text(json.dumps(stat,ensure_ascii=False,indent=2),encoding='utf-8')
        LOG.error('No usable programmes; existing guide preserved')
        return 2
    data=ET.tostring(output,encoding='utf-8',xml_declaration=True)
    (out/'epg.xml').write_bytes(data)
    with gzip.open(out/'epg.xml.gz','wb',compresslevel=9) as f:f.write(data)
    (out/'status.json').write_text(json.dumps(stat,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'matches.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['target_id','target_name','source','matched_source_id','match_type','programme_count','current_programmes']); writer.writeheader();writer.writerows(report)
    LOG.info('Success: %d programmes across %d/%d target IDs',retained,filled,len(targets))
    return 0

if __name__=='__main__':sys.exit(main())
