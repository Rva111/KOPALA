"""NASA CSV registry. Original cells stay unchanged; typed fields carry provenance."""
from pathlib import Path
import csv, hashlib, io, json, math, re

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
NUMBER = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')

def number(value):
    s = str(value).strip()
    if not NUMBER.fullmatch(s):
        return None
    v = float(s)
    return v if math.isfinite(v) else None

def field(index, label, unit='', kind='number', note=''):
    return dict(index=index, label=label, unit=unit, kind=kind, note=note)

F = field
REGISTRY = {
 'spice': dict(file='PSI-107_Experimental table_Spice.csv', name='SPICE · gas jets', accession='PSI-107',
   note='Airflow, fuel flow and nozzle diameter are imposed settings, not measured flame spread. Repeated flow stages share an ignition; exact duplicate rows are excluded. No flame-length or flame-spread column exists in this table.',
   fields=dict(fuel=F(3,'Fuel mixture',kind='category'), diameter=F(4,'Nozzle diameter','mm'), fuel_volume=F(5,'Fuel volumetric flow','sccm'), fuel_flow=F(6,'Fuel mass flow','mg/s'), hc_flow=F(7,'Hydrocarbon mass flow','mg/s'), airflow=F(8,'Air speed','cm/s')),
   controls=['fuel','diameter'], default=['airflow','fuel_flow','fuel']),
 'flex': dict(file='PSI-69_Experimental table_FLEX.csv', name='FLEX · liquid droplets', accession='PSI-69',
   note='No airflow column. Extinction diameter denotes droplet size at visible-flame extinction, not the diameter of a flame. Disruption and completion are separate outcomes. The CSV burning-rate unit is truncated; mm²/s is restored from NASA report 20150023456, Table 1, whose rows match this CSV.',
   fields=dict(fuel=F(4,'Fuel',kind='category'), pressure=F(5,'Ambient pressure','mmHg'), oxygen=F(6,'Initial oxygen mole fraction'), nitrogen=F(7,'Initial nitrogen mole fraction'), co2=F(8,'Initial carbon dioxide mole fraction'), helium=F(9,'Initial helium mole fraction'), diameter=F(10,'Initial droplet diameter','mm'), extinction_diameter=F(11,'Droplet diameter at visible-flame extinction','mm'), burning_rate=F(12,'Droplet burning-rate constant','mm²/s',note='Unit restored from NASA 20150023456 Table 1; original CSV preserved.'), burn_time=F(13,'Burn duration','s'), outcome=F(14,'Test end',kind='category')),
   controls=['oxygen','pressure','co2','helium'], default=['diameter','burn_time','fuel']),
 'cfi_normal': dict(file='PSI-159_Experimental table_CFI-G_Normal Flames.csv', name='CFI-G · normal flames', accession='PSI-159',
   note='Fuel mass flow is not air speed. SE means self-extinction; FT means flow termination. Neither failed ignition nor a blank is evidence of sustained combustion. Burn duration depends on how the test ended. Tad is a calculated adiabatic temperature; peak burner temperature is not flame temperature.',
   fields=dict(fuel=F(2,'Fuel mixture',kind='category'), oxygen=F(5,'Oxygen mole fraction before test'), oxygen_final=F(6,'Oxygen mole fraction after test'), pressure=F(7,'Approximate pressure','bar'), fuel_fraction=F(8,'Fuel mole fraction'), fuel_flow=F(9,'Hydrocarbon mass flow','mg/s'), tad=F(11,'Calculated adiabatic temperature','K'), ignition=F(13,'Hot ignition',kind='category'), burn_time=F(14,'Burn duration','s'), outcome=F(15,'Test termination',kind='category'), burner_temperature=F(16,'Peak burner temperature','°C')),
   controls=['oxygen','pressure','fuel_fraction'], default=['fuel_flow','burn_time','fuel']),
 'cfi_inverse': dict(file='PSI-159_Experimental table_CFI-G_Inverse Flames.csv', name='CFI-G · inverse flames', accession='PSI-159',
   note='Oxygen mass flow is not air speed. SE means self-extinction; FT means flow termination. Entirely empty rows are excluded. Burn duration depends on test termination; failed ignitions are excluded from burn-duration regressions. Tad is calculated, not a measured flame temperature.',
   fields=dict(fuel=F(2,'Fuel',kind='category'), fuel_fraction=F(4,'Fuel mole fraction before test'), pressure=F(6,'Approximate pressure','bar'), oxygen=F(7,'Oxygen mole fraction'), hc_flow=F(8,'Hydrocarbon burn rate','mg/s'), oxygen_flow=F(9,'Oxygen mass flow','mg/s'), tad=F(11,'Calculated adiabatic temperature','K'), ignition=F(13,'Hot ignition',kind='category'), burn_time=F(14,'Burn duration','s'), outcome=F(15,'Test termination',kind='category'), burner_temperature=F(16,'Peak burner temperature','°C')),
   controls=['oxygen','pressure','fuel_fraction'], default=['oxygen_flow','burn_time','fuel']),
 'bass2': dict(file='PSI-25_Experimental table_BASS-II.csv', name='BASS-II · solid materials', accession='PSI-25',
   note='Air display is an uncalibrated instrument setting, not cm/s. Multi-setting entries are excluded from numeric analysis. Material labels include different geometries. No paired flame-spread-rate column exists.',
   fields=dict(fuel=F(5,'Material and geometry',kind='category'), restrictor=F(6,'Flow restrictor',kind='category'), air_display=F(8,'Air display setting','display units'), oxygen=F(11,'Initial oxygen','vol %'), oxygen_final=F(12,'Final oxygen','vol %'), co2=F(13,'Initial carbon dioxide','vol %'), co2_final=F(14,'Final carbon dioxide','vol %'), co=F(15,'Initial carbon monoxide','ppm'), co_final=F(16,'Final carbon monoxide','ppm')),
   controls=['fuel','restrictor'], default=['oxygen','oxygen_final','fuel']),
 'same': dict(file='PSI-102_Experimental table_SAME.csv', name='SAME · smoke generation', accession='PSI-102',
   note='Small smoke/aerosol experiment table; weight loss is not flame spread. Too few distinct airflow settings may prevent a useful regression.',
   fields=dict(fuel=F(1,'Sample material',kind='category'), airflow=F(2,'Air speed','cm/s'), loss_rate=F(3,'Weight loss rate','mg/min'), aging=F(4,'Aging duration','min')),
   controls=['fuel'], default=['airflow','loss_rate','fuel']),
 'same_r': dict(file='PSI-101_Experimental table_SAME-R.csv', name='SAME-R · smoke aging', accession='PSI-101',
   note='Smoke generation and aging settings, not flame dimensions or flame-spread measurements. Rt/R0 is retained only in the original table because its definition needs further documentation.',
   fields=dict(fuel=F(0,'Sample material',kind='category'), airflow=F(4,'Inlet air speed','cm/s'), duration=F(6,'Generation duration','s'), aging=F(9,'Net aging time','s')),
   controls=['fuel'], default=['airflow','duration','fuel']),
}

# Flame Design tables have independently named columns, so mappings remain explicit.
REGISTRY['design_normal'] = dict(file='PSI-10_Experimental table_Flame Design_Normal Flame.csv', name='Flame Design · normal', accession='PSI-10', note='Input settings and calculated quantities. Tad is calculated adiabatic temperature, not observed flame temperature. Ramped flow entries are excluded.', fields={}, controls=[], default=[])
REGISTRY['design_inverse'] = dict(file='PSI-10_Experimental table_Flame Design_Inverse Flame.csv', name='Flame Design · inverse', accession='PSI-10', note='Input settings and calculated quantities. Oxygen flow is not air speed. Tad is calculated, not observed flame temperature. Ramped entries are excluded.', fields={}, controls=[], default=[])

def read_original(filename):
    raw = (DATA/'originals'/filename).read_bytes()
    try:
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        content = raw.decode('cp1252')
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    inventory=json.loads((DATA/'inventory.json').read_text(encoding='utf-8-sig'))
    expected=next((f.get('expected_headers') for it in inventory for f in it['files'] if f['filename']==filename),None)
    if expected and headers!=expected:
        raise ValueError(f'Source schema changed for {filename}. Review the column map before using updated data.')
    rows = []
    previous_line = reader.line_num
    for ordinal, cells in enumerate(reader, 1):
        rows.append(dict(row=ordinal, line_start=previous_line+1, line_end=reader.line_num, cells=cells))
        previous_line = reader.line_num
    return raw, headers, rows

def normalize_category(key, value):
    text = ' '.join(str(value).split())
    if key == 'fuel':
        text = re.sub(r'\s*%\s*', '% ', text)
    if key == 'ignition':
        text = text.casefold()
    if key == 'outcome':
        text = {'SE':'Self-extinction','FT':'Flow terminated','-':'Unreported'}.get(text, text)
    return text or 'Unreported'

def load_dataset(key):
    if key not in REGISTRY: raise ValueError('Unknown dataset.')
    meta = REGISTRY[key]
    raw, headers, originals = read_original(meta['file'])
    seen, rows, blank, duplicate = set(), [], 0, 0
    for row in originals:
        cells = row['cells']
        if not any(c.strip() for c in cells):
            blank += 1; continue
        sig = tuple(c.strip() for c in cells)
        if sig in seen:
            duplicate += 1; continue
        seen.add(sig)
        typed = {}
        for name, f in meta['fields'].items():
            val = cells[f['index']] if f['index'] < len(cells) else ''
            typed[name] = number(val) if f['kind']=='number' else normalize_category(name,val)
        cluster = '|'.join(cells[:2]) if key=='spice' else '|'.join(cells[1:4]) if key=='flex' else '|'.join([' '.join(cells[1].split()),' '.join(cells[3].split())]) if key.startswith('cfi_') else str(row['row'])
        rows.append(dict(**row, values=typed, cluster=cluster, id=f"{key}:r{row['row']}"))
    return dict(id=key, **meta, headers=headers, rows=rows, sha256=hashlib.sha256(raw).hexdigest(), source=f"https://psi.nasa.gov/physci/repo/data/investigations/{meta['accession']}", quality=dict(raw_records=len(originals),usable_records=len(rows),empty_removed=blank,duplicates_removed=duplicate,ignition_clusters=len(set(r['cluster'] for r in rows))))

def init_design_fields():
    for key in ('design_normal','design_inverse'):
        _, headers, _ = read_original(REGISTRY[key]['file'])
        # Exact units come from original headers; do not guess unlabelled units.
        fields = {}
        for i,h in enumerate(headers):
            h_clean=' '.join(h.split())
            if any(t in h_clean.lower() for t in ('mg/s','atm','tad','x','zst')) and h_clean.lower() not in ('test', 'flame type'):
                fields[f'c{i}']=F(i,h_clean)
        REGISTRY[key]['fields']=fields
        REGISTRY[key]['default']=(list(fields)[:2]+[''])
init_design_fields()

def catalog():
    datasets=[]
    for key in REGISTRY:
        d=load_dataset(key)
        fields={}
        for name,f in d['fields'].items():
            vals=[r['values'][name] for r in d['rows'] if r['values'][name] is not None]
            profile=dict(**f, valid=len(vals))
            if f['kind']=='number':
                profile.update(min=min(vals) if vals else None,max=max(vals) if vals else None,distinct=len(set(vals)))
            else: profile['values']=sorted(set(vals))
            fields[name]=profile
        datasets.append({k:d[k] for k in ('id','name','note','source','file','quality','sha256','default')} | dict(fields=fields,controls=d['controls']))
    inventory=json.loads((DATA/'inventory.json').read_text(encoding='utf-8-sig'))
    originals=[dict(**f, accession=it['id'], title=it['title']) for it in inventory for f in it['files']]
    return dict(datasets=datasets, originals=originals, snapshot=max(f.get('downloaded_utc','') for f in originals), total_records=sum(d['quality']['usable_records'] for d in datasets), file_count=len(originals))

def fingerprint():
    return hashlib.sha256(''.join(d['sha256'] for d in catalog()['datasets']).encode()).hexdigest()
