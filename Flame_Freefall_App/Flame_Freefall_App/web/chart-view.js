'use strict';
// Presentation only: keep every source point and fitted value unchanged.
(function(root){
 const clone=value=>JSON.parse(JSON.stringify(value));
 const escape=text=>String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function wrapped(text,limit=38){
  const lines=[''];
  for(const word of String(text).split(/\s+/)){
   const i=lines.length-1;
   if(lines[i]&&lines[i].length+word.length+1>limit)lines.push(word);
   else lines[i]+=(lines[i]?' ':'')+word;
  }
  return lines.map(escape).join('<br>');
 }
 function role(trace){
  if(trace.meta==='band'||(trace.meta==='fit'&&trace.line?.width===0))return 'band';
  if(trace.meta==='fit')return 'fit';
  return 'points';
 }
 function groups(chart){
  return chart.figure.data.filter(t=>t.type==='scatter'&&String(t.mode).includes('markers'));
 }
 function tint(hex){
  if(!/^#[0-9a-f]{6}$/i.test(hex||''))return 'rgba(90,90,90,0.10)';
  return `rgba(${[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)).join(',')},0.10)`;
 }
 function extent(values){
  const valid=values.filter(Number.isFinite);
  if(!valid.length)return [0,1];
  const lo=Math.min(...valid),hi=Math.max(...valid),pad=(hi-lo||Math.abs(lo)||1)*.07;
  return [lo-pad,hi+pad];
 }
 function groupTitle(group,all){
  const parts=String(group.name).split(' · ');
  // A condition common to all panels remains in the chart's title/condition table.
  const shared=parts.filter(part=>all.length>1&&all.every(g=>String(g.name).split(' · ').includes(part)));
  return (parts.filter(p=>!shared.includes(p)).join(' · ')||group.name).replace(/^Fuel(?: mixture)?: /,'');
 }
 function buildFigure(chart,{fit=true,band=false,panels=false,width=900}={}){
  const figure=clone(chart.figure),layout=figure.layout;
  layout.title={text:''};
  layout.paper_bgcolor='white';layout.plot_bgcolor='white';
  for(const key of ['xaxis','yaxis']){
   const axis=layout[key]||{};
   if(typeof axis.title==='string')axis.title={text:axis.title};
   layout[key]={...axis,automargin:true,gridcolor:'#eeeeee',zeroline:false};
  }
  if(chart.plan.kind!=='scatter')return figure;
  const all=groups(chart),data=[];
  all.forEach((group,i)=>{
   const traces=figure.data.filter(t=>String(t.legendgroup)===String(group.legendgroup));
   traces.sort((a,b)=>['band','fit','points'].indexOf(role(a))-['band','fit','points'].indexOf(role(b)));
   for(const trace of traces){
    const kind=role(trace);
    if(kind==='band'){
     trace.meta='band';trace.visible=fit&&band;trace.hoverinfo='skip';
     if(trace.fill)trace.fillcolor=tint(group.marker?.color);
    }else if(kind==='fit')trace.visible=fit;
    else{
     trace.marker={...trace.marker,size:7,opacity:.75,symbol:['circle','diamond','square','triangle-up','cross','triangle-down'][i%6]};
     trace.name=wrapped(groupTitle(group,all),width<650?24:38);
    }
    if(panels&&all.length>1){
     trace.xaxis='x'+(i?i+1:'');trace.yaxis='y'+(i?i+1:'');trace.showlegend=false;
    }
    data.push(trace);
   }
  });
  figure.data=data;
  layout.uirevision=(panels?'panels':'overlay')+':'+(band&&fit?'band':'plain')+':'+(width<650?'small':'large');
  if(panels&&all.length>1){
   const columns=width<650?1:2,rows=Math.ceil(all.length/columns);
   const panelHeight=285,totalHeight=rows*panelHeight;
   const gapY=85/totalHeight,domainHeight=(1-gapY*(rows-1))/rows;
   const gapX=columns===1?0:.18,domainWidth=(1-gapX*(columns-1))/columns;
   const visible=data.filter(t=>t.visible!==false);
   const xr=extent(all.flatMap(t=>t.x)),yr=extent(visible.flatMap(t=>t.y));
   const xbase=clone(layout.xaxis),ybase=clone(layout.yaxis);
   layout.annotations=[];layout.showlegend=false;
   layout.margin={l:76,r:24,t:50,b:70};layout.height=totalHeight+120;
   all.forEach((group,i)=>{
    const suffix=i?String(i+1):'',col=i%columns,row=Math.floor(i/columns);
    const left=col*(domainWidth+gapX),top=1-row*(domainHeight+gapY);
    layout['xaxis'+suffix]={...clone(xbase),domain:[left,left+domainWidth],anchor:'y'+suffix,range:xr,autorange:false,nticks:5,title:{...xbase.title,standoff:12},...(i?{matches:'x'}:{})};
    layout['yaxis'+suffix]={...clone(ybase),domain:[top-domainHeight,top],anchor:'x'+suffix,range:yr,autorange:false,nticks:5,title:{...ybase.title,standoff:10},...(i?{matches:'y'}:{})};
    layout.annotations.push({xref:'paper',yref:'paper',x:left+domainWidth/2,y:top,text:wrapped(groupTitle(group,all),38),showarrow:false,xanchor:'center',yanchor:'bottom',yshift:10,font:{size:12,color:'#202020'}});
   });
  }else{
   layout.showlegend=true;
   layout.height=all.length>3?520:440;
   layout.margin={l:width<650?62:76,r:20,t:20,b:all.length>3?130:90};
   layout.legend={orientation:'h',y:-.22,x:0,xanchor:'left',yanchor:'top',font:{size:11},groupclick:'togglegroup'};
  }
  return figure;
 }
 const api={buildFigure,groups};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.FlameCharts=api;
})(globalThis);
