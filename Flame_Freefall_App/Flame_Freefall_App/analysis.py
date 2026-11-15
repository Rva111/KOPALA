"""Deterministic, auditable statistics. The model supplies a plan, never executable code."""
import hashlib, json
import math
from typing import Literal
import numpy as np
from scipy.stats import t as student_t
from pydantic import BaseModel, Field
from datasets import load_dataset

class Filter(BaseModel):
    field: str
    op: Literal['eq','in','gte','lte']
    values: list[str]

class ChartPlan(BaseModel):
    dataset: str
    x: str
    y: str
    group: str
    kind: Literal['scatter','outcomes']
    filters: list[Filter]
    title: str

class Plan(BaseModel):
    scope: str
    missing: list[str]
    charts: list[ChartPlan] = Field(max_length=6)

COLORS=['#171717','#2563a0','#b65c35','#608466','#8a6095','#8c741c','#4a8d99','#a74965','#777777','#345344','#5c4f83','#986d59']

def label(field):
    return field['label'] + (f" ({field['unit']})" if field['unit'] else '')

def matches(row, filters, fields):
    for f in filters:
        value=row['values'][f.field]
        wanted=f.values
        if value is None: return False
        if fields[f.field]['kind']=='number':
            try: wanted=[float(v) for v in wanted]
            except ValueError: raise ValueError('Numeric filters need exact numbers.') from None
            if not all(math.isfinite(v) for v in wanted):raise ValueError('Numeric filters must be finite.')
        if f.op=='eq' and value!=wanted[0]: return False
        if f.op=='in' and value not in wanted: return False
        if f.op=='gte' and value<wanted[0]: return False
        if f.op=='lte' and value>wanted[0]: return False
    return True

def regression(x,y,clusters):
    """OLS point estimate + cluster-robust mean-response confidence band (CR1)."""
    x,y=np.asarray(x,float),np.asarray(y,float)
    n=len(x); g=len(set(clusters)); distinct=len(np.unique(x))
    if n<5 or distinct<3 or g<5:
        return dict(available=False,reason='A fit needs ≥5 records, ≥5 independent test groups and ≥3 distinct x values.',n=n,clusters=g)
    X=np.column_stack([np.ones(n),x])
    if np.linalg.matrix_rank(X)<2: return dict(available=False,reason='The x values have no usable variation.',n=n,clusters=g)
    inv=np.linalg.inv(X.T@X)
    beta=inv@X.T@y; resid=y-X@beta
    meat=np.zeros((2,2))
    clusters=np.asarray(clusters)
    for cluster in np.unique(clusters):
        m=clusters==cluster; score=X[m].T@resid[m]
        meat+=np.outer(score,score)
    cov=(g/(g-1))*((n-1)/(n-2))*(inv@meat@inv)
    grid=np.linspace(float(x.min()),float(x.max()),80)
    G=np.column_stack([np.ones(len(grid)),grid]); pred=G@beta
    se=np.sqrt(np.maximum(0,np.einsum('ij,jk,ik->i',G,cov,G)))
    crit=float(student_t.ppf(.975,g-1)); ss=float(((y-y.mean())**2).sum())
    r2=float(1-(resid@resid)/ss) if ss>1e-20 else None
    slope_se=float(np.sqrt(max(0,cov[1,1])))
    return dict(available=True,n=n,clusters=g,intercept=float(beta[0]),slope=float(beta[1]),r2=r2,slope_ci=[float(beta[1]-crit*slope_se),float(beta[1]+crit*slope_se)],x=grid.tolist(),y=pred.tolist(),lower=(pred-crit*se).tolist(),upper=(pred+crit*se).tolist(),range=[float(x.min()),float(x.max())],method='OLS; 95% cluster-robust confidence band for the fitted mean. Repeated records cluster by ignition in SPICE, identifier/date/time in FLEX and day/test in CFI-G; other tables use CSV record. This is not a causal effect or a prediction interval.')

def validate(plan, d):
    fields=d['fields']
    needed=[plan.x,plan.y]+([plan.group] if plan.group else [])
    if any(f not in fields for f in needed): raise ValueError('Requested field is not available in this dataset.')
    for f in plan.filters:
        if f.field not in fields or not f.values or len(f.values)>100: raise ValueError('Invalid comparison filter.')
        if f.op in ('gte','lte') and fields[f.field]['kind']!='number': raise ValueError('Range filters require numeric columns.')
    if plan.kind=='scatter' and any(fields[f]['kind']!='number' for f in (plan.x,plan.y)):
        raise ValueError('Regression requires two numeric measurements/settings.')
    if plan.kind=='outcomes' and fields[plan.y]['kind']!='category': raise ValueError('Outcome charts need a categorical outcome.')
    if plan.group and fields[plan.group]['kind']!='category': raise ValueError('Choose a categorical comparison field such as fuel.')

def layout(title,xlabel,ylabel):
    return dict(title=dict(text=title,font=dict(size=16)),paper_bgcolor='white',plot_bgcolor='white',font=dict(family='Arial, sans-serif',size=12,color='#202020'), margin=dict(l=75,r=25,t=55,b=85),height=440,hovermode='closest',legend=dict(orientation='h',y=-.23,x=0,font=dict(size=11)),xaxis=dict(title=dict(text=xlabel,standoff=14),gridcolor='#eeeeee',zeroline=False),yaxis=dict(title=dict(text=ylabel,standoff=12),gridcolor='#eeeeee',zeroline=False),dragmode='zoom')

def analyze(plan: ChartPlan):
    d=load_dataset(plan.dataset); validate(plan,d)
    fields=d['fields']; rows=[r for r in d['rows'] if matches(r,plan.filters,fields)]
    filtered_count=len(rows)
    warnings=[d['note']]
    automatic=[]
    if plan.dataset.startswith('cfi_') and 'burn_time' in (plan.x,plan.y):
        before=len(rows); rows=[r for r in rows if r['values'].get('ignition')=='yes']
        automatic.append(f'Only confirmed hot ignitions included; {before-len(rows)} other records excluded.')
    if plan.dataset=='flex' and 'extinction_diameter' in (plan.x,plan.y):
        before=len(rows); rows=[r for r in rows if r['values'].get('outcome')=='Extinction']
        automatic.append(f'Only tests ending in Extinction included; {before-len(rows)} completion/disruption records excluded.')
    valid=[r for r in rows if all(r['values'][f] is not None and r['values'][f]!='Unreported' for f in (plan.x,plan.y))]
    missing_count=len(rows)-len(valid)
    if not valid: raise ValueError(f"{d['name']}: no usable paired records after these filters. Change filters or select another relationship.")
    group_fields=[]
    if plan.group: group_fields.append(plan.group)
    # Avoid silent pooling of different fuels/diameters/termination mechanisms.
    for field in (['fuel','diameter'] if plan.dataset=='spice' else ['fuel','restrictor'] if plan.dataset=='bass2' else ['fuel','outcome'] if plan.dataset.startswith('cfi_') and 'burn_time' in (plan.x,plan.y) else ['fuel']):
        if field in fields and field not in (plan.x,plan.y) and field not in group_fields: group_fields.append(field)
    groups={}
    for row in valid:
        key=' · '.join(f"{fields[f]['label']}: {row['values'][f]}{(' '+fields[f]['unit']) if fields[f]['unit'] else ''}" for f in group_fields) or 'All selected records'
        groups.setdefault(key,[]).append(row)
    controls={}
    for f in d['controls']:
        if f in (plan.x,plan.y): continue
        vals=[r['values'][f] for r in valid if r['values'][f] is not None]
        if not vals: continue
        controls[label(fields[f])]=dict(min=min(vals),max=max(vals)) if fields[f]['kind']=='number' else sorted(set(vals))
    traces=[]; stats=[]
    if plan.kind=='scatter':
        for i,(group,gr) in enumerate(groups.items()):
            color=COLORS[i%len(COLORS)]
            x=[r['values'][plan.x] for r in gr]; y=[r['values'][plan.y] for r in gr]
            fit=regression(x,y,[r['cluster'] for r in gr])
            stat=dict(group=group,**fit)
            stats.append(stat)
            traces.append(dict(type='scatter',mode='markers',name=group,legendgroup=str(i),x=x,y=y,customdata=[r['id'] for r in gr],marker=dict(size=8,color=color,opacity=.65,line=dict(color='white',width=.5)),hovertemplate=f"{label(fields[plan.x])}: %{{x:.5g}}<br>{label(fields[plan.y])}: %{{y:.5g}}<br>Source: %{{customdata}}<extra>%{{fullData.name}}</extra>"))
            if fit['available']:
                traces.extend([
                    dict(type='scatter',mode='lines',x=fit['x'],y=fit['lower'],line=dict(width=0),showlegend=False,legendgroup=str(i),hoverinfo='skip',meta='band',visible=False),
                    dict(type='scatter',mode='lines',x=fit['x'],y=fit['upper'],line=dict(width=0),fill='tonexty',fillcolor='rgba(90,90,90,0.08)',showlegend=False,legendgroup=str(i),hoverinfo='skip',meta='band',visible=False),
                    dict(type='scatter',mode='lines',x=fit['x'],y=fit['y'],line=dict(width=2,color=color),showlegend=False,legendgroup=str(i),hoverinfo='skip',meta='fit')])
        fig=dict(data=traces,layout=layout(plan.title,label(fields[plan.x]),label(fields[plan.y])))
        if len(groups)>7:
            fig['layout']['height']=540
            warnings.append('Several groups are shown; click a legend entry to hide it, or double-click to isolate it.')
        warnings.append('Fits describe associations in these records. Controlled settings, changing ambient conditions and repeated tests can prevent a causal interpretation. No fit is extrapolated beyond its observed x range.')
        caption=f"{len(valid)} paired records in {len(groups)} groups; {sum(s['available'] for s in stats)} groups support a linear fit."
    else:
        # Numeric x uses labelled bins; category x retains its actual levels.
        numeric=fields[plan.x]['kind']=='number'
        edges=np.unique(np.quantile([r['values'][plan.x] for r in valid],np.linspace(0,1,6))) if numeric else None
        categories=sorted(set(r['values'][plan.x] for r in valid)) if not numeric else []
        if numeric:
            categories=[f'{edges[j]:.4g}–{edges[j+1]:.4g}' for j in range(len(edges)-1)] if len(edges)>1 else [f'{edges[0]:.4g}']
        outcomes=sorted(set(r['values'][plan.y] for r in valid))
        base_categories=categories[:]
        grouped_numeric=numeric and bool(group_fields)
        if grouped_numeric:
            categories=[g+' | '+c for g in groups for c in base_categories]
        bins={c:[] for c in categories}
        for r in valid:
            val=r['values'][plan.x]
            idx=max(0,min(len(base_categories)-1,int(np.searchsorted(edges,val,side='right')-1))) if numeric else base_categories.index(val)
            cat=base_categories[idx]
            if grouped_numeric:
                g=' · '.join(f"{fields[f]['label']}: {r['values'][f]}{(' '+fields[f]['unit']) if fields[f]['unit'] else ''}" for f in group_fields)
                cat=g+' | '+cat
            bins[cat].append(r)
        bins={c:rs for c,rs in bins.items() if rs}
        categories=list(bins)
        for i,outcome in enumerate(outcomes):
            counts=[sum(r['values'][plan.y]==outcome for r in bins[c]) for c in categories]
            totals=[len(bins[c]) for c in categories]
            traces.append(dict(type='bar',name=outcome,x=categories,y=[100*n/t if t else 0 for n,t in zip(counts,totals)],customdata=[[n,t] for n,t in zip(counts,totals)],marker=dict(color=COLORS[i%len(COLORS)]),hovertemplate='%{x}<br>%{y:.1f}% · %{customdata[0]} of %{customdata[1]} records<extra>%{fullData.name}</extra>'))
            stats.append(dict(group=outcome,counts=dict(zip(categories,counts)),totals=dict(zip(categories,totals))))
        fig=dict(data=traces,layout=layout(plan.title,label(fields[plan.x])+(' · quantile bins' if numeric else ''),'Share of reported outcomes (%)'))
        fig['layout'].update(barmode='stack');fig['layout']['yaxis'].update(range=[0,100])
        warnings.append('Outcome shares are descriptive, not extinction probabilities under controlled conditions. Flow termination is an intervention, not evidence that a flame would never extinguish. Linear regression is not applied to categorical outcomes.')
        caption=f"{len(valid)} records show the distribution of {len(outcomes)} reported outcomes; denominators are available on hover."
    payload=plan.model_dump(); chart_id=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:12]
    used_fields=list(dict.fromkeys([plan.x,plan.y]+group_fields+[f.field for f in plan.filters]+d['controls']))
    return dict(id=chart_id,plan=payload,dataset=d['name'],source=d['source'],file=d['file'],sha256=d['sha256'],quality=d['quality'],n=len(valid),filtered_count=filtered_count,missing_pairs=missing_count,caption=caption,figure=fig,stats=stats,warnings=warnings,automatic_filters=automatic,controls=controls,row_ids=[r['id'] for r in valid],highlight_columns=[fields[f]['index'] for f in used_fields],selected_columns={f:label(fields[f]) for f in used_fields},rows=[dict(id=r['id'],row=r['row'],line_start=r['line_start'],line_end=r['line_end'],cells=r['cells'],values=r['values']) for r in valid],headers=d['headers'])

def summary_for_model(chart):
    return {k:chart[k] for k in ('id','dataset','source','n','caption','warnings','automatic_filters','controls','missing_pairs','selected_columns')} | dict(plan=chart['plan'], statistics=[{k:v for k,v in s.items() if k not in ('x','y','lower','upper')} for s in chart['stats']], example_rows=[r['values'] for r in chart['rows'][:4]])

def analyze_many(plan):
    """Split SPICE's three nozzle configurations so 17 regressions never overlap."""
    if plan.dataset=='spice' and 'diameter' not in (plan.x,plan.y) and not any(f.field=='diameter' for f in plan.filters):
        d=load_dataset('spice')
        diameters=sorted(set(r['values']['diameter'] for r in d['rows'] if r['values']['diameter'] is not None))
        charts=[]
        for diameter in diameters:
            copy=plan.model_copy(deep=True)
            copy.filters.append(Filter(field='diameter',op='eq',values=[str(diameter)]))
            copy.title=plan.title+f' · {diameter:g} mm nozzle'
            try: charts.append(analyze(copy))
            except ValueError as error:
                if 'no usable paired records' not in str(error): raise
        if not charts:raise ValueError('No usable SPICE pairs after filtering.')
        return charts
    return [analyze(plan)]
