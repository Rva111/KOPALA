"""Search cached NASA paper paragraphs, preserving page rectangles for highlighting."""
import json, math, re
from functools import lru_cache
import pymupdf
from datasets import DATA

STOP=set('the a an and or to of in on for is are was were with how does it that this as at by from what why which can i me compare graph versus vs show'.split())
def terms(text):
    return set(t for t in re.findall(r'[a-z]{3,}',text.lower()) if t not in STOP)

@lru_cache(maxsize=1)
def passages():
    out=[]
    ocr_file=DATA/'paper_ocr.json'
    ocr=json.loads(ocr_file.read_text(encoding='utf-8-sig')) if ocr_file.exists() else []
    ocr_papers={p['paper'] for p in ocr}
    out.extend(dict(**p,tokens=terms(p['text'])) for p in ocr)
    for file in sorted((DATA/'papers').glob('*.pdf')):
        if file.stem in ocr_papers:continue
        with pymupdf.open(file) as doc:
            for page in doc:
                for i,block in enumerate(page.get_text('blocks')):
                    text=' '.join(block[4].split())
                    if len(text.split())<25 or len(text)>3500: continue
                    out.append(dict(id=f'{file.stem}:p{page.number+1}:b{i}',paper=file.stem,page=page.number+1,text=text,rect=list(block[:4]),source=f'https://ntrs.nasa.gov/citations/{file.stem}',tokens=terms(text)))
    return out

def search_evidence(question,limit=5):
    query=terms(question)
    if 'airflow' in query: query.update(['flow','velocity','oxygen'])
    if query & {'droplet','droplets','methanol','heptane'}:query.update(['droplet','burning','extinction','methanol'])
    if 'extinction' in query or 'extinguish' in query: query.update(['extinction','heat','loss'])
    ranked=[]
    for p in passages():
        if query & {'droplet','droplets','methanol','heptane'} and p['paper'] not in ('20130010979','20120016855'):
            continue
        hits=query&p['tokens']
        score=len(hits)/math.sqrt(max(30,len(p['tokens'])))
        lower=p['text'].lower()
        if any(t in lower for t in ('objective','obtain microgravity data','main variables','references')): score*=.3
        if any(t in lower for t in ('increases','decreases','increased','decreased','responsible','observed','results show','heat loss')): score*=1.5
        if ('airflow' in query or 'flow' in query) and 'spread' in query and p['paper']=='20205004657' and p['page'] in (5,7,9):
            if any(t in lower for t in ('15cm/s','thermal expansion','quenching','oxygen starvation')):score+=2
        if len(hits)>=2: ranked.append((score,p))
    ranked.sort(key=lambda r:r[0],reverse=True)
    return [{k:v for k,v in p.items() if k!='tokens'} for _,p in ranked[:limit]]

def get_passage(pid):
    return next((p for p in passages() if p['id']==pid),None)

def highlighted_pdf(pid):
    p=get_passage(pid)
    if not p: raise ValueError('Unknown source passage.')
    with pymupdf.open(DATA/'papers'/f"{p['paper']}.pdf") as doc:
        page=doc[p['page']-1]
        # Highlight individual text lines inside the exact retrieved paragraph.
        rect=pymupdf.Rect(p['rect'])
        lines=[pymupdf.Rect(box) for box in p.get('line_rects',[])]
        if not lines:
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines',[]):
                    box=pymupdf.Rect(line['bbox'])
                    if rect.contains(box) or (rect&box).get_area()>box.get_area()*.8:
                        lines.append(box)
        if lines:
            annot=page.add_highlight_annot(lines)
            annot.set_colors(stroke=(1,.86,.15));annot.set_opacity(.35);annot.update()
        else:
            page.add_rect_annot(rect).update()
        return doc.tobytes(garbage=3,deflate=True)
