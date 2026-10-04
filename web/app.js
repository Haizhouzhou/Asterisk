/* Dependency-free UI; all research content comes from the backend API. */
'use strict';
const $ = (selector) => document.querySelector(selector);
const state = { graph: null, selected: null, selectionType: 'node', detail: 'connection', report: null, live: null, view: 'network', positions: {}, health: null, request: 0, query: 'STXBP1' };
const colors = {'Vesicle release':'#3f7e87','GABA reuptake':'#83a68c','Shared observations':'#a691b1','Shared infrastructure':'#d9b362','Published evidence':'#8c9caf','Diseases':'#3f7e87','Genes':'#83a68c','Phenotypes':'#a691b1','Studies':'#d9b362','Publications':'#8c9caf','Investigators':'#c07966','Variants':'#ad83a6','Search context':'#243746'};
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const shorten = (value, n=30) => value.length > n ? value.slice(0,n-1) + '…' : value;
const pretty = value => String(value || '').replaceAll('_',' ');
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
    state.graph = graph; state.selected = focus; state.selectionType = 'node'; state.report = null; state.live = graph.live||null; state.positions = {};
    const node = graph.nodes.find(n => n.id === focus);
    $('#identity').textContent = node.label + ' · ' + node.id;
    $('#graph-count').textContent = `${graph.nodes.length} nodes · ${graph.edges.length} connections`;
    $('#map-status').textContent = `${graph.edges.filter(e=>e.status==='observed').length} documented · ${graph.edges.filter(e=>e.status==='inferred').length} proposed`;
    $('#cluster-list').innerHTML = graph.clusters.map(c=>`<div class="cluster-item"><svg class="dot" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="5" fill="${colors[c.name]||'#98a8a4'}"/></svg><span>${esc(c.name)}</span><span class="cluster-count">${c.count}</span></div>`).join('');
    $('#progress').textContent = ''; $('#progress').classList.remove('error');
    drawGraph(); renderDetails(); renderPapers();
    const note=$('.scope-note');
    if(graph.graph_id)note.innerHTML='<span class="status-dot"></span><div>Live research graph<small>'+esc(graph.live.query)+'<br>Retrieved '+esc(graph.live.retrieved_at.slice(0,10))+'</small></div>';
}

function layout() {
  const graph = state.graph;
  const preferred = {
    'MONDO:0012812':[250,285], 'atlas:disease:slc6a1-ndd':[550,285],
    'NCBIGene:6812':[110,135], 'NCBIGene:6529':[690,135],
    'atlas:mechanism:vesicle':[135,225], 'atlas:mechanism:gaba':[665,225],
    'HP:0001250':[400,465], 'HP:0001263':[520,425], 'HP:0001252':[280,425],
    'atlas:org:stx':[90,345], 'atlas:org:slc':[710,345],
    'atlas:asset:simons':[400,340], 'NCT:04937062':[400,185],
    'atlas:institution:cornell':[400,75],
    'PMID:26865513':[90,490], 'atlas:author:26865513:0':[75,585],
    'PMID:38137001':[255,540], 'atlas:author:38137001:0':[255,620],
    'PMID:33241211':[710,490], 'atlas:author:33241211:0':[725,585],
    'PMID:38781976':[545,540], 'atlas:author:38781976:0':[545,620]
  };
  const anchors = {'Vesicle release':[210,210], 'GABA reuptake':[600,220], 'Shared observations':[405,440], 'Shared infrastructure':[425,295], 'Published evidence':[365,580], 'Diseases':[150,230], 'Genes':[660,250], 'Phenotypes':[170,400], 'Studies':[570,515], 'Publications':[400,140], 'Investigators':[180,550], 'Variants':[660,400], 'Search context':[400,340]};
  const ids = graph.nodes.map(n=>n.id);
  const nodes = graph.nodes.map((node,i)=> {
    const a = node.id===graph.focus&&graph.graph_id?[400,340]:anchors[node.cluster] || [400,340];
    const p = state.positions[node.id] || (!graph.graph_id&&preferred[node.id] ? {x:preferred[node.id][0],y:preferred[node.id][1]} : null);
    return {...node, x:p?.x ?? a[0] + Math.cos(i*2.4)*75, y:p?.y ?? a[1]+Math.sin(i*2.4)*65, radius: node.id===graph.focus ? 34 : Math.min(22,10+node.degree*1.4), ax:a[0], ay:a[1]};
  });
  const byId = Object.fromEntries(nodes.map(n=>[n.id,n]));
  if (!Object.keys(state.positions).length && (graph.graph_id || nodes.some(n=>!preferred[n.id]))) {
    for (let tick=0; tick<220; tick++) {
      const force = Object.fromEntries(ids.map(id=>[id,{x:0,y:0}]));
      for (let i=0;i<nodes.length;i++) for (let j=i+1;j<nodes.length;j++) {
        const a=nodes[i], b=nodes[j]; let dx=a.x-b.x,dy=a.y-b.y, dist=Math.max(1,Math.hypot(dx,dy));
        const magnitude = 1100/(dist*dist) + Math.max(0,(a.radius+b.radius+47)-dist)*.12;
        force[a.id].x+=dx/dist*magnitude;force[a.id].y+=dy/dist*magnitude;
        force[b.id].x-=dx/dist*magnitude;force[b.id].y-=dy/dist*magnitude;
      }
      for (const edge of graph.edges) {
        const a=byId[edge.subject], b=byId[edge.object]; const dx=b.x-a.x,dy=b.y-a.y,dist=Math.max(1,Math.hypot(dx,dy));
        const mag=(dist-140)*.003;
        force[a.id].x+=dx/dist*mag;force[a.id].y+=dy/dist*mag;
        force[b.id].x-=dx/dist*mag;force[b.id].y-=dy/dist*mag;
      }
      for (const n of nodes) {
        n.x = Math.max(65,Math.min(735,n.x+force[n.id].x+(n.ax-n.x)*.015));
        n.y = Math.max(60,Math.min(610,n.y+force[n.id].y+(n.ay-n.y)*.015));
      }
    }
  }
  state.positions = Object.fromEntries(nodes.map(n=>[n.id,{x:n.x,y:n.y}]));
  return {nodes,byId};
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
  const {nodes,byId} = layout();
  const svg=$('#graph');
  svg.innerHTML = state.graph.edges.map(e=>{
    const a=byId[e.subject],b=byId[e.object];
    return `<g class="edge-group ${state.selectionType==='edge'&&state.selected===e.id?'selected':''}" data-edge="${esc(e.id)}" role="button" tabindex="0" aria-label="${esc(a.label+' to '+b.label+': '+pretty(e.relation))}"><title>${esc(e.explanation)}</title><line class="edge-line ${e.status}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/><line class="edge-hit" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/></g>`;
  }).join('') + nodes.map(n=>`<g class="node ${state.selectionType==='node'&&state.selected===n.id?'selected':''}" data-node="${esc(n.id)}" transform="translate(${n.x},${n.y})" tabindex="0" role="button" aria-label="${esc(n.label+' · '+n.kind)}"><title>${esc(n.label+' · '+n.kind)}</title><circle r="${n.radius}" fill="${colors[n.cluster]||'#98a8a4'}"/>${n.kind==='disease'?`<text class="node-initial" y="5">${esc(n.gene||'D')}</text>`:''}<text class="${n.kind==='disease'?'disease-name':''}" y="${n.radius+18}">${esc(graphLabel(n))}</text><text class="kind-label" y="${n.radius+32}">${esc(n.kind.toUpperCase())}</text></g>`).join('');
  svg.querySelectorAll('[data-edge]').forEach(el=>bindActivate(el,()=>select('edge',el.dataset.edge)));
  svg.querySelectorAll('[data-node]').forEach(el=> {
    bindActivate(el,()=>select('node',el.dataset.node));
    let drag=null,moved=false;
    el.addEventListener('pointerdown',event=>{ if(event.button!==0)return;drag={x:event.clientX,y:event.clientY};moved=false;el.setPointerCapture(event.pointerId); });
    el.addEventListener('pointermove',event=>{
      if(!drag)return;
      if(Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<5&&!moved)return;
      moved=true; const pt=svg.createSVGPoint();pt.x=event.clientX;pt.y=event.clientY;
      const position=pt.matrixTransform(svg.getScreenCTM().inverse());
      state.positions[el.dataset.node]={x:Math.max(30,Math.min(770,position.x)),y:Math.max(35,Math.min(620,position.y))};
      el.setAttribute('transform',`translate(${position.x},${position.y})`);
      // Update lines without replacing the captured pointer element.
      for(const e of state.graph.edges.filter(e=>e.subject===el.dataset.node||e.object===el.dataset.node)) {
        const a=state.positions[e.subject],b=state.positions[e.object];
        const group=Array.from(svg.querySelectorAll('[data-edge]')).find(g=>g.dataset.edge===e.id);
        group.querySelectorAll('line').forEach(line=>{line.setAttribute('x1',a.x);line.setAttribute('y1',a.y);line.setAttribute('x2',b.x);line.setAttribute('y2',b.y);});
      }
    });
    el.addEventListener('pointerup',()=>{drag=null; if(moved) {drawGraph();} });
    el.addEventListener('pointercancel',()=>{drag=null;drawGraph();});
  });
}
function bindActivate(el,fn) { el.addEventListener('click',fn); el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();fn();}}); }
function select(type,id) { state.selectionType=type;state.selected=id;state.detail='connection';renderDetails();drawGraph(); }
function selectedEdges() { return state.graph.edges.filter(e=>state.selectionType==='edge'?e.id===state.selected:e.subject===state.selected||e.object===state.selected); }
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
    container.innerHTML=`<div class="detail-header"><span class="eyebrow">SELECTED ${esc(n.kind.toUpperCase())}</span><h2>${esc(n.label)}</h2>${badge(n.cluster)}<p>${esc(n.description||n.affiliation||'Explore the cited relationships around this '+n.kind+'.')}</p></div><div class="detail-block"><span class="label">Stable identifier</span><p>${esc(n.id)}</p>${n.identity_note?`<p class="small">${esc(n.identity_note)}</p>`:''}${n.url?link(n.url,'Visit source'):''}</div>${n.study_status?`<p class="caveat">${esc(pretty(n.study_status))}. Last updated ${esc(n.last_updated)}. Refresh the study record before discussing participation.</p><div class="detail-block"><span class="label">Study evidence</span><p>${n.results_posted?'Results posted in the downloaded record.':'No results posted in the downloaded record.'} Registration is not proof of benefit.</p></div><details><summary>View registry eligibility criteria</summary><p>${esc(n.eligibility)}</p></details>`:''}<div class="detail-block"><span class="label">Connections in this map</span><strong>${n.degree} documented connections</strong><p class="small">Degree centrality: ${Math.round(n.centrality*100)} / 100. This measures map connectivity, not medical importance.</p></div>${assets?`<div class="detail-block"><span class="label">Existing assets</span><strong>${assets} registry connection${assets>1?'s':''}</strong></div>`:''}<div class="detail-block"><span class="label">Explore connections</span><div class="detail-list">${edges.map(e=>{const other=state.graph.nodes.find(x=>x.id===(e.subject===n.id?e.object:e.subject));return `<button class="connection-link" data-select-edge="${esc(e.id)}">${esc(shorten(other.label,58))}<span>${esc(pretty(e.relation))} · ${esc(e.status)}</span></button>`;}).join('')}</div></div><button class="secondary wide" data-open-actions>Find a next research step →</button>`;
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
  if(!r) { $('#details').innerHTML=`<div class="detail-header"><span class="eyebrow">A PLAN FOR MARIA</span><h2>What can we do this week?</h2><p>Review the filtered evidence to find reusable assets, partners, and questions that still need expert review.</p></div><button class="primary wide" id="detail-review">Review evidence →</button><p class="small">${state.health?.openai_configured?'OpenAI review is available when selected.':'Evidence checks are available. OpenAI review is not configured.'}</p>`;$('#detail-review').addEventListener('click',runReview);return; }
  $('#details').innerHTML=`<div class="detail-header"><span class="eyebrow">A PLAN FOR MARIA</span><h2>A connection worth discussing</h2>${badge(r.mode)}<p>${esc(r.summary)}</p></div>${r.agent_error?`<p class="caveat">${esc(r.agent_error)}</p>`:''}`+
    r.actions.map((a,i)=>`<article class="action-card"><div class="when">${i+1}. ${esc(a.when.toUpperCase())}</div><h3>${esc(a.title)}</h3><p>${esc(a.step)}</p><p class="caveat">${esc(a.check)}</p><p>${a.path.map(id=>citation(id)).join('<br>')}</p></article>`).join('')+
    (r.agent_review?`<div class="detail-block"><span class="label">OpenAI critical review</span><p>${esc(r.agent_review.summary)}</p>${[...r.agent_review.findings,...r.agent_review.actions].map(f=>`<article class="source-card">${badge(f.status)}<p>${esc(f.statement)}</p><p>${esc(f.limitations)}</p><p>${f.citation_ids.map(citation).join('<br>')}</p></article>`).join('')}<p class="small">${esc(r.agent_review.missing_evidence.join(' · '))}</p></div>`:'')+
    `<a class="secondary wide export" href="/api/reports/${esc(r.id)}/proposal" download="research-proposal.md">Download sourced proposal ↓</a><div class="detail-block"><span class="label">What still needs validation</span>${r.coverage.gaps.map(g=>`<p class="small">• ${esc(g)}</p>`).join('')}<p class="small">No outreach has been sent. ${esc(r.limitations[0])}</p></div>`;
  bindDetails();
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
  const progress=$('#progress');progress.classList.remove('error');
  const names={filter:'Filtering evidence…',retrieve:'Retrieving bounded paper and study candidates…',audit:'Checking provenance and visible limitations…',extract:'OpenAI is reviewing the filtered evidence…',critic:'OpenAI is challenging the draft and checking citations…',complete:'Review complete.'};
  try {
    let job=await api('/api/analysis',{...options(),role:'maria',use_live:$('#use-live').checked,use_agent:$('#use-openai').checked});
    while(!['complete','failed'].includes(job.status)) {
      progress.textContent=names[job.stage]||'Review queued…';
      await new Promise(resolve=>setTimeout(resolve,900));
      job=await api('/api/jobs/'+job.id);
    }
    if(job.status==='failed')throw new Error(job.error);
    const report=await api('/api/reports/'+job.report_id);
    if(snapshot!==state.graph){progress.textContent='Review saved for the previous map. Run a review for the current search.';return;}
    state.report=report;if(report.live){state.live=report.live;renderLive();}
    state.detail='actions';renderDetails();
    progress.textContent=report.agent_review?'Source checks and agent critical review complete. Human validation is still needed.':'Evidence checks complete. No model review was run.';
  } catch(error){showError(error);}
  finally{reviewing=false;button.disabled=false;button.innerHTML='Review evidence <span aria-hidden="true">→</span>';}
}
async function showCoverage() {
  try{
    const c=state.graph?.coverage||await api('/api/coverage');
    $('#coverage-content').innerHTML=`<p>${esc(c.scope)}</p>`+c.sources.map(s=>`<article class="source-card"><h3>${esc(s.name)} ${badge(s.status)}</h3><p>${esc(s.use)}</p></article>`).join('')+`<h3>Known gaps</h3><ul>${c.gaps.map(g=>`<li>${esc(g)}</li>`).join('')}</ul><h3>The 10× planning hypothesis</h3><p>${esc(c.moonshot.milestone)}</p><p>${c.moonshot.baseline_days} days → ${c.moonshot.proposed_days} days. ${esc(c.moonshot.status)}</p><ul>${c.moonshot.assumptions.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p>${esc(c.moonshot.validation)}</p><p>${state.graph?.excluded.length||0} graph edges excluded by current filters.</p>`;
    $('#coverage-dialog').showModal();
  }catch(error){showError(error);}
}
$('#search-form').addEventListener('submit',e=>{e.preventDefault();search($('#search').value.trim());});
document.querySelectorAll('.example').forEach(b=>b.addEventListener('click',()=>search(b.dataset.query)));
$('#confidence').addEventListener('change',()=>loadGraph(state.graph.focus));
$('#hypotheses').addEventListener('change',()=>loadGraph(state.graph.focus));
$('#network-tab').addEventListener('click',()=>setView('network'));
$('#papers-tab').addEventListener('click',()=>setView('papers'));
$('#fit').addEventListener('click',()=>{state.positions={};drawGraph();});
$('#live-papers').addEventListener('click',()=>retrieveLive());
$('#review').addEventListener('click',runReview);
document.querySelectorAll('[data-detail]').forEach(b=>b.addEventListener('click',()=>{state.detail=b.dataset.detail;renderDetails();}));
$('#coverage-open').addEventListener('click',showCoverage);
$('#coverage-close').addEventListener('click',()=>$('#coverage-dialog').close());
async function init(){
  try{state.health=await api('/api/health');const configured=state.health.agent?.configured;$('#use-openai').disabled=!configured;$('#use-openai').checked=configured;$('#agent-status').textContent=configured?'('+state.health.agent.provider+' available)':'(not configured)';}catch(error){showError(error);}
  await loadGraph('MONDO:0012812');
}
init();
