import csv, io, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pytest
import pymupdf
from fastapi.testclient import TestClient
from analysis import ChartPlan, Filter, analyze, analyze_many, regression
from datasets import number, load_dataset, catalog

@pytest.mark.parametrize('value',['1-5','1; 2','< 3','~4','1,000','NaN','inf','','—','3 cm/s'])
def test_reject_ambiguous_numbers(value):
    assert number(value) is None

@pytest.mark.parametrize('value,expected',[(' 1.25 ',1.25),('-0.04',-.04),('2e-3',.002),('0',0)])
def test_exact_numbers(value,expected):assert number(value)==expected

def plan(dataset='flex',x='diameter',y='burn_time',kind='scatter',filters=None,group='fuel'):
    return ChartPlan(dataset=dataset,x=x,y=y,kind=kind,group=group,filters=filters or [],title='Test relationship')

def test_real_data_counts_and_nonindependence():
    assert catalog()['total_records']==1615
    assert catalog()['file_count']==22
    s=load_dataset('spice')
    assert len(s['rows'])==435 and s['quality']['ignition_clusters']==151
    assert s['quality']['duplicates_removed']==34
    c=load_dataset('cfi_inverse')
    assert len(c['rows'])==154 and c['quality']['empty_removed']==861

def test_regression_matches_independent_numpy_solution():
    x=np.arange(8);y=np.array([2,4,5,9,9,11,15,15])
    r=regression(x,y,list(map(str,range(8))))
    expected=np.polyfit(x,y,1)
    assert r['slope']==pytest.approx(expected[0])
    assert r['intercept']==pytest.approx(expected[1])
    assert all(a<=b for a,b in zip(r['lower'],r['upper']))
    assert r['range']==[0,7]

def test_duplicate_stages_do_not_count_as_independent_tests():
    assert not regression(range(12),range(12),['same ignition']*12)['available']
    assert not regression([1,1,2,2,2,2],range(6),list('abcdef'))['available']

def test_spice_splits_nozzle_panels():
    charts=analyze_many(plan('spice','airflow','fuel_flow'))
    assert len(charts)==3 and sum(c['n'] for c in charts)==415
    for c in charts:
        assert len({r['values']['diameter'] for r in c['rows']})==1
        assert len(c['stats'])<=6
        assert all('Fuel mixture' in s['group'] for s in c['stats'])

def test_matched_flex_comparison_reproduces_calculated_result():
    filters=[Filter(field=f,op=op,values=[v]) for f,op,v in [('oxygen','eq','.21'),('co2','eq','0'),('helium','eq','0'),('pressure','gte','740'),('pressure','lte','780')]]
    c=analyze(plan(filters=filters));assert c['n']==27
    s={s['group']:s for s in c['stats']}
    assert s['Fuel: Methanol']['n']==12
    assert s['Fuel: Methanol']['slope']==pytest.approx(10.07,abs=.01)
    assert s['Fuel: Heptane']['n']==15
    assert s['Fuel: Heptane']['r2']==pytest.approx(.157,abs=.001)

def test_extinction_diameter_excludes_other_test_endings():
    c=analyze(plan(y='extinction_diameter'))
    assert all(r['values']['outcome']=='Extinction' for r in c['rows'])
    assert 'droplet' in c['figure']['layout']['yaxis']['title']['text'].lower()

def test_cfi_burn_duration_ignition_and_termination_handling():
    c=analyze(plan('cfi_inverse','oxygen_flow','burn_time'))
    assert all(r['values']['ignition']=='yes' for r in c['rows'])
    assert all('Test termination:' in s['group'] for s in c['stats'])

def test_outcomes_not_regressed_or_unknown_as_negative():
    c=analyze(plan('cfi_normal','fuel','outcome','outcomes'))
    assert c['n']==133
    assert {t['name'] for t in c['figure']['data']}=={'Self-extinction','Flow terminated'}
    assert all(sum(t['y'][i] for t in c['figure']['data'])==pytest.approx(100) for i in range(len(c['figure']['data'][0]['x'])))
    assert all('slope' not in s for s in c['stats'])

def test_numeric_outcome_chart_keeps_fuels_separate():
    c=analyze(plan('cfi_normal','fuel_flow','outcome','outcomes'))
    assert all('Fuel mixture:' in x for x in c['figure']['data'][0]['x'])

def test_source_values_and_lines_are_preserved():
    c=analyze(plan())
    r=c['rows'][0]
    assert r['id']=='flex:r1' and r['line_start']==2
    assert r['cells'][10]=='1.69' and r['values']['diameter']==1.69
    assert 10 in c['highlight_columns'] and 13 in c['highlight_columns']

def test_unknown_fields_cannot_execute_code():
    with pytest.raises(ValueError):analyze(plan(x="__import__('os').system('false')"))

def test_zero_results_fails_clearly():
    with pytest.raises(ValueError,match='no usable paired'):
        analyze(plan(filters=[Filter(field='fuel',op='eq',values=['invented fuel'])]))

def test_pdf_highlight_is_real_annotation():
    from evidence import search_evidence, highlighted_pdf
    results=search_evidence('How does airflow affect flame spread in microgravity?')
    assert any(p['paper']=='20205004657' and p['page']==5 for p in results)
    p=results[0]
    raw=highlighted_pdf(p['id'])
    with pymupdf.open(stream=raw,filetype='pdf') as doc:
        assert any(a.type[1]=='Highlight' for a in doc[p['page']-1].annots())

def test_ocr_source_highlights_all_cited_lines():
    from evidence import get_passage,highlighted_pdf
    p=get_passage('20120016855:p5:b5')
    assert len(p['line_rects'])>=8
    with pymupdf.open(stream=highlighted_pdf(p['id']),filetype='pdf') as doc:
        page=doc[p['page']-1]
        annotation=next(page.annots())
        assert len(annotation.vertices)==4*len(p['line_rects'])

def test_http_security_and_source_export():
    from server import app,TOKEN,jobs,local_comparison
    client=TestClient(app)
    assert client.post('/api/ask',json={'question':'x'}).status_code==403
    cat=client.get('/api/catalog').json()
    assert 'api_key' not in cat and cat['token']==TOKEN
    r=local_comparison(plan(),'comparison')
    jobs['test-export']={'status':'done','result':r}
    c=r['charts'][0]
    response=client.get('/api/export/test-export/'+c['id'])
    rows=list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert len(rows)==c['n']+1 and rows[1][0]=='flex:r1'
    assert client.get('/api/original/unknown.csv').status_code==404
    del jobs['test-export']

def test_cached_scientific_text_survives_windows_encoding(tmp_path,monkeypatch):
    """A UTF-8 cache must not be decoded with the Windows cp1252 default."""
    import assistant
    from server import app,jobs
    text='CO₂ · R² = 0.977; t = −13.783 + 10.074D; 1.61–3.89 mm; methanol’s fit'
    monkeypatch.setattr(assistant,'CACHE',tmp_path/'cache')
    monkeypatch.setattr(assistant,'fingerprint',lambda:'encoding-test')
    monkeypatch.setattr(assistant,'catalog',lambda:dict(datasets=[],originals=[]))
    monkeypatch.setattr(assistant,'search_evidence',lambda question:[])
    def fake_request(schema,instructions,payload):
        if schema is assistant.Plan:
            return schema(scope=text,missing=[],charts=[])
        return schema(introduction=text,conclusion='**'+text+'**',captions=[],evidence_ids=[])
    monkeypatch.setattr(assistant,'request',fake_request)
    original=assistant.answer('Compare diameter and duration')
    read_text=Path.read_text
    def windows_read_text(path,encoding=None,errors=None):
        return read_text(path,encoding=encoding or 'cp1252',errors=errors)
    monkeypatch.setattr(Path,'read_text',windows_read_text)
    monkeypatch.setattr(assistant,'request',lambda *args:pytest.fail('Cache hit must not call the API'))
    cached=assistant.answer('Compare diameter and duration')
    assert cached['cached'] is True
    for field in ('scope','introduction','conclusion'):
        assert cached[field]==original[field]
    monkeypatch.setitem(jobs,'encoding-test',dict(status='done',result=cached))
    client=TestClient(app)
    response=client.get('/api/jobs/encoding-test')
    assert response.json()['result']['introduction']==text
    report=client.get('/api/report/encoding-test')
    assert json.loads(report.content.decode('utf-8'))['introduction']==text
