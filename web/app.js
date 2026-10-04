/* Dependency-free UI; all research content comes from the backend API. */
'use strict';
const $ = (selector) => document.querySelector(selector);
const state = { graph: null, selected: null, selectionType: 'node', detail: 'connection', report: null, live: null, view: 'network', positions: {}, health: null, request: 0, query: 'STXBP1' };
const colors = {'Vesicle release':'#3f7e87','GABA reuptake':'#83a68c','Shared observations':'#a691b1','Shared infrastructure':'#d9b362','Published evidence':'#8c9caf','Diseases':'#3f7e87','Genes':'#83a68c','Phenotypes':'#a691b1','Studies':'#d9b362','Publications':'#8c9caf','Investigators':'#c07966','Variants':'#ad83a6','Search context':'#243746'};
const categoryNames = {'Shared observations':'Shared phenotypes','Vesicle release':'Synaptic vesicle release','GABA reuptake':'GABA reuptake','Shared infrastructure':'Research infrastructure','Published evidence':'Scientific literature','Phenotypes':'Phenotypes','Investigators':'Researchers','Variants':'Genetic variants','Search context':'Search context'};
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const shorten = (value, n=30) => value.length > n ? value.slice(0,n-1) + '…' : value;
const pretty = value => String(value || '').replaceAll('_',' ');
const metadataCandidate = e => e.metadata_only && ['identity_search_candidate','automatically_annotated_mention'].includes(e.relation);
function link(url, text) {
  try { if (new URL(url).protocol !== 'https:') return esc(text); } catch { return esc(text); }
  return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)} ↗</a>`;
}
function badge(status) { const cls = ['inferred','hypothesis','research_proposal'].includes(status) ? 'gold' : ['disputed','conflicting'].includes(status) ? 'rust' : ['unknown','unreviewed_candidate'].includes(status) ? 'muted' : ''; return `<span class="badge ${cls}">${esc(pretty(status))}</span>`; }
async function api(url, body) {
  const response = await fetch(url, body ? { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) } : {});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The request could not be completed.');
  return data;
}
function showError(error) { $('#progress').textContent = error.message; $('#progress').classList.add('error'); }
function options() { return {focus:state.graph?.focus || 'MONDO:0012812', ...(state.graph?.graph_id?{graph_id:state.graph.graph_id}:{}), min_confidence:$('#confidence').value, include_inferred:$('#hypotheses').checked}; }
async function loadGraph(focus) {
  const serial = ++state.request;
  const params = new URLSearchParams({...options(), focus});
  $('#map-status').textContent = 'Filtering the evidence…';
  try {
    const graph = await api('/api/graph?' + params);
    if (serial !== state.request) return;
    displayGraph(graph);
  } catch (error) { showError(error); }
}
function displayGraph(graph) {
    const focus=graph.focus;
    const hiddenClusters=new Set(state.graph?.focus===focus?[...$('#cluster-list').querySelectorAll('[data-cluster]:not(:checked)')].map(input=>input.dataset.cluster):[]);
    state.graph = graph; state.selected = focus; state.selectionType = 'node'; state.report = null; state.live = graph.live||null; state.positions = {};
    const node = graph.nodes.find(n => n.id === focus);
    $('#identity').textContent = node.label + ' · ' + node.id;
    $('#graph-count').textContent = `${graph.nodes.length} nodes · ${graph.edges.length} connections`;
    $('#map-status').textContent = `${graph.edges.filter(e=>e.status==='observed').length} documented · ${graph.edges.filter(e=>e.status==='inferred'&&!metadataCandidate(e)).length} proposed`;
    $('#cluster-list').innerHTML = graph.clusters.map(c=>`<label class="cluster-item"><input type="checkbox" data-cluster="${esc(c.name)}" ${hiddenClusters.has(c.name)?'':'checked'}><svg class="dot" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="5" fill="${colors[c.name]||'#98a8a4'}"/></svg><span>${esc(categoryNames[c.name]||c.name)}</span><span class="cluster-count">${c.count}</span></label>`).join('');
    $('#progress').textContent = ''; $('#progress').classList.remove('error');
    graphViewport={x:0,y:0,w:800,h:680};applyViewport();
    $('#cluster-list').querySelectorAll('[data-cluster]').forEach(input=>input.addEventListener('change',()=>{state.positions={};drawGraph();}));
    drawGraph(); renderDetails(); renderPapers(); renderActions(); loadLeads();
    const note=$('.scope-note');
    if(graph.graph_id)note.innerHTML='<span class="status-dot"></span><div>Live research graph<small>'+esc(graph.live.query)+'<br>Retrieved '+esc(graph.live.retrieved_at.slice(0,10))+'</small></div>';
}

function visibleGraph() {
  const full=state.graph;
  const visibleKinds=new Set(['disease','symptom','search','organization','asset','institution','researcher']);
  const graph=$('#graph-science').checked?{...full}:{...full,nodes:full.nodes.filter(n=>visibleKinds.has(n.kind))};
  const ids=new Set(graph.nodes.map(n=>n.id));
  graph.edges=full.edges.filter(e=>ids.has(e.subject)&&ids.has(e.object));
  const hiddenClusters=new Set([...$('#cluster-list').querySelectorAll('[data-cluster]:not(:checked)')].map(input=>input.dataset.cluster));
  graph.nodes=graph.nodes.filter(n=>!hiddenClusters.has(n.cluster||'Other'));
  const shownIds=new Set(graph.nodes.map(n=>n.id));
  graph.edges=graph.edges.filter(e=>shownIds.has(e.subject)&&shownIds.has(e.object));
  // Collapse paths through hidden nodes, preserving the original evidence edges.
  const neighbors=new Map(full.nodes.map(n=>[n.id,[]]));
  for(const e of full.edges){
    neighbors.get(e.subject)?.push({id:e.object,edge:e});
    neighbors.get(e.object)?.push({id:e.subject,edge:e});
  }
  const pairs=new Set(graph.edges.map(e=>JSON.stringify([e.subject,e.object].sort())));
  for(const start of graph.nodes){
    const seen=new Set([start.id]),queue=[{id:start.id,path:[],via:[]}];
    for(let i=0;i<queue.length;i++)for(const next of neighbors.get(queue[i].id)||[]){
      if(seen.has(next.id))continue;
      seen.add(next.id);
      const path=[...queue[i].path,next.edge.id],via=queue[i].via;
      if(shownIds.has(next.id)){
        const pair=JSON.stringify([start.id,next.id].sort());
        if(via.length&&!pairs.has(pair)){
          pairs.add(pair);
          graph.edges.push({id:'hidden-path:'+pair,subject:start.id,object:next.id,status:'collapsed',relation:'path_through_hidden_nodes',path,via,
            explanation:'Connected through hidden nodes: '+via.map(id=>full.nodes.find(n=>n.id===id).label).join(' → ')});
        }
      }else queue.push({id:next.id,path,via:[...via,next.id]});
    }
  }
  // Add only enough collapsed paths to join disconnected visible components.
  // Prefer paths from the search focus, avoiding a clique around shared papers.
  const parent=new Map(graph.nodes.map(n=>[n.id,n.id]));
  const root=id=>{while(parent.get(id)!==id)id=parent.get(id);return id;};
  const join=(a,b)=>{a=root(a);b=root(b);if(a===b)return false;parent.set(b,a);return true;};
  const direct=graph.edges.filter(e=>!e.path);
  direct.forEach(e=>join(e.subject,e.object));
  const routes=graph.edges.filter(e=>e.path).sort((a,b)=>
    Number(b.subject===full.focus||b.object===full.focus)-Number(a.subject===full.focus||a.object===full.focus)||a.path.length-b.path.length||a.id.localeCompare(b.id));
  graph.edges=[...direct,...routes.filter(e=>join(e.subject,e.object))];
  return graph;
}
function layout() {
  const graph=visibleGraph();
  const count=graph.nodes.length;
  const maxDegree=Math.max(1,...graph.nodes.map(n=>n.degree||0));
  const sizeScale=14/Math.sqrt(maxDegree);
  const nodes=graph.nodes.map((n,i)=>{
    const angle=i*2.399963, distance=50+210*Math.sqrt((i+1)/Math.max(1,count));
    const saved=state.positions[n.id];
    return {...n,x:saved?.x ?? 400+Math.cos(angle)*distance,y:saved?.y ?? 340+Math.sin(angle)*distance,
      // Connection counts scale size, with a readable minimum for category colors.
      radius:Math.max(6,sizeScale*Math.sqrt(n.degree||0))};
  });
  const byId=Object.fromEntries(nodes.map(n=>[n.id,n]));
  if(!Object.keys(state.positions).length){
    for(let tick=0;tick<280;tick++){
      const forces=nodes.map(()=>({x:0,y:0}));
      for(let i=0;i<count;i++)for(let j=i+1;j<count;j++){
        const a=nodes[i],b=nodes[j],dx=a.x-b.x,dy=a.y-b.y,d=Math.max(1,Math.hypot(dx,dy));
        const f=Math.min(8,1800/(d*d)+Math.max(0,65-d)*.08);
        forces[i].x+=dx/d*f;forces[i].y+=dy/d*f;forces[j].x-=dx/d*f;forces[j].y-=dy/d*f;
      }
      for(const e of graph.edges){
        const a=byId[e.subject],b=byId[e.object];if(!a||!b)continue;
        const dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),f=(d-100)*.015;
        a.fx=(a.fx||0)+dx/d*f;a.fy=(a.fy||0)+dy/d*f;
        b.fx=(b.fx||0)-dx/d*f;b.fy=(b.fy||0)-dy/d*f;
      }
      nodes.forEach((n,i)=>{
        n.x=Math.max(55,Math.min(745,n.x+forces[i].x+(n.fx||0)+(400-n.x)*.008));
        n.y=Math.max(50,Math.min(615,n.y+forces[i].y+(n.fy||0)+(340-n.y)*.008));
        n.fx=0;n.fy=0;
      });
    }
  }
  state.positions=Object.fromEntries(nodes.map(n=>[n.id,{x:n.x,y:n.y}]));
  return {nodes,byId,edges:graph.edges};
}
function graphLabel(n) {
  if(state.graph?.graph_id){
    if(n.kind==='paper')return (n.year||'')+' · '+n.id.replace('PMID:','');
    return shorten(n.graph_label||n.label,n.kind==='researcher'?16:23);
  }
  if(n.kind==='paper')return (n.label.includes('STXBP1')?'STXBP1':'SLC6A1')+' · '+n.year;
  if(n.kind==='study')return 'Shared clinical study';
  if(n.kind==='institution')return 'Weill Cornell';
  if(n.kind==='asset')return 'Simons Searchlight';
  if(n.kind==='mechanism')return n.id.endsWith('vesicle')?'Vesicle release ↓':'GABA reuptake ↓';
  if(n.id==='HP:0001263')return 'Developmental delay';
  if(n.kind==='disease')return n.gene;
  return shorten(n.label,24);
}
function drawGraph() {
  if (!state.graph) return;
  stopGraphMotion();
  const {nodes,byId,edges} = layout();
  state.visibleEdges=edges;
  $('#graph-count').textContent=`${nodes.length} nodes · ${edges.length} connections`;
  const svg=$('#graph');
  svg.classList.remove('has-highlight');
  svg.innerHTML = edges.map(e=>{
    const a=byId[e.subject],b=byId[e.object];
    return `<g class="edge-group ${state.selectionType==='edge'&&state.selected===e.id?'selected':''}" data-edge="${esc(e.id)}" role="button" tabindex="0" aria-label="${esc(a.label+' to '+b.label+': '+pretty(e.relation))}"><title>${esc(e.explanation)}</title><line class="edge-line ${metadataCandidate(e)?'candidate':e.status}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/><line class="edge-hit" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/></g>`;
  }).join('') + nodes.map(n=>`<g class="node ${state.selectionType==='node'&&state.selected===n.id?'selected':''}" data-node="${esc(n.id)}" transform="translate(${n.x},${n.y})" tabindex="0" role="button" aria-label="${esc(n.label+' · '+n.kind)}"><title>${esc(n.label+' · '+n.kind)}</title><circle r="${n.radius}" fill="${colors[n.cluster]||'#98a8a4'}"/><text y="${n.radius+17}">${esc(graphLabel(n))}</text></g>`).join('');
  svg.querySelectorAll('[data-edge]').forEach(el=>bindActivate(el,()=>select('edge',el.dataset.edge)));
  svg.querySelectorAll('[data-node]').forEach(el=> {
    el.addEventListener('click',()=>{if(!moved)select('node',el.dataset.node);});
    el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select('node',el.dataset.node);}});
    el.addEventListener('pointerenter',()=>highlightNeighborhood(el.dataset.node));
    el.addEventListener('pointerleave',()=>highlightNeighborhood(null));
    let drag=null,moved=false;
    el.addEventListener('pointerdown',event=>{ if(event.button!==0)return;drag={x:event.clientX,y:event.clientY};moved=false;beginGraphMotion(el.dataset.node);el.classList.add('dragging');el.setPointerCapture(event.pointerId); });
    el.addEventListener('pointermove',event=>{
      if(!drag)return;
      if(Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<5&&!moved)return;
      moved=true; const pt=svg.createSVGPoint();pt.x=event.clientX;pt.y=event.clientY;
      const position=pt.matrixTransform(svg.getScreenCTM().inverse());
      state.positions[el.dataset.node]={x:position.x,y:position.y};
      el.setAttribute('transform',`translate(${position.x},${position.y})`);
      paintGraphPositions();
      wakeGraphMotion();
    });
    const release=()=>{
      drag=null;el.classList.remove('dragging');
      if(graphMotion){
        if(moved){
          // Keep the dropped node in place and settle around the new arrangement.
          graphMotion.anchors=structuredClone(state.positions);
          graphMotion.velocities={};
          for(const e of graphMotion.edges){
            const a=state.positions[e.subject],b=state.positions[e.object];
            e.length=Math.hypot(a.x-b.x,a.y-b.y);
          }
          wakeGraphMotion();
        }else{stopGraphMotion();}
      }
    };
    el.addEventListener('pointerup',release);
    el.addEventListener('pointercancel',release);
    el.addEventListener('lostpointercapture',release);

  });
}
let graphMotion=null, motionFrame=0;
function stopGraphMotion(){cancelAnimationFrame(motionFrame);motionFrame=0;graphMotion=null;}
function paintGraphPositions(){
  const svg=$('#graph');
  svg.querySelectorAll('[data-node]').forEach(el=>{const p=state.positions[el.dataset.node];if(p)el.setAttribute('transform',`translate(${p.x},${p.y})`);});
  const groups=new Map([...svg.querySelectorAll('[data-edge]')].map(el=>[el.dataset.edge,el]));
  for(const e of state.visibleEdges||state.graph.edges){
    const a=state.positions[e.subject],b=state.positions[e.object];if(!a||!b)continue;
    groups.get(e.id)?.querySelectorAll('line').forEach(line=>{
      line.setAttribute('x1',a.x);line.setAttribute('y1',a.y);line.setAttribute('x2',b.x);line.setAttribute('y2',b.y);
    });
  }
}
function beginGraphMotion(id){
  stopGraphMotion();
  if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  graphMotion={pinned:id,anchors:structuredClone(state.positions),velocities:{},edges:(state.visibleEdges||state.graph.edges).filter(e=>state.positions[e.subject]&&state.positions[e.object]).map(e=>{
    const a=state.positions[e.subject],b=state.positions[e.object];
    return {...e,length:Math.hypot(a.x-b.x,a.y-b.y)};
  }),last:0,frames:0};
}
function wakeGraphMotion(){if(graphMotion&&!motionFrame){graphMotion.frames=0;graphMotion.last=0;motionFrame=requestAnimationFrame(stepGraphMotion);}}
function stepGraphMotion(time){
  motionFrame=0;const motion=graphMotion;if(!motion)return;
  const dt=motion.last?Math.min(2,(time-motion.last)/16.67):1;motion.last=time;
  const forces={};for(const [id,p] of Object.entries(state.positions)){
    const a=motion.anchors[id];forces[id]={x:(a.x-p.x)*.008,y:(a.y-p.y)*.008};
  }
  for(const e of motion.edges){
    const a=state.positions[e.subject],b=state.positions[e.object],dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy));
    const f=(d-e.length)*.025;
    forces[e.subject].x+=dx/d*f;forces[e.subject].y+=dy/d*f;
    forces[e.object].x-=dx/d*f;forces[e.object].y-=dy/d*f;
  }
  // Separate nearby nodes without pulling the layout back to its original shape.
  const ids=Object.keys(state.positions);
  for(let i=0;i<ids.length;i++)for(let j=i+1;j<ids.length;j++){
    const a=state.positions[ids[i]],b=state.positions[ids[j]];
    let dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy);
    if(d>=58)continue;
    if(d<.01){dx=Math.cos((i+j)*2.4);dy=Math.sin((i+j)*2.4);d=1;}
    const push=(58-d)*.065;
    forces[ids[i]].x-=dx/d*push;forces[ids[i]].y-=dy/d*push;
    forces[ids[j]].x+=dx/d*push;forces[ids[j]].y+=dy/d*push;
  }
  let energy=0;
  for(const [id,p] of Object.entries(state.positions)){
    const v=motion.velocities[id]||(motion.velocities[id]={x:0,y:0});
    if(id===motion.pinned){v.x=0;v.y=0;continue;}
    v.x=(v.x+forces[id].x*dt)*Math.pow(.8,dt);v.y=(v.y+forces[id].y*dt)*Math.pow(.8,dt);
    p.x+=v.x*dt;p.y+=v.y*dt;energy+=v.x*v.x+v.y*v.y;
  }
  paintGraphPositions();motion.frames++;
  if((energy>.002||motion.pinned)&&motion.frames<600)motionFrame=requestAnimationFrame(stepGraphMotion);
}
function highlightNeighborhood(id){
  const svg=$('#graph');svg.classList.toggle('has-highlight',Boolean(id));
  const neighbors=new Set([id]);
  for(const e of state.visibleEdges||state.graph.edges){
    if(e.subject===id)neighbors.add(e.object);if(e.object===id)neighbors.add(e.subject);
  }
  svg.querySelectorAll('[data-node]').forEach(el=>el.classList.toggle('highlighted',neighbors.has(el.dataset.node)));
  svg.querySelectorAll('[data-edge]').forEach(el=>{
    const e=(state.visibleEdges||state.graph.edges).find(e=>e.id===el.dataset.edge);
    el.classList.toggle('highlighted',e.subject===id||e.object===id);
  });
}
let graphViewport={x:0,y:0,w:800,h:680};
function applyViewport(){const v=graphViewport;$('#graph').setAttribute('viewBox',`${v.x} ${v.y} ${v.w} ${v.h}`);}
const graphCanvas=$('#graph');
graphCanvas.addEventListener('wheel',e=>{
  e.preventDefault();const point=graphCanvas.createSVGPoint();point.x=e.clientX;point.y=e.clientY;
  const p=point.matrixTransform(graphCanvas.getScreenCTM().inverse()),v=graphViewport;
  const w=Math.max(200,Math.min(2000,v.w*Math.exp(e.deltaY*.001))),scale=w/v.w;
  graphViewport={x:p.x-(p.x-v.x)*scale,y:p.y-(p.y-v.y)*scale,w,h:v.h*scale};applyViewport();
},{passive:false});
let canvasPan=null;
graphCanvas.addEventListener('pointerdown',e=>{
  if(e.button!==0||e.target.closest('[data-node],[data-edge]'))return;
  canvasPan={x:e.clientX,y:e.clientY,matrix:graphCanvas.getScreenCTM().inverse(),view:{...graphViewport}};
  graphCanvas.setPointerCapture(e.pointerId);graphCanvas.classList.add('panning');
});
graphCanvas.addEventListener('pointermove',e=>{
  if(!canvasPan)return;const m=canvasPan.matrix,dx=e.clientX-canvasPan.x,dy=e.clientY-canvasPan.y;
  graphViewport={...canvasPan.view,x:canvasPan.view.x-dx*m.a-dy*m.c,y:canvasPan.view.y-dx*m.b-dy*m.d};applyViewport();
});
for(const event of ['pointerup','pointercancel'])graphCanvas.addEventListener(event,()=>{canvasPan=null;graphCanvas.classList.remove('panning');});
function bindActivate(el,fn) { el.addEventListener('click',fn); el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();fn();}}); }
function select(type,id) {
  $('#technical-details').open=true;state.selectionType=type;state.selected=id;state.detail='connection';renderDetails();
  // Selection preserves the SVG elements, pointer hover and keyboard focus.
  $('#graph').querySelectorAll('[data-node],[data-edge]').forEach(el=>{
    el.classList.toggle('selected',type==='node'?el.dataset.node===id:el.dataset.edge===id);
  });
}
function selectedEdges() {
  const route=state.visibleEdges?.find(e=>e.id===state.selected&&e.path);
  return state.graph.edges.filter(e=>state.selectionType==='edge'?(route?route.path.includes(e.id):e.id===state.selected):e.subject===state.selected||e.object===state.selected);
}
function citation(id) {
  const source = state.graph.sources.find(s=>s.id===id);
  if(source)return link(source.url,source.name);
  const edge=state.graph.edges.find(e=>e.id===id);
  if(edge)return `<button class="text-button" data-select-edge="${esc(id)}">${esc(pretty(edge.relation))}</button>`;
  const live=state.report?.live;
  const record=[...(live?.papers||[]),...(live?.studies||[])].find(p=>p.id===id);
  return record?link(record.url,id):esc(id);
}
function renderDetails() {
  if(!state.graph)return;
  document.querySelectorAll('[data-detail]').forEach(b=>b.classList.toggle('active',b.dataset.detail===state.detail));
  const container=$('#details');
  if(state.detail==='actions') { renderActions();return; }
  const edges=selectedEdges();
  const route=state.selectionType==='edge'&&state.visibleEdges?.find(e=>e.id===state.selected&&e.path);
  if(route&&state.detail==='connection'){
    container.innerHTML=`<div class="detail-header"><h2>Path through hidden nodes</h2><p>${esc(route.explanation)}</p><p>This line summarizes an existing path, not a direct relationship.</p></div>`+route.path.map(id=>{
      const e=state.graph.edges.find(e=>e.id===id),node=id=>state.graph.nodes.find(n=>n.id===id);
      return `<div class="detail-block"><strong>${esc(node(e.subject).label)} → ${esc(node(e.object).label)}</strong><p>${esc(e.explanation)}</p>${(e.evidence||[]).map(ev=>citation(ev.source_id)).join(' · ')}</div>`;
    }).join('');
    return;
  }
  if(state.detail==='evidence') {
    const sources = new Map();
    edges.forEach(e=>e.evidence.forEach(ev=>{if(!sources.has(ev.source_id))sources.set(ev.source_id,{source:state.graph.sources.find(s=>s.id===ev.source_id),locators:new Set()});sources.get(ev.source_id).locators.add(ev.locator);}));
    container.innerHTML=`<div class="detail-header"><span class="eyebrow">FOLLOW THE SOURCE</span><h2>Evidence you can inspect</h2><p>${state.selectionType==='edge'?'Sources for the selected connection.':'Sources for the selected node’s visible connections.'} Copies of one paper count as one source.</p></div>`+
      edges.map(e=>`<div class="detail-block"><strong>${esc(pretty(e.relation))}</strong>${badge(e.status)}<p>${esc(e.explanation)}</p><p class="small">${esc(e.assessment.flags.join(' · '))}</p></div>`).join('')+
      [...sources.values()].map(({source:s,locators})=>`<article class="source-card"><h3>${esc(s.name)}</h3>${link(s.url,'Open source')}<p>${esc([...locators].join('; '))}</p><small>${s.published_at?'Source date: '+esc(s.published_at)+' · ':''}Reviewed: ${esc(s.reviewed_at)}</small><small>Source lineage: ${esc(s.family)}</small></article>`).join('');
  } else if(state.selectionType==='edge') {
    const e=edges[0];
    if(!e){container.textContent='This connection is hidden by the current filters.';return;}
    const a=state.graph.nodes.find(n=>n.id===e.subject), b=state.graph.nodes.find(n=>n.id===e.object);
    container.innerHTML=`<div class="detail-header"><span class="eyebrow">WHY THIS CONNECTION EXISTS</span><h2>${esc(a.label)} <span aria-hidden="true">→</span> ${esc(b.label)}</h2>${badge(e.status)}${badge(e.confidence+' confidence')}</div><div class="detail-block"><span class="label">Relationship</span><strong>${esc(pretty(e.relation))}</strong><p>${esc(e.explanation)}</p></div>${e.caveat?`<p class="caveat">${esc(e.caveat)}</p>`:''}<div class="detail-block"><span class="label">Evidence checks</span><p>${e.assessment.source_count} cited sources · ${e.assessment.source_families.length} source lineages</p><p class="small">${esc(e.assessment.flags.join(' · '))}</p><p class="small">${esc(e.confidence_basis)}</p></div><button class="secondary wide" data-open-evidence>Inspect supporting sources →</button><div class="detail-block"><span class="label">Explore either end</span><button class="connection-link" data-select-node="${esc(a.id)}">${esc(a.label)} →</button><button class="connection-link" data-select-node="${esc(b.id)}">${esc(b.label)} →</button></div>`;
  } else {
    const n=state.graph.nodes.find(n=>n.id===state.selected);
    if(!n)return;
    const assets=edges.filter(e=>state.graph.nodes.find(x=>x.id===(e.subject===n.id?e.object:e.subject))?.kind==='asset').length;
    container.innerHTML=`<div class="detail-header"><span class="eyebrow">SELECTED ${esc(n.kind.toUpperCase())}</span><h2>${esc(n.label)}</h2>${badge(n.cluster)}${n.affiliation?`<p>${esc(n.affiliation)}</p>`:n.description&&!['organization','asset','institution','researcher'].includes(n.kind)?`<p>${esc(n.description)}</p>`:''}</div><div class="detail-block"><span class="label">Stable identifier</span><p>${esc(n.id)}</p>${['organization','asset','institution','researcher'].includes(n.kind)?'':n.identity_note?`<p class="small">${esc(n.identity_note)}</p>`:''}${n.url?link(n.url,'Visit source'):''}</div>${n.study_status?`<p class="caveat">${esc(pretty(n.study_status))}. Last updated ${esc(n.last_updated)}. Refresh the study record before discussing participation.</p><div class="detail-block"><span class="label">Study evidence</span><p>${n.results_posted?'Results posted in the downloaded record.':'No results posted in the downloaded record.'} Registration is not proof of benefit.</p></div><details><summary>View registry eligibility criteria</summary><p>${esc(n.eligibility)}</p></details>`:''}<div class="detail-block"><span class="label">Connections in this map</span><strong>${n.degree} documented connections</strong><p class="small">Degree centrality: ${Math.round(n.centrality*100)} / 100. This measures map connectivity, not medical importance.</p></div>${assets?`<div class="detail-block"><span class="label">Existing assets</span><strong>${assets} registry connection${assets>1?'s':''}</strong></div>`:''}<div class="detail-block"><span class="label">Explore connections</span><div class="detail-list">${edges.map(e=>{const other=state.graph.nodes.find(x=>x.id===(e.subject===n.id?e.object:e.subject));return `<button class="connection-link" data-select-edge="${esc(e.id)}">${esc(shorten(other.label,58))}<span>${esc(pretty(e.relation))} · ${esc(e.status)}</span></button>`;}).join('')}</div></div><button class="secondary wide" data-open-actions>Find a next research step →</button>`;
  }
  bindDetails();
}
function bindDetails() {
  $('#details').querySelectorAll('[data-select-edge]').forEach(b=>b.addEventListener('click',()=>select('edge',b.dataset.selectEdge)));
  $('#details').querySelectorAll('[data-select-node]').forEach(b=>b.addEventListener('click',()=>select('node',b.dataset.selectNode)));
  $('#details').querySelector('[data-open-evidence]')?.addEventListener('click',()=>{state.detail='evidence';renderDetails();});
  $('#details').querySelector('[data-open-actions]')?.addEventListener('click',()=>{state.detail='actions';renderDetails();if(!state.report)runReview();});
}
function renderActions() {
  const r=state.report;
  if(!r) { $('#review-output').innerHTML='<p class="small">For patients, families and advocates like Maria: understand the condition, what research has found, and how far possible treatments have progressed. Explore what may be feasible, what is still uncertain, and questions to discuss with your care team — with links to the sources.</p>';return; }
  $('#review-output').innerHTML=`<div class="detail-header"><span class="eyebrow">PAPERS, FEASIBILITY & RISKS</span><h2>What the evidence means for you</h2>${badge(r.mode)}<p>${esc(r.agent_review?.summary || r.summary)}</p><p class="small">${esc(r.audience || r.role)}</p></div>${r.agent_error?`<p class="caveat">${esc(r.agent_error)}</p>`:''}`+
    (r.agent_review?[]:r.actions).map((a,i)=>`<article class="action-card"><div class="when">${i+1}. ${esc(a.when.toUpperCase())}</div><h3>${esc(a.title)}</h3><p>${esc(a.step)}</p><p class="caveat">${esc(a.check)}</p><p>${a.path.map(id=>citation(id)).join('<br>')}</p></article>`).join('')+
    (r.agent_review?`<div class="detail-block"><span class="label">What the papers say &amp; risks to consider</span><p>${esc(r.agent_review.summary)}</p>${r.agent_review.findings.map(f=>`<article class="source-card">${badge(f.status)}<p>${esc(f.statement)}</p><p>${esc(f.limitations)}</p><p>${f.citation_ids.map(citation).join('<br>')}</p></article>`).join('')}<h3>Feasibility &amp; next steps</h3>${r.agent_review.actions.map(f=>`<article class="source-card">${badge(f.status)}<p>${esc(f.statement)}</p><p>${esc(f.limitations)}</p><p>${f.citation_ids.map(citation).join('<br>')}</p></article>`).join('')}<p class="small">${esc(r.agent_review.missing_evidence.join(' · '))}</p></div>`:'')+
    `<a class="secondary wide export" href="/api/reports/${esc(r.id)}/proposal" download="research-proposal.md">Download sourced proposal ↓</a><div class="detail-block"><span class="label">What still needs validation</span>${r.coverage.gaps.map(g=>`<p class="small">• ${esc(g)}</p>`).join('')}<p class="small">No outreach has been sent. ${esc(r.limitations[0])}</p></div>`;
  $('#review-output').querySelectorAll('[data-select-edge]').forEach(b=>b.addEventListener('click',()=>{$('#graph-optional').open=true;select('edge',b.dataset.selectEdge);}));
}
function renderPapers() {
  if(!state.graph)return;
  const papers=state.graph.nodes.filter(n=>n.kind==='paper');
  $('#paper-list').innerHTML = papers.length?papers.map(p=>`<article class="paper-card"><div class="paper-meta">${esc(p.year)} · ${esc(p.id)} ${badge('indexed reading lead')}</div><h3>${esc(p.label)}</h3><p>${esc(shorten(p.authors||'',160))}</p>${link(p.url,'Read publication')} <button class="text-button" data-paper="${esc(p.id)}">View graph connection</button></article>`).join(''):`<p class="empty">No publication nodes in this filtered neighborhood. Public-source search can retrieve additional reading candidates.</p>`;
  $('#paper-list').querySelectorAll('[data-paper]').forEach(b=>b.addEventListener('click',()=>{select('node',b.dataset.paper);setView('network');}));
  renderLive();
}
function renderLive() {
  const live=state.live;
  if(!live){$('#live-results').innerHTML='';return;}
  $('#live-results').innerHTML=`<div class="live-banner"><strong>Retrieved candidates · ${esc(live.query)} · not validated claims</strong><p>${esc(live.coverage)}</p><p>${esc(live.independence_note)}</p><small>Retrieved ${esc(live.retrieved_at.slice(0,10))}${live.cached?' · cached for up to one hour':''}</small></div><p class="small">${live.providers.map(p=>esc(p.provider)+': '+esc(p.status)+(p.count!==undefined?' ('+p.count+')':'')).join(' · ')}</p>`+
    (live.identities.length?`<details><summary>${live.identities.length} public identity candidates</summary>${live.identities.map(x=>`<p>${link(x.url,x.label)} · ${esc(x.id)}<br><small>Identity match requires review; not added to the graph.</small></p>`).join('')}</details>`:'')+
    live.papers.map(p=>`<article class="paper-card"><div class="paper-meta">${esc(p.year||'')} · ${esc(p.id)} ${badge(p.preprint?'preprint':'unreviewed candidate')}</div><h3>${esc(p.title)}</h3><p class="paper-meta">Found in ${esc(p.seen_in.join(' + '))} · one publication lineage</p>${link(p.url,'Inspect paper')}<details><summary>Read retrieved abstract</summary><p>${esc(p.abstract)}</p></details></article>`).join('')+
    live.studies.map(t=>`<article class="paper-card"><div class="paper-meta">${esc(t.id)} ${badge(pretty(t.status))}</div><h3>${esc(t.title)}</h3><p>${esc(t.conditions.join('; '))}</p><p>Personal eligibility has not been assessed. Registration does not prove efficacy.</p>${link(t.url,'Inspect study')}</article>`).join('')+
    (!live.papers.length&&!live.studies.length?`<p class="empty">No reading or study candidates returned. Check provider status above; no results does not mean no evidence exists.</p>`:'')+
    `<details><summary>Filtering log (${live.excluded.length} excluded records)</summary>${live.excluded.map(x=>`<p>${esc(x.id)} · ${esc(pretty(x.reason))}</p>`).join('')||'<p>No records excluded.</p>'}</details>`;
}
function setView(view) { state.view=view;$('#network-view').hidden=view!=='network';$('#papers-view').hidden=view!=='papers';$('#network-tab').classList.toggle('active',view==='network');$('#papers-tab').classList.toggle('active',view==='papers');$('#fit').hidden=view!=='network'; }
async function search(query) {
  state.query=query;$('#search').value=query;
  const serial=++state.request;
  const button=$('#search-form button[type="submit"]');button.disabled=true;
  $('#progress').classList.remove('error');$('#progress').textContent='Searching public databases and assembling a live graph…';
  $('#identity').textContent='Building live evidence map for '+query+'…';
  try {
    const graph=await api('/api/live-graph',{query,min_confidence:$('#confidence').value,include_inferred:$('#hypotheses').checked});
    if(serial!==state.request)return;
    displayGraph(graph);setView('network');
    $('#progress').textContent='Live graph ready. Search relationships and automated mentions still need scientific review.';
    const box=$('#search-results');box.hidden=graph.identity_resolved;
    box.innerHTML='<p>Identity is unresolved or ambiguous. This graph is search context, not a confirmed diagnosis. Choose a term to refine it:</p>'+graph.live.identities.slice(0,10).map(n=>`<button class="match" data-identity="${esc(n.id)}">${esc(n.label)}<small>${esc(n.id)}</small></button>`).join('');
    if(!graph.live.identities.length)box.innerHTML='<p>No identity was resolved. The graph shows available search records; confirm the disease, gene, or symptom name before interpreting it.</p>';
    box.querySelectorAll('[data-identity]').forEach(b=>b.addEventListener('click',async()=>{
      try{const refined=await api('/api/live-graph',{query,identity_id:b.dataset.identity,...{min_confidence:$('#confidence').value,include_inferred:$('#hypotheses').checked}});displayGraph(refined);box.hidden=true;}catch(error){showError(error);}
    }));
  } catch(error){showError(error);$('#identity').textContent='Live graph unavailable; previous map remains visible.';}
  finally{button.disabled=false;}
}
async function retrieveLive(query=null) {
  const button=$('#live-papers');button.disabled=true;button.textContent='Searching trusted sources…';
  setView('papers');
  const node=state.graph?.nodes.find(n=>n.id===state.graph.focus);
  try { state.live=await api('/api/live-search',{query:query||node?.gene||node?.label||state.query});renderLive(); }
  catch(error){showError(error);}
  finally{button.disabled=false;button.textContent='Search public sources ↗';}
}
let reviewing=false;
async function runReview() {
  if(reviewing)return;
  reviewing=true;const button=$('#review');button.disabled=true;button.textContent='Reviewing…';
  const snapshot=state.graph;
  const audienceRole=$('#audience-role').value, reportLanguage=$('#language').value;
  const progress=$('#progress');progress.classList.remove('error');
  const names={filter:'Filtering evidence…',retrieve:'Retrieving bounded paper and study candidates…',audit:'Checking provenance and visible limitations…',extract:'Agent is reviewing the filtered evidence…',critic:'Agent is challenging the draft and checking citations…',complete:'Review complete.'};
  try {
    let job=await api('/api/analysis',{...options(),role:audienceRole,language:reportLanguage,use_live:$('#use-live').checked,use_agent:$('#use-openai').checked});
    while(!['complete','failed'].includes(job.status)) {
      progress.textContent=names[job.stage]||'Review queued…';
      await new Promise(resolve=>setTimeout(resolve,900));
      job=await api('/api/jobs/'+job.id);
    }
    if(job.status==='failed')throw new Error(job.error);
    const report=await api('/api/reports/'+job.report_id);
    if(audienceRole!==$('#audience-role').value || reportLanguage!==$('#language').value){progress.textContent='Review saved for the previous audience. Review again for the current selection.';return;}
    if(snapshot!==state.graph){progress.textContent='Review saved for the previous map. Run a review for the current search.';return;}
    state.report=report;if(report.live){state.live=report.live;renderLive();}
    renderActions();$('#review-output').scrollIntoView({behavior:'smooth',block:'nearest'});
    progress.textContent=report.agent_review?'Source checks and agent critical review complete. Human validation is still needed.':'Evidence checks complete. No model review was run.';
  } catch(error){showError(error);}
  finally{reviewing=false;button.disabled=false;button.textContent='Help me understand';}
}
async function showCoverage() {
  try{
    const c=state.graph?.coverage||await api('/api/coverage');
    // Every label, number and sentence sits in its own element so i18n.js can translate each text node whole.
    const tone=status=>/unavailable/.test(status)?'warn':/next/.test(status)?'planned':/live/.test(status)?'live':'curated';
    const m=c.moonshot, stat=(label,days,cls)=>`<div class="stat ${cls}"><span class="stat-label">${label}</span><span class="stat-value"><b>${days}</b><span>days</span></span></div>`;
    $('#coverage-content').innerHTML=`<p class="coverage-scope">${esc(c.scope)}</p>`+
      `<section class="coverage-section"><h3>Data sources</h3><div class="source-grid">`+c.sources.map(s=>`<article class="source-tile ${tone(s.status)}"><div class="source-head"><strong>${esc(s.name)}</strong><span class="source-status"><i aria-hidden="true"></i><span>${esc(pretty(s.status))}</span></span></div><p>${esc(s.use)}</p></article>`).join('')+`</div></section>`+
      `<section class="coverage-section"><h3>Known gaps</h3><ul class="gap-list">${c.gaps.map(g=>`<li>${esc(g)}</li>`).join('')}</ul></section>`+
      `<section class="coverage-section moonshot"><h3>The 10× planning hypothesis</h3><p class="moonshot-goal">${esc(m.milestone)}</p>`+
      `<div class="moonshot-stats">${stat('Baseline',m.baseline_days,'')}<span class="stat-arrow" aria-hidden="true">→</span>${stat('Proposed',m.proposed_days,'target')}<span class="stat-factor">${m.factor}×</span></div>`+
      `<p class="moonshot-status">${esc(m.status)}</p><h4>Assumptions</h4><ul class="check-list">${m.assumptions.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><h4>How to validate</h4><p>${esc(m.validation)}</p></section>`+
      `<p class="coverage-foot"><span>${state.graph?.excluded.length||0} graph edges excluded by current filters.</span><span>Reviewed ${esc(c.reviewed_at)}</span></p>`;
    $('#coverage-dialog').showModal();
  }catch(error){showError(error);}
}
$('#search-form').addEventListener('submit',e=>{e.preventDefault();search($('#search').value.trim());});
document.querySelectorAll('.example').forEach(b=>b.addEventListener('click',()=>search(b.dataset.query)));
$('#confidence').addEventListener('change',()=>loadGraph(state.graph.focus));
$('#hypotheses').addEventListener('change',()=>loadGraph(state.graph.focus));
$('#network-tab').addEventListener('click',()=>setView('network'));
$('#papers-tab').addEventListener('click',()=>setView('papers'));
$('#fit').addEventListener('click',()=>{graphViewport={x:0,y:0,w:800,h:680};applyViewport();});
$('#live-papers').addEventListener('click',()=>retrieveLive());
$('#review').addEventListener('click',runReview);
document.querySelectorAll('[data-detail]').forEach(b=>b.addEventListener('click',()=>{state.detail=b.dataset.detail;renderDetails();}));
$('#coverage-open').addEventListener('click',showCoverage);
$('#coverage-close').addEventListener('click',()=>$('#coverage-dialog').close());
// Home: a single search box. A search (or the example map) opens the full workspace as the detail view.
// The query lives in the address (#q=...), so Back returns home and a shared link opens the detail directly.
function showHome(){document.body.classList.add('is-home');$('#home-search').value='';$('#home-search').focus();}
function openDetail(query){
  document.body.classList.remove('is-home');window.scrollTo(0,0);
  if(query)search(query);
}
function goSearch(query){
  query=(query||'').trim();if(!query)return $('#home-search').focus();
  history.pushState({q:query},'','#q='+encodeURIComponent(query));openDetail(query);
}
const hashQuery=()=>{const m=/^#q=(.*)$/.exec(location.hash);return m?decodeURIComponent(m[1]):null;};
$('#home-form').addEventListener('submit',e=>{e.preventDefault();goSearch($('#home-search').value);});
document.querySelectorAll('.home-q').forEach(b=>b.addEventListener('click',()=>goSearch(b.dataset.query)));
$('#home-example').addEventListener('click',()=>{history.pushState({example:true},'','#example');openDetail(null);});
$('#brand-home').addEventListener('click',e=>{e.preventDefault();history.pushState({},'',location.pathname);showHome();});
window.addEventListener('popstate',()=>{const q=hashQuery();if(q)openDetail(q);else if(location.hash==='#example')openDetail(null);else showHome();});
async function init(){
  try{state.health=await api('/api/health');const configured=state.health.agent?.configured;$('#use-openai').disabled=!configured;$('#use-openai').checked=configured;$('#agent-status').textContent=configured?'('+state.health.agent.provider+' available)':'(not configured)';}catch(error){showError(error);}
  const q=hashQuery();
  if(q)document.body.classList.remove('is-home');else if(location.hash==='#example')openDetail(null);else showHome();
  await loadGraph('MONDO:0012812');   // the starter map loads first, so a live search always replaces it rather than racing it
  if(q)openDetail(q);
}
init();

for (const selector of ['#audience-role', '#language']) $(selector).addEventListener('change', () => { state.report = null; if(state.graph){renderDetails();renderActions();} $('#progress').textContent = 'Review again to generate a report for the selected audience and language.'; });

let outreachLeads=null, leadRequest=0;
async function loadLeads(){
  const serial=++leadRequest, graph=state.graph;
  $('#community-results').textContent='Finding community connections...';$('#research-results').textContent='';
  try{
    const leads=await api('/api/leads?'+new URLSearchParams(options()));
    if(serial!==leadRequest||graph!==state.graph)return;
    outreachLeads=leads;renderLeads();
  }catch(error){if(serial===leadRequest){$('#community-results').textContent='Community results could not be loaded. Please search again.';}}
}
function renderLeads(){
  if(!outreachLeads)return;

  for(const [key,selector,title] of [['communities','#community-results','Communities to connect with'],['research','#research-results','Researchers & institutions to reach out to']]){
    const container=$(selector);container.hidden=!$('#show-'+key).checked;
    const values=outreachLeads[key].filter(n=>($('#show-indirect').checked||!n.indirect)&&($('#show-no-contact').checked||n.email||n.phone||n.contact_url));
    const cards=values.map((n,i)=>{
      const avatar=n.image?`<img class="lead-image" src="${esc(n.image)}" alt="${esc(n.label)}" loading="lazy">`:`<span class="lead-avatar" aria-hidden="true">${esc(n.label.split(/\s+/).slice(0,2).map(x=>x[0]).join(''))}</span>`;
      const email=n.email&&/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(n.email)?`<a href="mailto:${esc(encodeURIComponent(n.email))}">${esc(n.email)}</a>`:'';
      const phone=n.phone?`<span>Phone: ${esc(n.phone)}</span>`:'';
      return `<article class="lead-card"><div class="lead-main"><div class="lead-title">${avatar}<div><span class="lead-rank">${i+1} &middot; ${esc(pretty(n.kind))}</span><h3>${esc(n.label)}</h3></div></div>${leadDescription(n)}${n.affiliation?`<p>${esc(n.affiliation)}</p>`:''}<div class="lead-links">${n.website?link(n.website,'Website / source record'):''}${n.contact_url?link(n.contact_url,'Contact page / study contact'):''}${email}${phone}</div><details><summary>Sources & connection</summary>${n.citations.map(c=>`<p>${link(c.url,c.name)}</p>`).join('')}<button class="text-button" data-inspect-lead="${esc(n.id)}">View in graph</button></details></div>${leadCriteria(n)}</article>`;
    });
    container.innerHTML=`<div class="lead-section-heading"><h3>${title}</h3><span>${values.length} sourced leads</span></div>`+(cards.length?cards.slice(0,3).join('')+(cards.length>3?`<details class="more-leads"><summary>Show ${cards.length-3} more</summary>${cards.slice(3).join('')}</details>`:''):'<p class="empty">No sourced leads match these filters in the current coverage. Try including indirect connections or search a disease or gene.</p>');
    if(values.length){
      container.innerHTML=`<div class="lead-section-heading"><h3>${title}</h3><span>${values.length} sourced leads</span></div><div class="research-gallery">${values.slice(0,3).map((n,i)=>researchTile(n,i,key)).join('')}</div><button class="find-more secondary" type="button">Find out more <span aria-hidden="true">→</span></button>`;
      container.querySelector('.find-more').addEventListener('click',()=>{
        $('#research-dialog-title').textContent=title;
        $('#research-list').innerHTML=cards.join('');
        bindLeadInspection($('#research-list'));
        $('#research-dialog').showModal();
      });
      container.querySelectorAll('.research-tile-toggle').forEach(button=>button.addEventListener('click',()=>{
        const tile=button.closest('.research-tile'),open=tile.classList.toggle('is-open');
        button.setAttribute('aria-expanded',String(open));
      }));
      container.querySelectorAll('.research-tile').forEach(tile=>tile.addEventListener('keydown',e=>{if(e.key==='Escape'){tile.classList.remove('is-open');tile.querySelector('button').setAttribute('aria-expanded','false');tile.querySelector('button').blur();}}));
    }
    bindLeadInspection(container);
  }
}
function leadDescription(n){
  if(!n.description)return '';
  return `<p class="lead-description">${esc(n.description)}</p>${n.description_source?`<p class="lead-description-source">${link(n.description_source,'About this community')}</p>`:''}`;
}
function leadCriteria(n){
  return `<div class="criteria" ${$('#show-criteria').checked?'':'hidden'}><span class="eyebrow">OUTREACH RANK</span><strong>${n.score}<small> / 100</small></strong>${n.criteria.map(c=>`<div class="criterion"><div><span>${esc(c.label)}</span><span>${c.value}</span></div><svg class="criterion-track" viewBox="0 0 100 5" preserveAspectRatio="none" aria-label="${esc(c.label)}: ${c.value} / 100"><rect width="100" height="5" class="criterion-background"/><rect width="${c.value}" height="5" class="criterion-value"/></svg></div>`).join('')}</div>`;
}
function researchTile(n,i,key){
  const initials=n.label.split(/\s+/).slice(0,2).map(x=>x[0]).join('');
  const email=n.email&&/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(n.email)?`<a href="mailto:${esc(encodeURIComponent(n.email))}">${esc(n.email)}</a>`:'';
  return `<article class="research-tile ${i===0?'featured':''}"><div class="research-art"><span class="research-monogram" aria-hidden="true">${esc(initials)}</span><span class="image-unavailable">${n.kind==='researcher'?'Photo unavailable':'Logo unavailable'}</span>${n.image?`<img src="${esc(n.image)}" alt="${esc(n.label)}" loading="lazy">`:''}</div><button class="research-tile-toggle" type="button" aria-expanded="false" aria-controls="${key}-info-${i}"><strong>${esc(n.label)}</strong></button><div class="research-hover" id="${key}-info-${i}"><div class="research-hover-content">${n.affiliation?`<p>${esc(n.affiliation)}</p>`:''}${leadCriteria(n)}<div class="lead-links">${n.website?link(n.website,'Website / source record'):''}${n.contact_url?link(n.contact_url,'Contact page / study contact'):''}${email}${n.phone?`<span>Phone: ${esc(n.phone)}</span>`:''}</div><details><summary>Sources & connection</summary>${n.citations.map(c=>`<p>${link(c.url,c.name)}</p>`).join('')}<button class="text-button" data-inspect-lead="${esc(n.id)}">View in graph</button></details></div></div></article>`;
}
function bindLeadInspection(container){
  container.querySelectorAll('[data-inspect-lead]').forEach(button=>button.addEventListener('click',()=>{if($('#research-dialog').open)$('#research-dialog').close();$('#graph-optional').open=true;$('#graph-science').checked=true;drawGraph();select('node',button.dataset.inspectLead);$('#graph-optional').scrollIntoView({behavior:'smooth'});}));
  container.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.hidden=true;}));
}
$('#research-close').addEventListener('click',()=>$('#research-dialog').close());
// Scroll to the AI guide without touching the URL hash (the hash carries the search query; popstate would go home).
$('#ai-jump-icon').addEventListener('click',()=>{const guide=$('#ai-guide');guide.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});guide.focus({preventScroll:true});});
for(const id of ['communities','research','indirect','no-contact','criteria'])$('#show-'+id).addEventListener('change',renderLeads);
$('#expand-graph').addEventListener('click',()=>{const panel=$('#graph-optional'),expanded=panel.classList.toggle('expanded');$('#expand-graph').setAttribute('aria-pressed',String(expanded));$('#expand-graph').textContent=expanded?'Restore workspace size':'Enlarge graph workspace';});
$('#graph-science').addEventListener('change',()=>{state.positions={};drawGraph();});
// Experts start with the graph open; patients and families start with people and the AI guide.
$('#audience-role').addEventListener('change',()=>{$('#graph-optional').open=$('#audience-role').value==='expert';});
