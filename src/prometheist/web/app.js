import {el, icon, button, badge, api, toast, grant, date} from './ui.js';
import {inspector} from './controls.js';
import {modelsView} from './models.js';
import {settingsView} from './settings.js';
import {activityView} from './activity.js';
import {filesView} from './files.js';
import {previewRoute, reviewFallback} from './routing.js';

const state = {view:'chat', settings:null, bootstrap:null, jobs:[], active:null, conversation:crypto.randomUUID(), draft:'', task:'auto', modelTab:'installed', settingTab:'general', controls:false, version:0};
let writeQueue = Promise.resolve();
const ctx = {state, navigate, render, saveSettings, toggleControls, refreshJobs, newChat, resumeDefault:()=>sendMessage('default')};
const VIEWS = [
  {id:'chat', name:'Chat', icon:'chat'}, {id:'models', name:'Models', icon:'cube', render:modelsView},
  {id:'files', name:'Files', icon:'folder', render:filesView},
  {id:'activity', name:'Activity', icon:'activity', render:activityView}, {id:'settings', name:'Settings', icon:'settings', render:settingsView},
];
function applyTheme() {
  const theme = state.settings.theme;
  document.documentElement.dataset.theme = theme === 'system' ? matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light' : theme;
}
matchMedia('(prefers-color-scheme:dark)').addEventListener('change', () => state.settings && applyTheme());
async function saveSettings(patch) {
  const update = async () => {
    const next = typeof patch === 'function' ? patch(structuredClone(state.settings)) : {...state.settings, ...patch};
    const response = await api('/settings', {method:'PUT', body:{settings:next, revision:state.bootstrap.revision}});
    state.settings = response.settings; state.bootstrap.revision = response.revision; applyTheme(); updateStatus();
    return response;
  };
  const result = writeQueue.then(update); writeQueue = result.catch(() => {}); return result;
}
function navigate(view) { state.view = view; document.querySelector('.app-shell')?.classList.remove('menu-open'); render(); }
function newChat() { state.conversation = crypto.randomUUID(); state.draft = ''; state.fallbackPlan=null; navigate('chat'); }
function toggleControls(value = !state.controls) { state.controls = value; render(); }
function shell() {
  const sidebar = el('aside', {class:'sidebar'}, el('div', {class:'brand'}, el('img', {src:'/assets/mark.svg', alt:''}), el('div', {}, el('strong', {}, 'Prometheist'), el('small', {}, 'Personal intelligence'))),
    el('div', {class:'stack'}, button('New conversation', newChat, {glyph:'plus', kind:'new-chat'}), el('nav', {class:'nav', 'aria-label':'Main navigation'}, ...VIEWS.map(view => button(view.name, () => navigate(view.id), {glyph:view.icon, kind:state.view === view.id ? 'active' : '', 'aria-current':state.view === view.id ? 'page' : undefined})))),
    el('div', {class:'history'}, el('div', {class:'sidebar-section'}, 'Recent conversations'), el('div', {id:'history-list'})),
    el('div', {class:'sidebar-footer'}, el('div', {class:'avatar'}, '01'), el('div', {}, el('div', {class:'field-label'}, state.bootstrap.subject), el('small', {}, 'Private workspace'))));
  const topbar = el('header', {class:'topbar'}, el('div', {class:'breadcrumb'}, button('', () => document.querySelector('.app-shell').classList.toggle('menu-open'), {glyph:'menu', kind:'icon-button mobile-menu', 'aria-label':'Toggle navigation'}), el('span', {}, 'Workspace'), icon('chevron',12), el('strong', {}, VIEWS.find(view => view.id === state.view).name)),
    el('div', {class:'top-actions'}, el('span', {class:'privacy'}, icon('shield',14), 'Local control'), button(state.settings.advanced ? 'Advanced on' : 'Advanced', async () => { await saveSettings({advanced:!state.settings.advanced}); state.controls = state.settings.advanced; render(); }, {glyph:'settings', kind:state.settings.advanced ? 'active' : 'ghost'})));
  return el('div', {class:'app-shell'}, sidebar, el('section', {class:'workspace'}, topbar, el('main', {class:'body', id:'view', 'aria-label':'Workspace content'}), el('footer', {class:'status-bar', id:'status-bar'})));
}
function updateHistory() {
  const root = document.querySelector('#history-list'); if (!root) return;
  const seen = new Set();
  const chats = state.jobs.filter(job => job.action === 'chat').filter(job => { const id = job.payload.conversation_id; if (seen.has(id)) return false; seen.add(id); return true; });
  root.replaceChildren(...chats.slice(0,20).map(job => button(job.payload.text.slice(0,70), () => { state.conversation = job.payload.conversation_id; state.draft = ''; navigate('chat'); }, {kind:state.conversation === job.payload.conversation_id ? 'active' : '', title:job.payload.text.slice(0,150)})));
  if (!chats.length) root.append(el('p', {class:'hint', style:undefined}, 'Your conversations will appear here.'));
}
function updateStatus() {
  const root = document.querySelector('#status-bar'); if (!root) return;
  const ready = state.bootstrap.health.status === 'ready';
  root.replaceChildren(el('div', {class:'row'}, el('span', {class:ready ? 'dot' : 'badge amber'}, ready ? '' : '•'), ready ? 'Runtime ready' : 'Setup needed', el('span', {}, '·'), state.active ? 'Task in progress' : 'No active task'), el('span', {}, [state.settings.selection, ...Object.values(state.settings.routes)].some(route => route.provider === 'openai') ? 'Cloud route selected · external requests require consent' : 'Ollama selected · local by default'));
  const notice = document.querySelector('#runtime-notice');
  if (notice) {
    notice.hidden = ready;
    notice.replaceChildren(el('span', {}, state.bootstrap.health.message), button('Setup', () => {state.settingTab='general';navigate('settings');}, {kind:'ghost'}));
  }
  const send = document.querySelector('#send-message');
  if (send) { send.disabled = !ready || Boolean(state.active); }
}
async function render() {
  const version = ++state.version;
  document.querySelector('#app').replaceChildren(shell()); updateHistory(); updateStatus();
  const root = document.querySelector('#view');
  if (state.view === 'chat') {
    root.append(chatView()); updateStatus();
    if (state.controls) {
      const panel = await inspector(ctx);
      if (version === state.version) document.querySelector('.chat-layout')?.append(panel);
    }
  } else {
    root.append(el('div', {class:'empty'}, el('span', {class:'spinner'}), el('p', {}, 'Loading…')));
    try { const view = await VIEWS.find(item => item.id === state.view).render(ctx); if (version === state.version) root.replaceChildren(view); }
    catch (error) { if (version === state.version) root.replaceChildren(el('div', {class:'empty'}, el('h3', {}, 'This view is unavailable'), el('p', {}, error.message), button('Retry', render))); }
  }
}
function chatView() {
  const selection = state.settings.selection;
  const routeCount = Object.keys(state.settings.routes).length;
  const hasCloud = [selection, ...Object.values(state.settings.routes)].some(route => route.provider === 'openai');
  const toolbar = el('div', {class:'chat-toolbar'}, button('', () => toggleControls(), {kind:'ghost', title:'Choose provider and model', 'aria-label':'Choose model'}), button('Controls', () => toggleControls(), {glyph:'settings', kind:state.controls ? '' : 'ghost'}));
  toolbar.firstChild.replaceChildren(el('span', {class:'model-pill'}, icon(selection.provider === 'openai' ? 'cloud' : 'cpu',16), el('strong', {}, selection.model), badge(hasCloud ? 'Cloud enabled' : 'Local', hasCloud ? 'amber' : 'green'), routeCount ? badge(`${routeCount} routes`) : null, icon('chevron',12)));
  const conversation = el('div', {class:'conversation', id:'conversation'});
  const textarea = el('textarea', {id:'message-input', placeholder:'Message Prometheist…', 'aria-label':'Message Prometheist', rows:2, maxlength:32768});
  textarea.value = state.draft;
  textarea.addEventListener('input', () => { state.draft = textarea.value; state.fallbackPlan=null; });
  textarea.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); sendMessage().catch(error => toast(error.message,true)); } });
  const task=el('select',{'aria-label':'Task type'},el('option',{value:'auto'},'Auto task'),el('option',{value:'general'},'General'),el('option',{value:'coding'},'Coding'));
  task.value=state.task; task.addEventListener('change',()=>{state.task=task.value;});
  const form = el('div', {class:'composer-area'}, el('div', {class:'runtime-notice', id:'runtime-notice'}), el('form', {class:'composer', onsubmit:event => {event.preventDefault();sendMessage().catch(error => toast(error.message,true));}}, textarea,
    el('div', {class:'composer-bottom'}, el('div', {class:'row'}, badge('Private conversation'), el('span', {class:'composer-help'}, 'Enter to send · Shift + Enter for a new line')),
      button('', sendMessage, {id:'send-message', glyph:'arrow', kind:'primary send-button', 'aria-label':'Send message'}))),
    el('div',{class:'task-controls'},task,button('Preview route',()=>previewRoute(ctx),{kind:'ghost'})),
    el('p', {class:'composer-foot'}, 'Built around you. Evidence stays local unless you explicitly allow a destination.'));
  const view = el('div', {class:'chat-layout'}, el('div', {class:'chat-column'}, toolbar, conversation, form));
  fillConversation(conversation); return view;
}
function fillConversation(root) {
  const jobs = state.jobs.filter(job => job.action === 'chat' && job.payload.conversation_id === state.conversation).reverse();
  const scrollDown = root.scrollHeight - root.scrollTop - root.clientHeight < 100;
  if (!jobs.length) {
    const prompt = value => { state.draft=value; const input=document.querySelector('#message-input'); input.value=value; input.focus(); };
    root.replaceChildren(el('div', {class:'welcome'}, el('div', {class:'welcome-kicker'}, el('div', {class:'welcome-mark'}, icon('shield',24)), el('span', {class:'eyebrow'}, 'Your own intelligence')), el('h1', {}, 'A private space', el('br'), 'to ', el('em', {}, 'think clearly.')), el('p', {}, 'A conversation that builds understanding over time. Your models, your memory, your boundaries.'),
      el('div', {class:'suggestions'},
        suggestion('chat','Start with me','Tell Prometheist what matters to you.', () => prompt('I want you to understand what matters most to me. Help me get started.')),
        suggestion('book','Make room for a thought','Work through something on your mind.', () => prompt('Help me think through a decision. Ask me what you need to know first.')),
        suggestion('shield','Review my environment','See host resources and security observations.', () => {state.settingTab='environment';navigate('settings');}))));
  } else {
    const messages = el('div', {class:'messages', 'aria-live':'polite'});
    for (const job of jobs) {
      messages.append(el('article', {class:'message user', 'aria-label':'Your message'}, el('div', {class:'message-text'}, job.payload.text)));
      const response = el('article', {class:'message assistant', 'aria-label':'Prometheist response'}, el('div', {class:'message-label'}, icon('shield',15), 'Prometheist', badge(job.admission?.stages?.V2_RESPOND?.model||job.selection.model)));
      if(job.admission)response.append(el('p',{class:'hint'},job.admission.route_reason));
      if(job.admission?.specialist_offer)response.append(el('div',{class:'notice'},el('p',{},job.admission.specialist_offer),button('Find a specialist',()=>{state.specialistTask=job.admission.task;state.modelTab='catalog';navigate('models');},{kind:'ghost',glyph:'search'})));
      if(job.admission?.openai_offer)response.append(el('div',{class:'notice'},el('p',{},'If no local option suits this task, would you like to review an OpenAI route?'),button('Review OpenAI options',()=>{state.modelTab='openai';navigate('models');},{kind:'ghost',glyph:'cloud'})));
      if (job.status === 'completed') {
        response.append(el('div', {class:'message-text'}, job.result?.text ?? 'No response was required for this interaction.'), el('div', {class:'message-meta'}, date(job.finished_at), button('Copy', () => navigator.clipboard.writeText(job.result?.text || '').then(() => toast('Response copied')), {glyph:'copy', kind:'ghost'})));
      } else if (['running','cancelling'].includes(job.status)) response.append(el('div', {class:'running'}, el('span', {class:'spinner'}), job.progress?.stage ? job.progress.stage.replaceAll('_',' ').toLowerCase() : job.progress?.status || 'Starting the guarded worker pipeline…'), button('Stop task', async () => {await api(`/jobs/${job.id}/cancel`,{method:'POST',body:{}});await refreshJobs();}, {kind:'ghost'}));
      else response.append(el('p', {class:'error-copy'}, job.error || `Task ${job.status}`), button('View diagnostics', () => navigate('activity'), {kind:'ghost'}));
      messages.append(response);
    }
    root.replaceChildren(messages);
    if (scrollDown) requestAnimationFrame(() => root.scrollTop = root.scrollHeight);
  }
}
function suggestion(glyph,title,description,action) { return el('button', {class:'suggestion', type:'button', onclick:action}, icon(glyph,19), el('strong', {}, title), el('span', {}, description)); }
let sending = false;
async function sendMessage(fallback='review') {
  if (sending || state.active || !state.draft.trim()) return;
  sending = true;
  try {
    const selections = [state.settings.selection, ...Object.values(state.settings.routes)];
    if (selections.some(item => item.provider === 'openai') && !await grant('model_inference','https://api.openai.com')) return;
    const endpoint = new URL(state.settings.ollama_url);
    if (selections.some(item => item.provider === 'ollama') && !['127.0.0.1','localhost','[::1]'].includes(endpoint.hostname) && !await grant('model_inference',endpoint.origin)) return;
    const body={text:state.draft,conversation_id:state.conversation,task:state.task,fallback:fallback==='default'?'default':'review'};
    let plan=await api('/routing/preview',{method:'POST',body});
    if(plan.status==='needs_choice'){
      const choice=await reviewFallback(ctx,plan);if(!choice)return;
      body.fallback=choice;plan=await api('/routing/preview',{method:'POST',body});
    }
    if(plan.status!=='eligible'){await previewRoute(ctx);return;}
    await api('/chat', {method:'POST', body});
    state.draft=''; const input=document.querySelector('#message-input'); if(input) input.value=''; await refreshJobs();
  } finally { sending=false; }
}
let lastJobs='';
async function refreshJobs() {
  const result = await api('/jobs'); state.jobs=result.jobs; state.active=result.active;
  const signature=JSON.stringify(result);
  updateStatus(); updateHistory();
  if (signature !== lastJobs) {
    lastJobs=signature;
    if (state.view === 'chat') {const root=document.querySelector('#conversation');if(root)fillConversation(root);}
    else if(state.view==='activity') await render();
  }
}
async function boot() {
  try {
    const token = new URLSearchParams(location.hash.slice(1)).get('token');
    history.replaceState(null,'',location.pathname);
    if (token) {
      const response=await fetch('/auth/handshake',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
      if(!response.ok) throw new Error((await response.json()).detail);
    }
    state.bootstrap=await api('/bootstrap'); state.settings=state.bootstrap.settings;state.controls=state.settings.advanced;applyTheme();
    const initial=await api('/jobs');state.jobs=initial.jobs;state.active=initial.active;
    await render();
    let tick=0;
    async function poll(){
      try { await refreshJobs(); if(++tick%5===0){const data=await api('/bootstrap');state.bootstrap.health=data.health;state.bootstrap.openai_connected=data.openai_connected;updateStatus();} }
      catch {const bar=document.querySelector('#status-bar');if(bar)bar.textContent='Connection to the local app was lost. Your draft remains in this window.';}
      setTimeout(poll,2000);
    }
    setTimeout(poll,2000);
  } catch(error) {
    document.querySelector('#app').replaceChildren(el('div',{class:'loading-screen'},el('img',{src:'/assets/mark.svg',alt:'',width:48}),el('h1',{},'Open your private workspace'),el('p',{},error.message),el('p',{},'Use the one-use link printed by the local app. If it has already been used in another browser, restart the app to generate a new link.'),el('pre',{class:'json'},'uv run prometheist gui')));
  }
}
boot();
