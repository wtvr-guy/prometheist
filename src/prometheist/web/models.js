import {el, icon, button, field, badge, pretty, empty, bytes, modal, confirm, api, toast, grant} from './ui.js';
import {checkFit, editSpecialist, continueFallback} from './routing.js';

export async function modelsView(ctx) {
  const {state} = ctx;
  const content=el('div',{class:'content'});
  const root=el('div',{},el('header',{class:'view-header'},el('div',{},el('div',{class:'eyebrow'},'Choose how you think'),el('h1',{},'Your model library'),el('p',{class:'subtitle'},'Run models on your machine, or connect a cloud model for a specific task.')),button('Add a model',()=>addModel(ctx),{glyph:'plus',kind:'primary'})),content);
  content.append(el('nav',{class:'tabs','aria-label':'Model sources'},...[['installed','Installed'],['catalog','Ollama library'],['openai','OpenAI']].map(([id,label])=>button(label,()=>{state.modelTab=id;ctx.render();},{kind:state.modelTab===id?'active':''}))));
  if(state.modelTab==='installed') await installed(content,ctx);
  if(state.modelTab==='catalog') catalog(content,ctx);
  if(state.modelTab==='openai') await cloud(content,ctx);
  return root;
}
async function installed(root,ctx){
  root.append(el('div',{class:'connection-banner'},el('div',{class:'model-symbol'},icon('cpu',22)),el('div',{class:'banner-content'},el('h3',{},'Ollama on your machine'),el('p',{},ctx.state.settings.ollama_url)),button('Connection settings',()=>{ctx.state.settingTab='general';ctx.navigate('settings');},{kind:'ghost'})));
  let models;
  try{models=(await api('/models')).models;}catch(error){root.append(empty('Ollama is not reachable',error.message+' Start Ollama, then refresh this view.',button('Refresh',ctx.render,{glyph:'refresh'})));return;}
  const filter=el('input',{type:'search',placeholder:'Filter installed models…','aria-label':'Filter installed models'});
  const cards=el('div',{class:'cards'});
  root.append(el('div',{class:'searchbar'},filter,button('Refresh',ctx.render,{glyph:'refresh'})),cards);
  const render=()=>{
    const shown=models.filter(model=>model.name.toLowerCase().includes(filter.value.toLowerCase()));
    cards.replaceChildren(...shown.map(model=>{
      const selected=ctx.state.settings.selection.provider==='ollama'&&ctx.state.settings.selection.model===model.name;
      return el('article',{class:'card model-card'},el('div',{class:'card-top'},el('div',{class:'model-symbol'},icon('cube',21)),badge(selected?'Selected':'Installed',selected?'amber':'green')),el('h3',{},model.name),el('p',{class:'model-sub'},[bytes(model.size),model.details?.parameter_size,model.details?.quantization_level].filter(Boolean).join(' · ')),
        el('div',{class:'row'},button('Check capacity',()=>checkFit(selected?ctx.state.settings.selection:{provider:'ollama',model:model.name,parameters:{}}),{glyph:'cpu',kind:'ghost'}),button('Use as specialist',()=>editSpecialist(ctx,model.name,ctx.state.settings.task_routing.specialists.find(item=>item.selection.model===model.name)),{kind:'ghost'})),
        el('div',{class:'row'},button(selected?'Selected':'Use model',()=>selectModel(ctx,'ollama',model.name),{glyph:selected?'check':undefined,kind:selected?'ghost':'primary'}),button('Details',async()=>{const details=await api(`/models/details?model=${encodeURIComponent(model.name)}`);modal(model.name,el('div',{class:'stack'},el('div',{class:'row'},...details.capabilities.map(value=>badge(value))),pretty(details)),[button('Close',()=>document.querySelector('#dialog').close())]);},{kind:'ghost'}),button('',()=>removeModel(ctx,model.name),{glyph:'trash',kind:'icon-button ghost','aria-label':`Delete ${model.name}`})));
    }));
    if(!shown.length)cards.append(empty(models.length?'No models match':'Make room for your first model',models.length?'Try a different filter.':'Search the Ollama library, or add an exact model name.',button('Browse library',()=>{ctx.state.modelTab='catalog';ctx.render();},{glyph:'search'})));
  };
  filter.addEventListener('input',render);render();
}
async function selectModel(ctx,provider,model){
  await ctx.saveSettings({selection:{provider,model,parameters:{}}});toast(`${model} selected for new conversations and tasks`);ctx.render();
}
async function removeModel(ctx,name){
  const input=el('input',{placeholder:name,autocomplete:'off','aria-label':'Type model name to confirm deletion'});
  const dialog=modal('Delete local model weights?',el('div',{class:'stack'},el('p',{},`This removes ${name} from the configured Ollama service. Conversation and evidence records remain available. You can download the model again.`),field('Type the exact model name',input)),[button('Cancel',()=>document.querySelector('#dialog').close()),button('Delete model',async()=>{await api('/models',{method:'DELETE',body:{model:name,confirmation:input.value}});dialog.close();toast('Model weights deleted');ctx.render();},{kind:'danger',glyph:'trash'})]);
}
async function startDownload(ctx,name){
  if(!await grant('model_download','https://registry.ollama.ai'))return;
  await api('/models/pull',{method:'POST',body:{model:name}});await ctx.refreshJobs();toast(`Downloading ${name}`);ctx.navigate('activity');
}
function addModel(ctx,name=''){
  const input=el('input',{value:name,placeholder:'e.g. qwen3:4b',autocomplete:'off','aria-label':'Ollama model name'});
  const dialog=modal('Add an Ollama model',el('div',{class:'stack'},field('Model name and optional tag',input,'Use a library name such as qwen3:4b, or namespace/model:tag.'),el('p',{class:'hint'},'Ollama downloads weights into its own model directory. Check model size and your available memory before choosing a large model.')),[button('Cancel',()=>document.querySelector('#dialog').close()),button('Review download',async()=>{const name=input.value.trim();if(!name)throw new Error('Enter a model name');dialog.close();await startDownload(ctx,name);},{glyph:'download',kind:'primary'})]);
}
function catalog(root,ctx){
  const query=el('input',{type:'search',placeholder:'Search the Ollama library…','aria-label':'Search Ollama library',maxlength:200});
  const categoryLabels={general:'General',coding:'Coding',vision:'Vision',tools:'Tool use',thinking:'Reasoning',embedding:'Embedding',base:'Base / foundation'};
  const task=el('select',{'aria-label':'Specialist category'},...Object.entries(categoryLabels).map(([value,label])=>el('option',{value},label)));
  task.value=ctx.state.specialistTask||'coding';
  const results=el('div',{class:'cards'});
  const specialistSearch=async()=>{
    if(!await grant('model_catalog','https://ollama.com'))return;
    results.replaceChildren(empty('Matching advertised capabilities…','Fixed public queries are sent for this category. Your message and files stay here.'));
    const data=await api(`/models/specialists?task=${task.value}`);
    const filter=data.resource_filter;
    const cards=[];
    if(filter)cards.push(el('p',{class:'notice'},filter.calibration_sample_count
      ?`Sizes estimated to exceed this host's ~${Math.round(filter.ceiling_mib/1024)} GB usable memory (from ${filter.calibration_sample_count} installed model${filter.calibration_sample_count===1?'':'s'}) are hidden or flagged below.`
      :"Install at least one model to enable capacity-based filtering; nothing is hidden by size yet."));
    cards.push(...data.models.map(model=>el('article',{class:'card model-card'},
      el('h3',{},model.name),el('div',{class:'row'},...model.advertised_capabilities.map(value=>badge(value))),
      el('p',{class:'hint'},model.advertised_sizes.length?`Advertised sizes: ${model.advertised_sizes.join(', ')}`:'Exact local sizes are not reported in this result.'),
      model.resource_filtered_sizes&&model.resource_filtered_sizes.length?el('p',{class:'hint'},`Estimated too large for this host: ${model.resource_filtered_sizes.join(', ')}`):null,
      el('p',{class:'hint'},model.verification),
      el('div',{class:'row'},button('Choose tag to download',()=>addModel(ctx,model.name),{glyph:'download',kind:'primary'}),el('a',{href:model.url,target:'_blank',rel:'noopener noreferrer',class:'button ghost'},'Review model')))));
    if(!data.models.length)cards.push(empty('No advertised catalog matches','The fixed queries and advertised capability filters returned no candidates. You can broaden the ordinary search or add a model by its exact ID.'));
    if(data.openai_offer)cards.push(el('article',{class:'card stack'},el('h3',{},'No suitable local option?'),el('p',{class:'hint'},'Next: optional OpenAI review, then your local default. You choose the model and route, connect a key, and review destination consent before cloud inference. API charges may apply.'),button('Continue to OpenAI review',()=>continueFallback(ctx),{glyph:'cloud'})));
    results.replaceChildren(...cards);
  };
  const search=async()=>{
    if(!await grant('model_catalog','https://ollama.com'))return;
    results.replaceChildren(empty('Searching the library…','The request goes directly to ollama.com.'));
    try{const data=await api(`/models/search?q=${encodeURIComponent(query.value)}`);
      results.replaceChildren(...data.models.map(model=>el('article',{class:'card model-card'},el('div',{class:'card-top'},el('div',{class:'model-symbol'},icon('cube')),badge('Ollama library')),el('h3',{},model.name),el('p',{class:'model-sub'},'Choose a size or tag before downloading.'),el('div',{class:'row'},button('Add model',()=>addModel(ctx,model.name),{glyph:'plus',kind:'primary'}),el('a',{href:model.url,target:'_blank',rel:'noopener noreferrer',class:'button ghost'},'Model page')))));
      if(!data.models.length)results.append(empty('No catalog matches','Try a shorter query or add an exact model name. The public catalog page may also have changed.'));
    }catch(error){results.replaceChildren(empty('Search unavailable',error.message,el('a',{href:'https://ollama.com/search',target:'_blank',rel:'noopener noreferrer',class:'button'},'Open Ollama library')));}
  };
  query.addEventListener('keydown',event=>{if(event.key==='Enter')search().catch(error=>toast(error.message,true));});
  root.append(el('div',{class:'searchbar'},query,button('Search library',search,{glyph:'search',kind:'primary'})),el('div',{class:'row'},task,button('Find task specialist',specialistSearch,{glyph:'search'})),el('p',{class:'notice'},'Browse on demand. Library searches and model downloads each have their own external-access permission. Nothing is downloaded automatically. Specialist search uses registered rules and advertised metadata; exact capabilities and capacity are checked after installation.'),results);
  results.append(empty('Find a model that fits','Search by model family or enter an exact model name. Metadata becomes available after the model is installed.',button('Add by name',()=>addModel(ctx),{glyph:'plus'})));
  if(ctx.state.runSpecialistSearch){ctx.state.runSpecialistSearch=false;specialistSearch().catch(error=>toast(error.message,true));}
}
async function cloud(root,ctx){
  const connected=ctx.state.bootstrap.openai_connected;
  root.append(el('div',{class:'connection-banner'},el('div',{class:'model-symbol'},icon('cloud',23)),el('div',{class:'banner-content'},el('h3',{},'OpenAI API'),el('p',{},connected?'API key available in this app session.':'Connect your own API key. API usage is billed by OpenAI.')),
    connected?button('Disconnect',async()=>{const result=await api('/openai/key',{method:'DELETE',body:{}});ctx.state.bootstrap.openai_connected=false;toast(result.effect);ctx.render();},{kind:'ghost'}):button('Connect OpenAI',()=>connectCloud(ctx),{kind:'primary'})));
  root.append(el('p',{class:'notice'},'Cloud requests can contain your current prompt and selected personal evidence. Each request uses store: false; OpenAI’s own retention and abuse-monitoring policies still apply. Only explicitly selected stages use OpenAI.'));
  if(ctx.state.fallbackPlan)root.append(el('div',{class:'row'},button('Continue fallback review',()=>continueFallback(ctx),{kind:'ghost'})));
  const model=el('input',{placeholder:'Exact OpenAI model ID', 'aria-label':'OpenAI model ID'});
  const filter=el('input',{type:'search',placeholder:'Filter available model IDs…','aria-label':'Filter OpenAI model IDs'});
  const results=el('div',{class:'cards'});
  const choose=()=>selectModel(ctx,'openai',model.value.trim());
  root.append(el('div',{class:'searchbar'},model,button('Use model ID',choose,{glyph:'check'})),el('div',{class:'searchbar'},filter,button('Load available models',async()=>{
    if(!await grant('model_inference','https://api.openai.com'))return;
    const items=(await api('/openai/models')).models;
    const draw=()=>{const shown=items.filter(item=>item.id.toLowerCase().includes(filter.value.toLowerCase()));results.replaceChildren(...shown.map(item=>el('article',{class:'card model-card'},el('div',{class:'card-top'},el('div',{class:'model-symbol'},icon('cloud')),badge('Cloud','amber')),el('h3',{},item.id),el('p',{class:'model-sub'},'API-listed ID · task compatibility checked on use'),el('div',{class:'row'},button('Select',()=>selectModel(ctx,'openai',item.id),{kind:'primary'})))));};filter.addEventListener('input',draw);draw();
  },{glyph:'refresh',disabled:!connected})),results);
  results.append(empty('Use cloud intelligence deliberately','Select a Responses-compatible text model, then use Settings → Model routing to assign it only to the tasks you choose.'));
}
async function connectCloud(ctx){
  if(!await grant('model_inference','https://api.openai.com'))return;
  const key=el('input',{type:'password',autocomplete:'off',spellcheck:'false',placeholder:'Paste your API key','aria-label':'OpenAI API key'});
  const dialog=modal('Connect your OpenAI account',el('div',{class:'stack'},field('API key',key,'Held in server memory until the app exits. Never saved in settings or browser storage.'),el('p',{class:'hint'},'Alternatively, set OPENAI_API_KEY before launching the app. This does not use a ChatGPT subscription.')),[button('Cancel',()=>document.querySelector('#dialog').close()),button('Connect',async()=>{const value=key.value;key.value='';await api('/openai/key',{method:'POST',body:{key:value}});ctx.state.bootstrap.openai_connected=true;dialog.close();toast('API key connected for this session');ctx.render();},{kind:'primary'})]);
}
