import re,sys,json,urllib.request,urllib.parse
seen=set()
for q in sys.argv[1:]:
    url="https://www.youtube.com/results?search_query="+urllib.parse.quote(q)
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"en-US"})
    t=urllib.request.urlopen(req,timeout=30).read().decode("utf-8","replace")
    m=re.search(r"var ytInitialData = (\{.*?\});</script>",t,re.S)
    if not m: print("no data for",q); continue
    d=json.loads(m.group(1))
    out=[]
    def walk(o):
        if isinstance(o,dict):
            if "videoRenderer" in o:
                v=o["videoRenderer"]
                vid=v.get("videoId")
                title="".join(r.get("text","") for r in v.get("title",{}).get("runs",[]))
                ch="".join(r.get("text","") for r in v.get("ownerText",{}).get("runs",[]))
                dur=v.get("lengthText",{}).get("simpleText","")
                pub=v.get("publishedTimeText",{}).get("simpleText","")
                views=v.get("viewCountText",{}).get("simpleText","")
                out.append((vid,title,ch,dur,pub,views))
            for x in o.values(): walk(x)
        elif isinstance(o,list):
            for x in o: walk(x)
    walk(d)
    print("=== "+q)
    for vid,title,ch,dur,pub,views in out[:12]:
        if vid in seen: continue
        seen.add(vid)
        print(f"  {vid} | {title[:80]} | {ch} | {dur} | {pub} | {views}")
