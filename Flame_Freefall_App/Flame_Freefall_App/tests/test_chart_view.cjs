const {test}=require('node:test');
const assert=require('node:assert/strict');
const {buildFigure}=require('../web/chart-view.js');

function fixture(count=2){
 const data=[];
 for(let i=0;i<count;i++){
  const base={type:'scatter',legendgroup:String(i),x:[1+i,2+i,3+i]};
  data.push({...base,mode:'markers',name:'Fuel: Group '+i,marker:{color:'#2563a0'},y:[3,4,5],customdata:['row'+i+'a','row'+i+'b','row'+i+'c']});
  data.push({...base,mode:'lines',meta:'fit',line:{width:0},y:[2,3,4]});
  data.push({...base,mode:'lines',meta:'fit',line:{width:0},fill:'tonexty',y:[4,5,6]});
  data.push({...base,mode:'lines',meta:'fit',line:{width:2},y:[3,4,5]});
 }
 return {plan:{kind:'scatter'},figure:{data,layout:{xaxis:{title:{text:'Diameter (mm)'}},yaxis:{title:{text:'Duration (s)'}}}}};
}

test('old cached bands are hidden while measured points and fits are preserved',()=>{
 const input=fixture(),before=JSON.stringify(input),figure=buildFigure(input);
 assert.equal(JSON.stringify(input),before);
 assert.equal(figure.data.filter(t=>t.meta==='band'&&t.visible===false).length,4);
 assert.equal(figure.data.filter(t=>t.meta==='fit'&&t.visible===true).length,2);
 const points=figure.data.filter(t=>t.mode==='markers');
 assert.deepEqual(points.map(t=>t.customdata),input.figure.data.filter(t=>t.mode==='markers').map(t=>t.customdata));
 assert.deepEqual(figure.data.find(t=>t.meta==='fit').x,[1,2,3]);
});

test('uncertainty is opt-in and disappears when fitted lines are disabled',()=>{
 assert.ok(buildFigure(fixture(),{band:true}).data.filter(t=>t.meta==='band').every(t=>t.visible));
 assert.ok(buildFigure(fixture(),{band:true,fit:false}).data.filter(t=>t.meta).every(t=>!t.visible));
 const fresh=fixture();fresh.figure.data.filter(t=>t.line?.width===0).forEach(t=>t.meta='band');
 assert.equal(buildFigure(fresh).data.filter(t=>t.meta==='band'&&!t.visible).length,4);
});

test('six fuel panels share scales, preserve all rows and use matched zoom axes',()=>{
 const input=fixture(6),figure=buildFigure(input,{panels:true,width:900});
 assert.equal(figure.layout.annotations.length,6);
 assert.equal(figure.data.filter(t=>t.mode==='markers').length,6);
 assert.deepEqual(figure.layout.xaxis.range,figure.layout.xaxis6.range);
 assert.deepEqual(figure.layout.yaxis.range,figure.layout.yaxis6.range);
 assert.equal(figure.layout.xaxis6.matches,'x');
 assert.equal(figure.layout.yaxis6.matches,'y');
 assert.ok(figure.data.filter(t=>t.legendgroup==='5').every(t=>t.xaxis==='x6'&&t.yaxis==='y6'));
 assert.ok(figure.layout.xaxis2.domain[0]>figure.layout.xaxis.domain[1]);
});

test('small screens stack panels and keep labels safely escaped',()=>{
 const input=fixture(2);input.figure.data[0].name='Fuel: <img src=x onerror=alert(1)>';
 const figure=buildFigure(input,{panels:true,width:360});
 assert.deepEqual(figure.layout.xaxis.domain,figure.layout.xaxis2.domain);
 assert.ok(figure.layout.yaxis2.domain[1]<figure.layout.yaxis.domain[0]);
 assert.ok(figure.layout.annotations[0].text.includes('&lt;'));
 assert.ok(!figure.layout.annotations[0].text.includes('<img'));
});
