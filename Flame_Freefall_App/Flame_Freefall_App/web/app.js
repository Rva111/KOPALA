'use strict';
const $=s=>document.querySelector(s), el=(tag,cls)=>{const n=document.createElement(tag);if(cls)n.className=cls;return n;};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const rich=s=>esc(s).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
const num=n=>n==null?'—':Number(n).toLocaleString(undefined,{maximumSignificantDigits:4});
let catalog, history=[], busy=false;

async function api(path,options={}){
 const res=await fetch(path,{...options,headers:{'Content-Type':'application/json','X-Flame-Token':catalog?.token||'',...(options.headers||{})}});
 if(!res.ok){let message='The request could not complete.';try{const data=await res.json();message=typeof data.detail==='string'?data.detail:message;}catch{}throw new Error(message);}
 return res.json();
}
function setBusy(value){busy=value;$('#send').disabled=value;$('#compare-submit').disabled=value;$('#working').hidden=!value;}
function errorBox(message){const b=el('div','error');b.textContent=message;$('#conversation').append(b);b.scrollIntoView({behavior:'smooth',block:'center'});}
function fieldLabel(f){return f.label+(f.unit?' ('+f.unit+')':'');}
function option(select,value,label){const o=el('option');o.value=value;o.textContent=label;select.append(o);}

async function submit(question,direct=null,explain=true){
 if(busy||!question.trim())return;
 $('#welcome').hidden=true;$('#progress').textContent='Starting analysis…';setBusy(true);$('#question').value='';
 const turn=el('article','turn'), label=el('div','question-label'),h=el('h2','question-text');label.textContent='YOU';h.textContent=question;turn.append(label,h);$('#conversation').append(turn);turn.scrollIntoView({behavior:'smooth',block:'start'});
 try{
  const {job_id}=await api('/api/ask',{method:'POST',body:JSON.stringify({question,history:history.slice(-4),direct,explain})});
  let job;
  do {await new Promise(r=>setTimeout(r,900));job=await api('/api/jobs/'+job_id);$('#progress').textContent=job.progress||'Working…';} while(job.status==='running');
  if(job.status==='error')throw new Error(job.error);
  renderResult(turn,job.result,job_id);
  history.push({question,answer:job.result.introduction,charts:job.result.charts.map(c=>c.plan)});
  history=history.slice(-4);
 }catch(error){const box=el('div','error');box.textContent=error.message;turn.append(box);}
 finally{setBusy(false);$('#question').focus();}
}

function renderResult(parent,result,jobId){
 const intro=el('div','intro');intro.innerHTML=rich(result.introduction);parent.append(intro);
 if(result.missing?.length){const m=el('div','notice');m.textContent=result.missing.join(' ');parent.append(m);}
 for(const [index,c] of result.charts.entries())renderChart(parent,c,jobId,index);
 for(const error of result.errors||[]){const e=el('p','notice');e.textContent=error;parent.append(e);}
 const conclusion=el('div','conclusion');conclusion.innerHTML=rich(result.conclusion);parent.append(conclusion);
 const evidence=el('div');for(const e of result.evidence||[]){const b=el('button','source-chip');b.textContent=`NASA ${e.paper} · p. ${e.page} · highlight`;b.onclick=()=>openPaper(e);evidence.append(b);}parent.append(evidence);
 const foot=el('div','answer-foot');foot.innerHTML=`<span>${result.cached?'Saved analysis':'Analysis complete'}</span><span>NASA CSV measurements · source references</span>`;
 const download=el('a');download.href='/api/report/'+jobId;download.textContent='Save analysis';download.download='flame_analysis.json';foot.append(download);parent.append(foot);
}

function renderChart(parent,c,jobId,index){
 const card=el('section','chart-card'),head=el('div','chart-head'),meta=el('span');meta.textContent=`${String(index+1).padStart(2,'0')} / ${c.dataset} · ${c.n} records`;
 const plot=el('div','plot'),panelNote=el('p','panel-note'),settings={fit:true,band:false,panels:c.plan.kind==='scatter'&&FlameCharts.groups(c).length>3};
 panelNote.textContent='Separate groups, matching axis scales. Use “Compare together” to overlay them.';
 let drawing=Promise.resolve(),clickBound=false,lastWidth=0;
 function draw(){
  drawing=drawing.then(async()=>{
   if(!plot.isConnected)return;
   panelNote.hidden=!settings.panels;
   lastWidth=plot.clientWidth;
   const figure=FlameCharts.buildFigure(c,{...settings,width:lastWidth});
   await Plotly.react(plot,figure.data,figure.layout,{responsive:true,displaylogo:false,displayModeBar:'hover',modeBarButtonsToRemove:['select2d','lasso2d','toImage']});
   if(!clickBound){plot.on('plotly_click',event=>{const id=event.points?.[0]?.customdata;if(typeof id==='string')openRows(c,jobId,id);});clickBound=true;}
  }).catch(()=>{plot.textContent='This chart could not render. Reload the page and try again; the source rows remain available.';});
  return drawing;
 }
 const actions=el('div','chart-actions');
 const source=el('button');source.textContent='Source rows';source.onclick=()=>openRows(c,jobId);actions.append(source);
 const csv=el('a');csv.textContent='CSV ↓';csv.href=`/api/export/${jobId}/${c.id}`;actions.append(csv);
 const png=el('button','png');png.textContent='PNG ↓';actions.append(png);
 if(c.plan.kind==='scatter'){
  const fitLabel=el('label','fit-switch'),fit=el('input');fit.type='checkbox';fit.checked=true;fitLabel.append(fit,document.createTextNode('Fit'));actions.append(fitLabel);
  const bandLabel=el('label','fit-switch'),band=el('input');band.type='checkbox';band.checked=false;bandLabel.append(band,document.createTextNode('95% band'));bandLabel.title='Uncertainty in the fitted mean, within the measured range';actions.append(bandLabel);
  fit.onchange=()=>{settings.fit=fit.checked;band.disabled=!fit.checked;draw();};
  band.onchange=()=>{settings.band=band.checked;draw();};
  if(FlameCharts.groups(c).length>1){
   const view=el('select','chart-view');view.setAttribute('aria-label','Chart group layout');
   option(view,'overlay','Compare together');option(view,'panels','Separate panels');view.value=settings.panels?'panels':'overlay';
   view.onchange=()=>{settings.panels=view.value==='panels';draw();};actions.append(view);
  }
 }
 head.append(meta,actions);card.append(head);
 const title=el('h3','chart-title');title.textContent=c.plan.title;card.append(title);
 panelNote.hidden=!settings.panels;card.append(panelNote);
 card.append(plot);parent.append(card);draw();
 const observer=new ResizeObserver(()=>{if(!plot.isConnected){observer.disconnect();return;}if(Math.abs(plot.clientWidth-lastWidth)>30)draw();});observer.observe(plot);
 png.onclick=async()=>{await drawing;if(plot.data)Plotly.downloadImage(plot,{format:'png',filename:'NASA_'+c.id,width:1400,height:Math.max(900,Math.round(plot.layout.height*1.45)),scale:1.5});};
 const caption=el('p','caption');caption.innerHTML=rich(c.caption);card.append(caption);
 if(c.plan.kind==='scatter'){
  const wrapper=el('div','stats-scroll'),table=el('table','stats');
  table.innerHTML='<thead><tr><th>Comparison group</th><th>Linear fit · y = mx + b</th><th>R²</th><th>Records / test groups</th></tr></thead><tbody>'+c.stats.map(s=>`<tr><td>${esc(s.group)}</td><td>${s.available?`y = ${num(s.slope)}x ${s.intercept<0?'−':'+'} ${num(Math.abs(s.intercept))}`:esc(s.reason)}</td><td>${num(s.r2)}</td><td>${s.n} / ${s.clusters}</td></tr>`).join('')+'</tbody>';
  wrapper.append(table);card.append(wrapper);
 }
 const details=el('details');details.innerHTML='<summary>Conditions, exclusions & interpretation</summary>';
 const text=el('div','smallprint');text.innerHTML=c.warnings.map(w=>'<p>'+esc(w)+'</p>').join('')+c.automatic_filters.map(w=>'<p>'+esc(w)+'</p>').join('')+`<p>${c.missing_pairs} records excluded for missing, ranged or nonnumeric axis values. ${c.quality.duplicates_removed} exact duplicates and ${c.quality.empty_removed} empty records excluded from the original table.</p>`;
 for(const [name,value] of Object.entries(c.controls)){const p=el('p');p.textContent=name+': '+(Array.isArray(value)?value.join(', '):`${num(value.min)}–${num(value.max)}`);text.append(p);}
 if(c.plan.kind==='scatter'){const p=el('p');p.textContent='Optional 95% band: cluster-robust uncertainty in the fitted mean, not individual prediction uncertainty. It is hidden by default. Lines and bands stay within each group’s measured x range. Separate panels share axis scales. Groups with fewer than 5 records/test groups or 3 distinct x values are shown without a fitted line.';text.append(p);}
 const link=el('a');link.href=c.source;link.target='_blank';link.rel='noopener';link.textContent='Open NASA investigation ↗';text.append(link);details.append(text);card.append(details);
}

function openRows(c,jobId,selected){
 $('#source-title').textContent=c.dataset+' · '+c.n+' source records';const root=$('#source-content');root.replaceChildren();
 const intro=el('p','muted');intro.textContent='Yellow cells were used for this graph, grouping or condition checks. Values below are the original CSV text. Click a point in the graph to locate its row.';root.append(intro);
 const links=el('div','source-actions');links.innerHTML=`<a href="/api/export/${jobId}/${c.id}">Download these rows ↓</a><a href="/api/original/${encodeURIComponent(c.file)}">Original NASA CSV ↓</a><a href="${esc(c.source)}" target="_blank" rel="noopener">NASA source ↗</a>`;root.append(links);
 const wrap=el('div','source-table'),table=el('table');
 table.innerHTML='<thead><tr><th>Source ID</th><th>CSV lines</th>'+c.headers.map((h,i)=>`<th class="${c.highlight_columns.includes(i)?'used':''}">${esc(h)}</th>`).join('')+'</tr></thead><tbody>'+c.rows.map(r=>`<tr data-row="${esc(r.id)}" class="${r.id===selected?'selected':''}"><td>${esc(r.id)}</td><td>${r.line_start}${r.line_end!==r.line_start?'–'+r.line_end:''}</td>${r.cells.map((v,i)=>`<td class="${c.highlight_columns.includes(i)?'used':''}">${esc(v)}</td>`).join('')}</tr>`).join('')+'</tbody>';
 wrap.append(table);root.append(wrap);const hash=el('p','muted');hash.style.overflowWrap='anywhere';hash.textContent='Original file SHA-256: '+c.sha256;root.append(hash);$('#source-dialog').showModal();if(selected)setTimeout(()=>table.querySelector('.selected')?.scrollIntoView({block:'center'}),60);
}
function openPaper(e){
 $('#source-title').textContent=`NASA ${e.paper} · PDF page ${e.page}`;const root=$('#source-content');root.replaceChildren();const quote=el('blockquote');quote.textContent=e.text;root.append(quote);const links=el('div','source-actions');links.innerHTML=`<a href="/api/evidence/${encodeURIComponent(e.id)}/highlighted.pdf#page=${e.page}" target="_blank" rel="noopener">Open highlighted PDF ↗</a><a href="/api/evidence/${encodeURIComponent(e.id)}/highlighted.pdf" download>Download highlighted PDF ↓</a><a href="${esc(e.source)}" target="_blank" rel="noopener">NASA source ↗</a>`;root.append(links);$('#source-dialog').showModal();
}

function configureComparison(){
 const d=catalog.datasets.find(d=>d.id===$('#dataset').value);for(const id of ['x-field','y-field','group-field','fuel-filter'])$('#'+id).replaceChildren();
 for(const [key,f] of Object.entries(d.fields)){option($('#x-field'),key,fieldLabel(f));option($('#y-field'),key,fieldLabel(f));if(f.kind==='category')option($('#group-field'),key,f.label);}
 option($('#group-field'),'','No additional group');$('#x-field').value=d.default[0];$('#y-field').value=d.default[1];$('#group-field').value=d.default[2]||'';
 for(const f of d.fields.fuel?.values||[])option($('#fuel-filter'),f,f);
 $('#dataset-note').textContent=d.note;$('#condition-filters').replaceChildren();
 for(const key of d.controls){const f=d.fields[key];if(f.kind!=='number')continue;const row=el('div','condition');row.innerHTML=`<span>${esc(fieldLabel(f))}</span><input type="number" step="any" data-field="${key}" data-op="gte" placeholder="Min" aria-label="Minimum ${esc(f.label)}"><input type="number" step="any" data-field="${key}" data-op="lte" placeholder="Max" aria-label="Maximum ${esc(f.label)}">`;$('#condition-filters').append(row);}
}
$('#compare-form').onsubmit=e=>{e.preventDefault();const d=catalog.datasets.find(d=>d.id===$('#dataset').value),x=$('#x-field').value,y=$('#y-field').value;const filters=[];const fuels=[...$('#fuel-filter').selectedOptions].map(o=>o.value);if(fuels.length)filters.push({field:'fuel',op:'in',values:fuels});for(const input of $('#condition-filters').querySelectorAll('input'))if(input.value.trim())filters.push({field:input.dataset.field,op:input.dataset.op,values:[input.value]});const kind=d.fields[y].kind==='category'?'outcomes':'scatter';if(kind==='scatter'&&d.fields[x].kind!=='number'){alert('For regression, choose a numeric horizontal axis. For outcomes, select Test end or Test termination vertically.');return;}const title=d.fields[y].label+' vs '+d.fields[x].label;const direct={dataset:d.id,x,y,group:$('#group-field').value,kind,filters,title};$('#compare-dialog').close();submit(`Compare ${title} in ${d.name}${fuels.length?' · '+fuels.join(' and '):''}.`,direct,$('#ai-explain').checked);};
$('#dataset').onchange=configureComparison;
$('#compare-open').onclick=()=>{if(catalog)$('#compare-dialog').showModal();};
$('#data-open').onclick=()=>{if(catalog)$('#data-dialog').showModal();};
for(const close of document.querySelectorAll('.close'))close.onclick=()=>close.closest('dialog').close();
for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
$('#ask-form').onsubmit=e=>{e.preventDefault();submit($('#question').value);};
$('#question').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit($('#question').value);}};
for(const b of document.querySelectorAll('[data-question]'))b.onclick=()=>{$('#question').value=b.dataset.question;$('#question').focus();};
$('#clear').onclick=()=>{if(busy)return;history=[];$('#conversation').replaceChildren();$('#welcome').hidden=false;$('#question').value='';scrollTo({top:0,behavior:'smooth'});};

async function init(){
 try{catalog=await api('/api/catalog');$('#dataset-count').textContent=`${catalog.file_count} NASA CSVs · ${catalog.total_records.toLocaleString()} usable records`;
 if(!catalog.api_ready){$('#key-warning').hidden=false;$('#key-warning').textContent='Add your private .env.local file to the app folder for AI answers. Compare works immediately without it.';}
 $('#data-summary').textContent=`${catalog.file_count} original CSV files. ${catalog.datasets.length} tables have validated chart fields, containing ${catalog.total_records.toLocaleString()} nonempty, deduplicated records. Records are not necessarily independent experiments. Snapshot: ${catalog.snapshot}.`;
 for(const d of catalog.datasets){option($('#dataset'),d.id,d.name);const card=el('div','dataset-item');card.innerHTML=`<h3>${esc(d.name)} <span class="muted">· ${d.quality.usable_records} records</span></h3><p>${esc(d.note)}</p><div>${Object.values(d.fields).map(f=>`<span class="tag">${esc(fieldLabel(f))}</span>`).join('')}</div><p><a href="${esc(d.source)}" target="_blank" rel="noopener">NASA investigation ↗</a></p>`;$('#dataset-list').append(card);}
 for(const f of catalog.originals){const a=el('a');a.href='/api/original/'+encodeURIComponent(f.filename);a.textContent=f.filename+' ↓';$('#original-list').append(a);}configureComparison();
 }catch(error){errorBox('The app could not load its dataset catalog. '+error.message);}
}
init();
