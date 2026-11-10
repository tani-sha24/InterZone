let state = null;
const $ = id => document.getElementById(id);
function toast(msg){const t=$("toast");t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),3200)}
async function api(path, options={}) {
  const res=await fetch(path,{headers:{"Content-Type":"application/json"},...options});
  const data=await res.json().catch(()=>({error:"Unexpected server response"}));
  if(!res.ok) throw new Error(data.error||"Request failed");
  return data;
}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function status(s){return `<span class="status ${s.includes("approved")?"approved":s.includes("rejected")?"rejected":"pending"}">${esc(s.replaceAll("_"," "))}</span>`}
function table(headers, rows){if(!rows.length)return `<div class="empty">Nothing to display yet.</div>`;return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`}
async function load(){
  try{
    state=await api("/api/dashboard");const u=state.user;
    $("user-name").textContent=u.full_name;$("user-role").textContent=`${u.title} · ${u.department}`;
    $("avatar").textContent=u.full_name[0];$("first-name").textContent=u.full_name.split(" ")[0];
    $("count-requests").textContent=state.counts.requests;$("count-grants").textContent=state.counts.active_grants;
    $("count-audit").textContent=state.counts.audit_events;$("count-exec").textContent=state.counts.pending_exec;
    renderResources();renderRequests();renderGrants();renderAudit();renderExecutive();
  }catch(e){toast(e.message)}
}
function renderResources(){
  const resources=state.resources;
  $("resource-list").innerHTML=resources.map(r=>`<div class="resource"><div><b>${esc(r.name)}</b><small>${esc(r.department)} · <span class="sensitivity">${esc(r.sensitivity)}</span></small></div><button class="small-btn" onclick="openResource('${esc(r.resource_id)}')">Try access</button></div>`).join("")||'<div class="empty">No resources visible for this identity.</div>';
  const opts=resources.map(r=>`<option value="${esc(r.resource_id)}">${esc(r.name)} — ${esc(r.department)}</option>`).join("");
  $("request-resource").innerHTML=opts;
  $("exec-resource").innerHTML=resources.map(r=>`<option value="${esc(r.resource_id)}">${esc(r.name)} — ${esc(r.sensitivity)}</option>`).join("");
}
async function openResource(id){
  try{const d=await api(`/api/resource/${encodeURIComponent(id)}`);toast(`ACCESS GRANTED · ${d.resource} · ${d.message}`);await load();}
  catch(e){toast(`ACCESS BLOCKED · ${e.message}`);await load();}
}
async function submitRequest(){
  try{const d=await api("/api/request",{method:"POST",body:JSON.stringify({resource_id:$("request-resource").value,action:$("request-action").value,reason:$("request-reason").value,duration_minutes:Number($("request-duration").value)})});$("request-reason").value="";toast(`Request #${d.request_id} submitted. Manager review is next.`);await load();}
  catch(e){toast(e.message)}
}
function renderRequests(){
  const rows=state.requests.map(r=>{
    let action="";
    if(state.user.role==="manager"&&r.status==="pending_manager"&&state.user.department===state.user.department)
      action=`<button class="small-btn" onclick="approve(${r.id},'manager')">Manager review</button>`;
    if(state.user.role==="manager"&&r.status==="pending_owner")
      action+=` <button class="small-btn" onclick="approve(${r.id},'owner')">Owner approve</button>`;
    if(state.user.role==="executive"&&r.status==="pending_manager")action=`<button class="small-btn" onclick="approve(${r.id},'manager')">Review</button>`;
    if(state.user.role==="executive"&&r.status==="pending_owner")action=`<button class="small-btn" onclick="approve(${r.id},'owner')">Approve</button>`;
    if(["pending_manager","pending_owner"].includes(r.status)&&["manager","executive"].includes(state.user.role))action+=` <button class="danger" onclick="reject(${r.id})">Reject</button>`;
    return `<tr><td>#${r.id}</td><td>${esc(r.requester)}</td><td>${esc(r.resource_id)}</td><td>${r.duration_minutes}m</td><td>${status(r.status)}</td><td>${action||"—"}</td></tr>`;
  });
  $("request-list").innerHTML=table(["ID","Requester","Resource","Duration","Status","Action"],rows);
}
function renderGrants(){
  const rows=state.grants.map(g=>`<tr><td>#${g.id}</td><td>${esc(g.username)}</td><td>${esc(g.resource_id)}</td><td>${new Date(g.expires_at).toLocaleTimeString()}</td><td>${g.revoked_at?"Revoked":new Date(g.expires_at)>new Date()?"Active":"Expired"}</td><td>${state.user.role==="manager"||state.user.role==="executive"?`<button class="danger" onclick="revoke(${g.id})">Revoke</button>`:"—"}</td></tr>`);
  $("grant-list").innerHTML=table(["Grant","Employee","Resource","Expires","State","Action"],rows);
}
async function approve(id,step){try{await api(`/api/requests/${id}/approve-${step}`,{method:"POST",body:"{}"});toast("Approval recorded.");await load()}catch(e){toast(e.message)}}
async function reject(id){try{await api(`/api/requests/${id}/reject`,{method:"POST",body:"{}"});toast("Request rejected.");await load()}catch(e){toast(e.message)}}
async function revoke(id){try{await api(`/api/grants/${id}/revoke`,{method:"POST",body:"{}"});toast("Grant revoked immediately.");await load()}catch(e){toast(e.message)}}
async function submitExecutiveRequest(){
  try{const d=await api("/api/executive/request",{method:"POST",body:JSON.stringify({resource_id:$("exec-resource").value,reason:$("exec-reason").value})});$("exec-reason").value="";toast(`Executive request #${d.request_id} sent for second approval.`);await load()}
  catch(e){toast(e.message)}
}
function renderExecutive(){
  const isExec=state.user.role==="executive";
  $("exec-queue").innerHTML=isExec?table(["ID","Requested by","Resource","Status","Action"],state.executive_requests.map(r=>`<tr><td>#${r.id}</td><td>${esc(r.requester)}</td><td>${esc(r.resource_id)}</td><td>${status(r.status)}</td><td><button class="small-btn" onclick="approveExec(${r.id})">Second approval</button></td></tr>`)):'<div class="empty">Executive request and approval controls are visible to executive identities only. Your department view remains limited.</div>';
  $("exec-resource").disabled=!isExec;$("exec-reason").disabled=!isExec;
}
async function approveExec(id){try{await api(`/api/executive/${id}/approve`,{method:"POST",body:"{}"});toast("Second executive approval recorded. Try opening the resource.");await load()}catch(e){toast(e.message)}}
function renderAudit(){
  const rows=state.events.map(e=>`<div class="event"><time>${new Date(e.created_at).toLocaleString()}</time><div><b>${esc(e.event_type.replaceAll("_"," "))}</b><br><small>${esc(e.details)} ${e.resource_id?"· "+esc(e.resource_id):""}</small></div><span>${esc(e.actor)}</span></div>`);
  $("audit-list").innerHTML=rows.join("")||'<div class="empty">No events visible.</div>';
}
load();setInterval(load,15000);
