import {el, button, field, badge, api, toast, modal, pretty, grant} from './ui.js';
import {parameterFields} from './controls.js';

export async function checkFit(selection) {
  const result = await api('/models/assess', {method:'POST', body:selection});
  const value = result.assessment;
  modal(`Capacity · ${selection.model}`, el('div',{class:'stack'},
    badge(value.status.replaceAll('_',' '), value.status==='eligible'?'green':'amber'),
    el('p',{},...value.reasons),
    value.required_memory_mib ? el('p',{class:'hint'},`${value.required_memory_mib.toLocaleString()} MiB estimated · ${value.required_cpu_units} CPU slot(s). This is a fresh snapshot; every job checks again.`) : null,
    el('p',{class:'hint'},'The first estimator uses CPU inference, reserved OS headroom, model weights, context cache and runtime buffers. GPU offload and unknown architectures need a registered calibration.'),
    el('details',{},el('summary',{},'Inspect evidence and effective parameters'),pretty(result))));
  return value;
}

export async function editSpecialist(ctx, name, existing=null) {
  const selection=existing?.selection||{provider:'ollama',model:name,parameters:{}};
  const taskFields = new Map(['general','coding','vision'].map(task=>[task,el('input',{type:'checkbox',checked:(existing?.tasks||['coding']).includes(task),'aria-label':`${task} specialist`})]));
  const priority=el('input',{type:'number',min:0,max:1000,step:1,value:existing?.priority??100,'aria-label':'Specialist priority'});
  const content=el('div',{class:'stack'},el('p',{},'Declare where you want this installed model considered. These are your expertise labels, not benchmark scores. Provider-reported modalities and current resources are checked independently.'),
    ...[...taskFields].map(([task,input])=>el('label',{class:'check-row'},input,task[0].toUpperCase()+task.slice(1))),
    el('p',{class:'hint'},'Vision is registered for extension; image input is not yet connected to the guarded chat pipeline.'),field('Priority',priority,'Lower comes first. Ties use the smaller memory estimate, then model ID.'));
  const fields=await parameterFields(selection); content.append(el('details',{},el('summary',{},'Specialist generation parameters'),fields.root));
  const dialog=modal(`Specialist · ${name}`,content,[button('Cancel',()=>document.querySelector('#dialog').close()),button('Register specialist',async()=>{
    if(!priority.checkValidity())throw new Error('Check the priority');
    const tasks=[...taskFields].filter(([,input])=>input.checked).map(([task])=>task);
    if(!tasks.length)throw new Error('Choose at least one task');
    const entry={selection:{...selection,parameters:fields.read()},tasks,priority:Number(priority.value)};
    await ctx.saveSettings(settings=>{settings.task_routing.specialists=settings.task_routing.specialists.filter(item=>item.selection.model!==name);settings.task_routing.specialists.push(entry);return settings;});
    dialog.close();toast('Installed specialist registered');ctx.render();
  },{kind:'primary'})]);
}

export function specialistSettings(ctx) {
  const config=ctx.state.settings.task_routing;
  const enabled=el('input',{type:'checkbox',role:'switch',checked:config.enabled,'aria-label':'Automatic specialist routing'});
  const fallback=el('input',{type:'checkbox',role:'switch',checked:config.allow_default_fallback,'aria-label':'Use default model when no specialist fits'});
  const root=el('section',{class:'card stack'},el('h2',{},'Installed specialists'),
    el('p',{class:'subtitle'},'Choose the downloads. Prometheist chooses among your registered installed models using explicit task, capability and resource rules.'),
    el('label',{class:'check-row'},enabled,'Automatically choose an eligible specialist'),el('label',{class:'check-row'},fallback,'Offer the local default after catalog and OpenAI review'),
    el('p',{class:'hint'},'Order: installed specialist → capability catalog search → optional OpenAI review → local default. Explicit stage routes win. Auto detects /code or fenced code; use the task selector for other coding requests. No automatic downloads or cloud calls.'),
    el('div',{class:'row'},button('Save routing rules',async()=>{await ctx.saveSettings(settings=>{settings.task_routing.enabled=enabled.checked;settings.task_routing.allow_default_fallback=fallback.checked;return settings;});toast('Routing rules saved');},{kind:'primary'}),button('Choose installed models',()=>ctx.navigate('models'),{glyph:'cube'})));
  for(const entry of config.specialists)root.append(el('div',{class:'setting-row'},el('div',{},el('h3',{},entry.selection.model),el('p',{},`${entry.tasks.join(', ')} · priority ${entry.priority}`)),el('div',{class:'row'},button('Edit',()=>editSpecialist(ctx,entry.selection.model,entry)),button('Remove',async()=>{await ctx.saveSettings(settings=>{settings.task_routing.specialists=settings.task_routing.specialists.filter(item=>item.selection.model!==entry.selection.model);return settings;});ctx.render();},{kind:'ghost'}))));
  return root;
}

export async function continueFallback(ctx) {
  const plan=ctx.state.fallbackPlan;
  if(!plan){ctx.state.modelTab='openai';ctx.render();return;}
  if(await reviewFallback(ctx,plan,true)==='default'){
    ctx.state.fallbackPlan=null;ctx.navigate('chat');await ctx.resumeDefault();
  }
}

export async function reviewFallback(ctx, plan, startWithCloud=false) {
  ctx.state.fallbackPlan=plan;
  return new Promise(resolve=>{
    const content=el('div',{class:'stack'});
    const dialog=modal('Choose the next model option',content);
    let settled=false;
    const finish=value=>{if(!settled){settled=true;resolve(value);}dialog.close();};
    dialog.addEventListener('close',()=>{if(!settled){settled=true;resolve(null);}},{once:true});
    const actions=dialog.querySelector('.dialog-actions');
    const showCloud=()=>{
      content.replaceChildren(badge('2 · Optional OpenAI review','amber'),el('h3',{},'Would you like to use a cloud model?'),
        el('p',{},'Choose a Responses-compatible model and connect your own key. Prompts and selected evidence would go to OpenAI only after destination consent; API charges may apply.'),
        el('p',{class:'hint'},'Reviewing this option makes no model call. You can continue to the local default instead.'),
        ...plan.reasons.map(reason=>el('p',{class:'hint'},reason)));
      actions.replaceChildren(button('Choose OpenAI',()=>{finish(null);ctx.state.modelTab='openai';ctx.navigate('models');},{glyph:'cloud'}),
        button('Continue to local default',()=>{
          content.replaceChildren(badge('3 · Local default'),el('h3',{},ctx.state.settings.selection.model),el('p',{},'The installed specialist, catalog and optional cloud choices have been reviewed. Recheck current capacity and use your local default?'));
          actions.replaceChildren(button('Back',showCloud),button('Use local default',()=>finish('default'),{kind:'primary',disabled:!ctx.state.settings.task_routing.allow_default_fallback}));
          if(!ctx.state.settings.task_routing.allow_default_fallback)content.append(el('p',{class:'notice'},'Default fallback is disabled in Model routing settings.'));
        },{kind:'primary'}));
    };
    if(startWithCloud){showCloud();return;}
    const results=el('div',{class:'stack'});
    content.append(badge('1 · Capability catalog search'),el('p',{},plan.specialist_offer||'No eligible installed specialist.'),
      ...Object.entries(plan.routing_exclusions||{}).map(([model,reason])=>el('p',{class:'hint'},`${model}: ${reason}`)),
      el('p',{class:'hint'},'Search uses a fixed public task query. Your message is not sent. You choose the exact model and tag before any download.'),results);
    actions.replaceChildren(button('Search specialists',async()=>{
      // Consent uses the same dialog surface, so request it before reopening this review.
      finish(null);
      if(!await grant('model_catalog','https://ollama.com'))return;
      ctx.state.fallbackPlan=plan;ctx.state.specialistTask=plan.task;ctx.state.modelTab='catalog';ctx.state.runSpecialistSearch=true;ctx.navigate('models');
    },{glyph:'search',kind:'primary'}),button('Continue to OpenAI review',showCloud));
  });
}

export async function previewRoute(ctx) {
  const text=ctx.state.draft.trim()||'Preview a general conversation';
  const plan=await api('/routing/preview',{method:'POST',body:{text,conversation_id:ctx.state.conversation,task:ctx.state.task}});
  modal('Model route for this task',el('div',{class:'stack'},badge(plan.status.replaceAll('_',' '),plan.status==='eligible'?'green':'amber'),
    el('p',{},`${plan.task}: ${plan.classification_reason}`),el('p',{},plan.route_reason),
    el('p',{class:'hint'},`One local model at a time · ${plan.required_memory_mib.toLocaleString()} MiB peak estimate including worker overhead.`),
    ...Object.entries(plan.routing_exclusions||{}).map(([model,reason])=>el('p',{class:'hint'},`${model}: ${reason}`)),
    ...Object.entries(plan.stages).map(([stage,selection])=>el('p',{class:'hint'},`${stage}: ${selection.model}`)),
    ...plan.reasons.map(reason=>el('p',{},reason)),plan.specialist_offer?el('p',{class:'notice'},plan.specialist_offer):null,
    el('p',{class:'hint'},plan.capacity_basis==='after_unload_estimate'?'This estimate includes memory reported by currently loaded models. Sending unloads them and checks actual free memory before starting.':'No inference, download or unloading took place. The worker unloads local models and measures again before execution.'),
    el('details',{},el('summary',{},'Decision inputs and evidence'),pretty(plan))),
    [button('Close',()=>document.querySelector('#dialog').close()),button('Find a specialist',()=>{document.querySelector('#dialog').close();ctx.state.specialistTask=plan.task;ctx.state.modelTab='catalog';ctx.navigate('models');},{glyph:'search'}),
      ...(plan.openai_offer?[button('Review OpenAI',()=>{document.querySelector('#dialog').close();ctx.state.modelTab='openai';ctx.navigate('models');},{glyph:'cloud'})]:[])]);
}
