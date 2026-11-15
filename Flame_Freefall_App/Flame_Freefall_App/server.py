import csv, io, json, os, secrets, threading, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from analysis import ChartPlan, analyze_many
from assistant import MODEL, api_key, answer
from datasets import ROOT, DATA, catalog
from evidence import get_passage, highlighted_pdf

app=FastAPI(docs_url=None,redoc_url=None)
TOKEN=secrets.token_urlsafe(24)
jobs={}; pool=ThreadPoolExecutor(max_workers=2); lock=threading.Lock()

class Ask(BaseModel):
    question: str = Field(min_length=1,max_length=4000)
    history: list[dict] = Field(default_factory=list,max_length=4)
    direct: ChartPlan | None = None
    explain: bool = True
    fresh: bool = False

@app.middleware('http')
async def local_guard(request:Request,call_next):
    if request.method=='POST' and request.headers.get('x-flame-token')!=TOKEN:
        return Response('Reload the app before submitting.',status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    return response

@app.get('/api/catalog')
def get_catalog():
    try: api_key();ready=True
    except RuntimeError:ready=False
    return dict(**catalog(),model=MODEL,api_ready=ready,token=TOKEN)

def local_comparison(direct,question):
    charts=analyze_many(direct)
    outcomes=direct.kind=='outcomes'
    introduction='Bars show the share of each reported outcome; hover to see counts and denominators. Different fuels remain separate.' if outcomes else 'Each point is a source record. Separate fits keep the selected fuels and relevant geometry groups apart.'
    conclusion='**These are observed outcome shares, not controlled extinction probabilities.** Flow-terminated tests are stopped by an intervention. Missing outcomes are excluded and reported in the conditions panel.' if outcomes else 'The fitted line describes the selected records. **An association does not establish causation.** Use the experiment conditions and source rows below before comparing slopes across fuels.'
    return dict(question=question,scope='Comparison calculated directly from the cached NASA CSV.',introduction=introduction,conclusion=conclusion,charts=charts,evidence=[],missing=[],errors=[],model='Local Python analysis',cached=False,api_calls=0)

def run_job(job_id,body):
    def progress(message):
        with lock:jobs[job_id]['progress']=message
    try:
        if body.direct and not body.explain: result=local_comparison(body.direct,body.question)
        else: result=answer(body.question,body.history,body.direct.model_dump() if body.direct else None,progress,body.fresh)
        with lock:jobs[job_id].update(status='done',result=result,progress='Complete')
    except (ValueError,RuntimeError) as error:
        with lock:jobs[job_id].update(status='error',error=str(error),progress='Stopped')
    except Exception:
        with lock:jobs[job_id].update(status='error',error='The analysis could not complete. Check your selected data and retry; no old answer has been reused.',progress='Stopped')

@app.post('/api/ask')
def ask(body:Ask):
    with lock:
        if sum(j['status']=='running' for j in jobs.values())>=2:raise HTTPException(429,'An analysis is already running. Please wait.')
        jid=uuid.uuid4().hex
        if len(jobs)>60:
            for key in list(jobs):
                if jobs[key]['status']!='running':del jobs[key];break
        jobs[jid]=dict(status='running',progress='Starting analysis…')
    pool.submit(run_job,jid,body)
    return dict(job_id=jid)

@app.get('/api/jobs/{job_id}')
def job(job_id:str):
    if job_id not in jobs:raise HTTPException(404,'Analysis not found.')
    return jobs[job_id]

def get_chart(job_id,chart_id):
    job=jobs.get(job_id,{})
    chart=next((c for c in job.get('result',{}).get('charts',[]) if c['id']==chart_id),None)
    if chart is None:raise HTTPException(404,'Chart not found. Run the question again.')
    return chart

@app.get('/api/export/{job_id}/{chart_id}')
def export(job_id:str,chart_id:str):
    c=get_chart(job_id,chart_id)
    out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(['Source record','Original CSV record','Physical line start','Physical line end']+c['headers'])
    for row in c['rows']:writer.writerow([row['id'],row['row'],row['line_start'],row['line_end']]+row['cells'])
    return Response(out.getvalue().encode('utf-8-sig'),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{chart_id}_source_rows.csv"'})

@app.get('/api/report/{job_id}')
def report(job_id:str):
    j=jobs.get(job_id,{})
    if j.get('status')!='done':raise HTTPException(404,'Completed analysis not found.')
    data=json.dumps(j['result'],ensure_ascii=False,indent=2)
    return Response(data,media_type='application/json',headers={'Content-Disposition':'attachment; filename="flame_analysis.json"'})

@app.get('/api/original/{filename}')
def original(filename:str):
    allowed={f['filename'] for f in catalog()['originals']}
    if filename not in allowed:raise HTTPException(404,'Original file not found.')
    return FileResponse(DATA/'originals'/filename,filename=filename,media_type='text/csv')

@app.get('/api/evidence/{pid}')
def evidence(pid:str):
    p=get_passage(pid)
    if not p:raise HTTPException(404,'Passage not found.')
    return {k:v for k,v in p.items() if k!='tokens'}

@app.get('/api/evidence/{pid}/highlighted.pdf')
def pdf(pid:str):
    try:data=highlighted_pdf(pid)
    except ValueError:raise HTTPException(404,'Passage not found.')
    return Response(data,media_type='application/pdf',headers={'Content-Disposition':f'inline; filename="{pid.replace(":","_")}_highlighted.pdf"'})

app.mount('/',StaticFiles(directory=ROOT/'web',html=True),name='web')

if __name__=='__main__':
    import argparse
    import uvicorn
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default=os.getenv('FLAME_HOST','127.0.0.1'))
    parser.add_argument('--port',type=int,default=int(os.getenv('PORT','8765')))
    args,_=parser.parse_known_args()
    uvicorn.run('server:app',host=args.host,port=args.port,access_log=False)
