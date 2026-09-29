import {el, icon, button, field, badge, pretty, empty, modal, confirm, api, toast, grant, bytes} from './ui.js';
import {parameterFields} from './controls.js';
import {specialistSettings} from './routing.js';

const SECTIONS=[['general','Workspace'],['routing','Model routing'],['resources','Resources'],['memory','Memory & evidence'],['environment','Devices & sensors'],['security','OS security'],['privacy','Privacy & consent'],['registries','Registries']];
export async function settingsView(ctx){
  const {state}=ctx;
  const panel=el('section',{class:'settings-content'});
  const root=el('div',{},el('header',{class:'view-header'},el('div',{},el('div',{class:'eyebrow'},'Make it yours'),el('h1',{},'Settings'),el('p',{class:'subtitle'},'A simple surface when you want it. Precise controls when you need them.'))),el('div',{class:'content split'},el('nav',{class:'settings-nav','aria-label':'Settings sections'},...SECTIONS.map(([id,name])=>button(name,()=>{state.settingTab=id;ctx.render();},{kind:state.settingTab===id?'active':''}))),panel));
  const handlers={general, routing, resources, memory, environment, security, privacy, registries};
  await handlers[state.settingTab](panel,ctx);
  return root;
}
function section(title,description,...children){return el('section',{class:'card'},el('div',{class:'section-title'},el('div',{},el('h2',{},title),description?el('p',{class:'subtitle'},description):null)),...children);}
function general(root,ctx){
  const settings=ctx.state.settings;
  const theme=el('select',{'aria-label':'Color theme'},...['dark','light','system'].map(value=>el('option',{value},value[0].toUpperCase()+value.slice(1))));theme.value=settings.theme;
  const advanced=el('input',{type:'checkbox',role:'switch',checked:settings.advanced,'aria-label':'Show advanced controls by default'});
  const endpoint=el('input',{type:'url',value:settings.ollama_url});
  const personality=el('textarea',{rows:5,maxlength:8192,placeholder:'Optional preferences for tone, depth, and communication style.'});personality.value=settings.personality;
  const timeout=el('input',{type:'number',min:30,max:3600,step:1,value:settings.worker_timeout_seconds});
  root.append(section('Your workspace','Local settings for this single-person profile.',el('div',{class:'field-grid'},field('Theme',theme),field('Ollama endpoint',endpoint,'Localhost stays on this machine. Remote destinations require consent.'),field('Worker timeout (seconds)',timeout,'Applied to each guarded cognitive stage.'),el('label',{class:'check-row'},advanced,'Open generation controls by default'),el('div',{class:'span-two'},field('Communication preferences',personality,'Adds your preferences to the registered personality rules.')))),
    section('Runtime connection',null,el('div',{class:'stack'},badge(ctx.state.bootstrap.health.status,ctx.state.bootstrap.health.status==='ready'?'green':'amber'),el('p',{class:'hint'},ctx.state.bootstrap.health.message),el('p',{class:'hint'},'Private runtime: ',el('code',{class:'inline-code'},ctx.state.bootstrap.private_root)),el('p',{class:'hint'},'Database credentials come from the profile’s environment variable. The app does not display or save them.'),button('Recheck runtime & scan host',async()=>{await api('/environment/scan',{method:'POST',body:{}});toast('A fresh scan and runtime check were requested');},{glyph:'refresh'}))),
    el('div',{class:'settings-save'},button('Save settings',async()=>{if(!endpoint.checkValidity()||!timeout.checkValidity())throw new Error('Check the endpoint and timeout');await ctx.saveSettings({theme:theme.value,advanced:advanced.checked,ollama_url:endpoint.value,personality:personality.value,worker_timeout_seconds:Number(timeout.value)});toast('Workspace settings saved');},{kind:'primary'})));
}
async function routing(root,ctx){
  root.append(specialistSettings(ctx));
  root.append(section('Assign models by task','The chat model is the default. An explicit stage route overrides it.',el('p',{class:'notice'},'A route applies to the registered worker stage. A cloud route receives only that stage’s bounded instructions and evidence, after destination consent. Control workers keep deterministic sampling; reasoning models may not offer deterministic generation.')));
  for(const [id,role] of Object.entries(ctx.state.bootstrap.routes)){
    const selection=ctx.state.settings.routes[id];
    root.append(el('div',{class:'card'},el('div',{class:'row spread'},el('div',{},el('h3',{},role[0].toUpperCase()+role.slice(1)),el('p',{class:'hint'},id)),badge(selection?selection.provider:'Inherited',selection?.provider==='openai'?'amber':'')),el('div',{class:'setting-row'},el('div',{},el('h3',{},selection?.model||ctx.state.settings.selection.model),el('p',{},selection?'Explicit route':'Uses the chat model and its settings')),el('div',{class:'row'},button('Configure',()=>editRoute(ctx,id,role,selection)),selection?button('Reset',async()=>{await ctx.saveSettings(settings=>{delete settings.routes[id];return settings;});ctx.render();},{kind:'ghost'}):null))));
  }
}
function editRoute(ctx,id,role,existing){
  const selection=existing||ctx.state.settings.selection;
  const provider=el('select',{},el('option',{value:'ollama'},'Ollama'),el('option',{value:'openai'},'OpenAI'));provider.value=selection.provider;
  const model=el('input',{value:selection.model});
  const content=el('div',{class:'stack'},field('Provider',provider),field('Model ID',model),el('p',{class:'hint'},'Changing the provider or model resets its overrides. Use “Generation parameters” to review controls for the selected ID.'));
  let parameters={...selection.parameters};let fields=null;
  const load=button('Generation parameters',async()=>{
    const next={provider:provider.value,model:model.value.trim(),parameters:provider.value===selection.provider&&model.value.trim()===selection.model?parameters:{}};
    fields=await parameterFields(next);container.replaceChildren(fields.root);
  },{glyph:'settings'});
  const container=el('div',{});content.append(load,container);
  provider.addEventListener('change',()=>{fields=null;parameters={};container.replaceChildren();});
  model.addEventListener('input',()=>{fields=null;parameters={};container.replaceChildren();});
  const dialog=modal(role,content,[button('Cancel',()=>document.querySelector('#dialog').close()),button('Save route',async()=>{
    const route={provider:provider.value,model:model.value.trim(),parameters:fields?fields.read():parameters};
    await ctx.saveSettings(settings=>{settings.routes[id]=route;return settings;});dialog.close();toast('Stage route saved');ctx.render();
  },{kind:'primary'})]);
}
async function numericSection(root,ctx,key,title,description,labels){
  const schema=await api('/settings/schema');
  const definition=key==='resources'?schema.$defs.ResourceSettings:schema.$defs.MemorySettings;
  const fields={};const grid=el('div',{class:'field-grid'});
  for(const [name,spec] of Object.entries(definition.properties)){
    const input=el('input',{type:'number',min:spec.minimum,max:spec.maximum,step:spec.type==='integer'?1:.1,value:ctx.state.settings[key][name]});fields[name]=input;
    grid.append(field(labels[name]||name.replaceAll('_',' '),input));
  }
  root.append(section(title,description,grid),el('p',{class:'notice'},key==='resources'?'These values govern admission for new jobs. They do not reserve physical RAM in the operating system. Larger models, context windows, and simultaneous external workloads need larger memory estimates. Routed models do not share residency credit.':'Evidence budgets are finite byte limits. They are independent of a model’s token context window. Raising a limit increases memory use and possible disclosure to a consented cloud model.'),el('div',{class:'settings-save'},button('Save limits',async()=>{
    const values={};for(const [name,input] of Object.entries(fields)){if(!input.checkValidity()){input.reportValidity();throw new Error('Check the numeric limits');}values[name]=Number(input.value);}
    await ctx.saveSettings({[key]:values});toast('Limits saved for new jobs');
  },{kind:'primary'})));
}
function resources(root,ctx){return numericSection(root,ctx,'resources','Resource admission','Keep capacity available for the operating system and other applications.',{cpu_system_headroom_percent:'CPU headroom (%)',memory_system_headroom_percent:'Memory headroom (%)',memory_system_headroom_min_mib:'Minimum memory headroom (MiB)',uncertainty_headroom_percent:'Uncertainty headroom (%)',max_cpu_pressure_percent:'Maximum CPU pressure (%)',default_llm_process_memory_mib:'Cold local model + worker estimate (MiB)',default_process_memory_mib:'Worker process estimate (MiB)'});}
function memory(root,ctx){return numericSection(root,ctx,'memory','Memory & evidence','Control how much evidence can enter one model request.',{max_item_bytes:'Maximum evidence item (bytes)',max_total_bytes:'Maximum combined evidence (bytes)',max_input_bytes:'Maximum complete input (bytes)'});}
async function environment(root,ctx){
  const data=await api('/environment');const scan=data.observation?.scan;const reports=scan?.reports||[];const resources=reports.flatMap(report=>(report.resources||[]).map(resource=>({...resource,provider:report.provider})));
  // Group the display only. The scan receipt retains every provider record and ID.
  const groups=new Map();
  for(const resource of resources){
    const name=(resource.name||resource.label||String(resource.resource_id)).trim();
    const key=`${resource.kind}\u0000${name.toLocaleLowerCase()}`;
    if(!groups.has(key))groups.set(key,{name,kind:resource.kind,items:[]});
    groups.get(key).items.push(resource);
  }
  const grouped=[...groups.values()].sort((a,b)=>a.kind.localeCompare(b.kind)||a.name.localeCompare(b.name));
  const interval=el('input',{type:'number',min:10,max:3600,step:1,value:ctx.state.settings.monitor_interval_seconds});
  root.append(section('Devices & sensors','Passive host discovery runs when the app starts and at the configured interval.',el('div',{class:'row spread'},field('Scan interval (seconds)',interval),button('Save interval',async()=>{await ctx.saveSettings({monitor_interval_seconds:Number(interval.value)});toast('Scan interval saved');}),button('Scan now',async()=>{await api('/environment/scan',{method:'POST',body:{}});toast('Scan requested; refresh to read the result');},{glyph:'refresh'})),el('p',{class:'hint'},data.health.message),el('p',{class:'notice'},'Phone Link can show that its Windows app is present, but it cannot grant Prometheist access to Android sensors. Phone permissions must be requested by an installed Android companion app on the phone; that integration is not implemented yet.')),el('div',{class:'metrics'},...[[grouped.length,'Displayed resource groups'],[reports.length,'Provider reports'],[data.observation?.persisted_to_database?'Recorded':'Local only','Observation persistence']].map(([value,label])=>el('div',{class:'card'},el('div',{class:'large-stat'},value),el('p',{class:'hint'},label)))));
  if(!scan){root.append(empty('Waiting for a host observation','The first scan may take a few moments.',button('Refresh',ctx.render,{glyph:'refresh'})));return;}
  const filter=el('input',{type:'search',placeholder:'Filter resources by name, kind or provider…','aria-label':'Filter observed resources'});
  const rows=el('tbody',{});
  const draw=()=>{
    const query=filter.value.trim().toLocaleLowerCase();
    const shown=grouped.filter(group=>!query||[group.name,group.kind,...group.items.map(item=>item.provider)].some(value=>String(value).toLocaleLowerCase().includes(query)));
    rows.replaceChildren(...shown.map(group=>el('tr',{},el('td',{},group.name,group.items.length>1?el('span',{class:'hint'},` · ${group.items.length} observations`):null),el('td',{},group.kind),el('td',{},button('Inspect',()=>modal('Resource observations',pretty(group.items)),{kind:'ghost'})))));
  };
  filter.addEventListener('input',draw);draw();
  root.append(section('Provider coverage',null,el('div',{class:'table-wrap'},el('table',{class:'data-table'},el('thead',{},el('tr',{},el('th',{},'Provider'),el('th',{},'Status'),el('th',{},'Resources'))),el('tbody',{},...reports.map(report=>el('tr',{},el('td',{},report.provider),el('td',{},badge(report.status,report.status==='COMPLETE'?'green':'')),el('td',{},report.resources?.length||0))))))),
    section('Observed resources','Matching names are grouped for display; inspect a group to see each original provider record. Distinct devices with the same name may appear in one group.',filter,el('div',{class:'table-wrap'},el('table',{class:'data-table'},el('thead',{},el('tr',{},el('th',{},'Resource'),el('th',{},'Kind'),el('th',{},'Details'))),rows))),el('div',{class:'row'},button('Refresh observations',ctx.render,{glyph:'refresh'}),button('Full scan receipt',()=>modal('Host observation',pretty(data)),{kind:'ghost'})));
}
async function security(root,ctx){
  const [enrollment,environment]=await Promise.all([api('/security/enrollment'),api('/environment')]);
  const posture=environment.observation?.security_posture;
  root.append(section('Host security authority','Grant or revoke the implemented security capabilities for this person and this machine.',el('div',{class:'setting-row'},el('div',{},el('h3',{},enrollment.enrollment?'Security authority enrolled':'Review security enrollment'),el('p',{},'Capabilities remain subject to native OS permissions.')),enrollment.enrollment?button('Revoke enrollment',async()=>{if(await confirm('Revoke security authority?',el('p',{},'Future privileged security actions will be denied. Existing Firewall rules remain until you review and execute a removal plan.'),'Revoke',true)){await api('/security/enrollment',{method:'DELETE',body:{}});ctx.render();}},{kind:'danger'}):button('Review & enroll',async()=>{if(await confirm('Review host security authority',el('div',{class:'stack'},el('p',{},enrollment.proposal.disclosure),pretty(enrollment.proposal.capabilities)),'Enroll this host')){await api('/security/enrollment',{method:'POST',body:{accepted_digest:enrollment.accepted_digest}});ctx.render();}},{kind:'primary'}))));
  const findings=posture?.findings||[];
  root.append(section('Security observations','A failed or unknown observation is evidence to inspect, not proof of compromise.',findings.length?el('div',{class:'stack'},...findings.map(finding=>el('div',{class:'setting-row'},el('div',{},el('h3',{},finding.rule_id),el('p',{},finding.meaning||finding.message||finding.provider)),badge(finding.status,finding.status==='PASS'?'green':finding.status==='FAIL'?'red':'amber')))):el('p',{class:'hint'},'No security assessment is available yet.')),
    section('Windows Firewall','Review exact executable paths and network scopes before applying or removing Prometheist’s managed rules.',el('p',{class:'notice'},'The local-only policy blocks consented cloud calls too. Applying rules requires Windows administrator rights. The app does not elevate itself or change unrelated Firewall rules.'),el('div',{class:'row'},button('Review local-only policy',()=>reviewFirewall(ctx,'APPLY'),{glyph:'shield'}),button('Review removal',()=>reviewFirewall(ctx,'REMOVE'),{kind:'ghost'}))));
}
async function reviewFirewall(ctx,action){
  const review=await api(`/security/firewall?action=${action}`);
  if(await confirm(action==='APPLY'?'Apply local-only Firewall rules?':'Remove managed Firewall rules?',el('div',{class:'stack'},el('p',{},review.plan.impact||'Review the exact plan below.'),pretty(review.plan)),action==='APPLY'?'Apply reviewed plan':'Remove reviewed rules',action==='REMOVE')){
    await api('/security/firewall',{method:'POST',body:review});await ctx.refreshJobs();ctx.navigate('activity');
  }
}
async function privacy(root,ctx){
  const consents=await api('/consents');
  root.append(section('External access','Each grant names a destination and the information that can leave this machine.',el('p',{class:'notice'},'Local chat, host observations and evidence remain private by default. Revocation is checked before future app requests. It cannot recall data already sent or guarantee cancellation of a transfer owned by another service.')));
  if(!consents.grants.length)root.append(empty('No external destinations authorized','A reviewed disclosure appears when you choose an external model, search the catalog, or download a model.'));
  for(const consent of consents.grants)root.append(el('div',{class:'card stack'},el('div',{class:'row spread'},el('h3',{class:'break'},consent.destination),badge(consent.purpose.replaceAll('_',' '))),el('p',{class:'hint'},consent.disclosure),el('div',{class:'row'},button('Revoke access',async()=>{await api('/consents',{method:'DELETE',body:{purpose:consent.purpose,destination:consent.destination}});toast('Destination access revoked for future requests');ctx.render();},{kind:'danger'}))));
  const destination=el('input',{type:'url',placeholder:'https://host.example:port'});
  const purpose=el('select',{},...['model_inference','database_storage','connectivity_check'].map(value=>el('option',{value},value.replaceAll('_',' '))));
  root.append(section('Add a specific destination',null,el('div',{class:'stack'},field('Purpose',purpose),field('Destination',destination,'Database destinations use postgresql://host:port. Connectivity checks use an exact HTTPS URL.'),button('Review disclosure',async()=>{if(await grant(purpose.value,destination.value))ctx.render();},{glyph:'shield'}))));
}
async function registries(root,ctx){
  const registry=await api('/registries');
  root.append(section('Registered contracts','Inspect the schemas, prompts, capabilities, worker stages and provider controls the running app knows about.',el('p',{class:'notice'},'Registries are code-owned contracts. Extensions add a validated schema, a registered implementation, and tests. Personal settings and authority grants live separately in the private runtime.')));
  for(const [key,value] of Object.entries(registry)){
    if(typeof value!=='object'||value===null)continue;
    root.append(el('details',{class:'card'},el('summary',{},key.replaceAll('_',' '),' · ',Object.keys(value).length,' entries'),pretty(value)));
  }
  if(ctx.state.settings.advanced){
    const editor=el('textarea',{rows:18,spellcheck:'false','aria-label':'Advanced settings JSON'});editor.value=JSON.stringify(ctx.state.settings,null,2);
    root.append(section('Advanced settings JSON','Validated against app-settings/v1. Unknown keys and invalid bounds are rejected.',editor,el('div',{class:'row'},button('Validate & save',async()=>{const value=JSON.parse(editor.value);await ctx.saveSettings(()=>value);toast('Validated settings saved');ctx.render();},{kind:'primary'}),button('Inspect schema',async()=>modal('Settings schema',pretty(await api('/settings/schema'))),{kind:'ghost'}))));
  }
}
