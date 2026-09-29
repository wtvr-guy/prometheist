import {el, icon, button, badge, pretty, empty, modal, api, date, bytes} from './ui.js';
export async function activityView(ctx){
  const root=el('div',{},el('header',{class:'view-header'},el('div',{},el('div',{class:'eyebrow'},'Nothing behind the curtain'),el('h1',{},'Activity'),el('p',{class:'subtitle'},'Follow tasks, inspect the settings they used, and stop work that is in progress.')),button('Refresh',ctx.refreshJobs,{glyph:'refresh'})));
  const content=el('div',{class:'content'});root.append(content);
  if(!ctx.state.jobs.length){content.append(empty('A clear starting point','Chat tasks, downloads, and reviewed Firewall changes will appear here.'));return root;}
  for(const job of ctx.state.jobs){
    const active=['running','cancelling'].includes(job.status);
    const label=job.action==='chat'?'Conversation':job.action==='pull'?'Model download':job.action==='file_copy'?'File copy':'Firewall change';
    const progress=job.progress;
    const summary=job.action==='chat'?job.payload.text.slice(0,180):job.payload.model||job.payload.path||job.payload.plan?.action;
    content.append(el('article',{class:'activity-row'},el('div',{class:'activity-icon'},icon(job.action==='chat'?'chat':job.action==='pull'?'download':'shield')),el('div',{class:'activity-body'},el('div',{class:'row spread'},el('h3',{},label),badge(job.status,job.status==='completed'?'green':active?'amber':'red')),el('p',{},summary),el('p',{},date(job.created_at),' · ',job.selection.model),
      progress&&active?el('p',{class:'running'},el('span',{class:'spinner'}),progress.stage||progress.status,progress.total?`${bytes(progress.completed||0)} / ${bytes(progress.total)}`:''):null,
      job.error?el('p',{class:'error-copy'},job.error):null,
      el('div',{class:'row'},active?button('Stop task',async()=>{await api(`/jobs/${job.id}/cancel`,{method:'POST',body:{}});await ctx.refreshJobs();},{glyph:'close'}):null,
        button('Details',()=>modal('Task receipt',el('div',{class:'stack'},el('p',{class:'hint'},'These are the settings captured when the job started. Later edits do not change them.'),pretty(job))),{kind:'ghost'}),
        button('Worker log',async()=>{const result=await api(`/jobs/${job.id}/log`);modal('Local worker log',el('pre',{class:'json'},result.text||'No log output.'),[button('Close',()=>document.querySelector('#dialog').close())]);},{kind:'ghost'})))));
  }
  content.append(el('p',{class:'hint'},'Showing the most recent 200 jobs. Older receipts remain in the private app-jobs directory; canonical events and artifact journals are retained separately.'));
  return root;
}
