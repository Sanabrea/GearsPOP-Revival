"""Dump content pages (ns 0) from a MediaWiki XML export (sources/wikis/*.xml) to one .txt per page,
ranked by stat-like words. Usage: wiki_extract.py EXPORT_XML OUT_DIR TAG
"""
import sys,re,os,xml.etree.ElementTree as ET
src,outdir,tag=sys.argv[1],sys.argv[2],sys.argv[3]
ns={'m':'http://www.mediawiki.org/xml/export-0.11/'}
tree=ET.parse(src); root=tree.getroot()
nsuri=root.tag.split('}')[0]+'}'
rows=[]
for page in root.iter(nsuri+'page'):
    title=page.find(nsuri+'title').text
    nsid=page.find(nsuri+'ns').text
    if nsid!='0': continue
    revs=page.findall(nsuri+'revision')
    last=revs[-1]
    text=(last.find(nsuri+'text').text or '')
    ts=last.find(nsuri+'timestamp').text
    stat=len(re.findall(r'(?i)\b(health|hp|damage|dps|speed|range|cost|energy|attack|hit|level|rarity)\b',text))
    nums=len(re.findall(r'\b\d+(\.\d+)?\b',text))
    rows.append((stat,nums,len(text),title,ts))
    fn=re.sub(r'[^A-Za-z0-9_.-]+','_',title)[:80]
    open(os.path.join(outdir,f"{tag}__{fn}.txt"),'w').write(text)
rows.sort(reverse=True)
print(f"{tag}: {len(rows)} content pages")
for r in rows[:45]: print(f"  stat_words={r[0]:3d} nums={r[1]:4d} chars={r[2]:6d} | {r[3]} | {r[4][:10]}")
