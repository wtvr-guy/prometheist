import {el, icon, button, field, badge, api, toast} from './ui.js';

const suggestions = {temperature:.65, top_p:.9, top_k:40, min_p:0, seed:0, num_predict:1024, max_output_tokens:8192, num_ctx:4096, num_keep:0, repeat_last_n:64, repeat_penalty:1, presence_penalty:0, frequency_penalty:0, num_thread:4, num_batch:512, num_gpu:-1, main_gpu:0, draft_num_predict:0, keep_alive:300};
export async function parameterFields(selection, {compact = false} = {}) {
  let metadata = null;
  let catalog;
  let warning;
  if (selection.provider === 'ollama') {
    try { metadata = await api(`/models/details?model=${encodeURIComponent(selection.model)}`); catalog = metadata.controls; }
    catch (error) { warning = error.message; }
  }
  if (!catalog) catalog = await api(`/models/parameters?provider=${selection.provider}&model=${encodeURIComponent(selection.model)}`);
  const controls = new Map();
  const root = el('div', {class:'parameter-fields'});
  root.append(el('p', {class:'hint'}, 'Enable a switch to override a value. Disabled switches inherit model and runtime defaults. Sampling controls affect the final response.'));
  if (metadata) root.append(el('div', {class:'row'}, ...metadata.capabilities.map(value => badge(value))), el('details', {}, el('summary', {}, 'Reported model defaults'), el('pre', {class:'json'}, metadata.parameters || 'The model did not report parameter defaults.')));
  if (warning) root.append(el('p', {class:'notice'}, 'Model metadata is unavailable. Showing registered controls; capability checks run again before chat.'));
  if (selection.provider === 'openai') root.append(el('p', {class:'notice'}, 'The OpenAI model list does not expose parameter schemas. Controls use a conservative family profile; the API validates exact model support.'));
  const groups = [...new Set(Object.values(catalog).map(spec => spec.group))];
  for (const group of groups) {
    root.append(el('h3', {class:'parameter-group'}, group));
    for (const [name, spec] of Object.entries(catalog).filter(([, value]) => value.group === group)) {
      const overridden = Object.hasOwn(selection.parameters, name);
      const value = selection.parameters[name];
      const enabled = el('input', {type:'checkbox', role:'switch', checked:overridden, 'aria-label':`Override ${spec.label}`});
      let input;
      if (spec.kind === 'boolean') input = el('select', {'aria-label':spec.label}, el('option', {value:'true'}, 'Enabled'), el('option', {value:'false'}, 'Disabled'));
      else if (spec.kind === 'choice') input = el('select', {'aria-label':spec.label}, ...spec.choices.map(choice => el('option', {value:choice}, choice)));
      else if (spec.kind === 'strings') input = el('textarea', {'aria-label':spec.label, rows:2, placeholder:'One sequence per line'});
      else input = el('input', {type:'number', step:spec.kind === 'integer' ? 1 : .01, min:spec.minimum, max:spec.maximum, 'aria-label':spec.label});
      input.value = spec.kind === 'strings' ? (value || []).join('\n') : value ?? (spec.kind === 'choice' ? spec.choices[0] : spec.kind === 'boolean' ? 'true' : Math.min(spec.maximum, suggestions[name] ?? spec.minimum));
      input.disabled = !overridden;
      enabled.addEventListener('change', () => { input.disabled = !enabled.checked; });
      controls.set(name, {enabled, input, spec});
      root.append(el('div', {class:'parameter'}, el('label', {}, el('span', {}, spec.label, spec.scope === 'all' ? ' · all workers' : ''), enabled), el('span', {class:'hint'}, spec.description), input));
    }
  }
  return {root, read() {
    const result = {};
    for (const [name, {enabled, input, spec}] of controls) {
      if (!enabled.checked) continue;
      if (!input.checkValidity()) { input.reportValidity(); throw new Error(`Check ${spec.label}`); }
      result[name] = spec.kind === 'strings' ? input.value.split('\n').filter(Boolean) : spec.kind === 'boolean' ? input.value === 'true' : spec.kind === 'choice' ? input.value : Number(input.value);
    }
    return result;
  }};
}

export async function inspector(ctx) {
  const container = el('aside', {class:'inspector', 'aria-label':'Generation controls'}, el('div', {class:'inspector-title'}, el('h2', {}, 'Generation'), button('', () => ctx.toggleControls(false), {glyph:'close', kind:'icon-button', 'aria-label':'Close generation controls'})));
  const selection = ctx.state.settings.selection;
  const responder = ctx.state.settings.routes.V2_RESPOND;
  if (responder) container.append(el('p', {class:'notice'}, `Final responses use the explicit ${responder.model} route. Change its parameters in Settings → Model routing.`));
  const provider = el('select', {}, el('option', {value:'ollama'}, 'Ollama · local'), el('option', {value:'openai'}, 'OpenAI · cloud'));
  provider.value = selection.provider;
  const model = el('input', {value:selection.model, list:'model-options', 'aria-label':'Model ID', autocomplete:'off'});
  const choices = el('datalist', {id:'model-options'});
  container.append(el('div', {class:'stack'}, field('Provider', provider), field('Model', model, 'Choose an installed model or enter an exact ID.'), choices,
    button('Use model', async () => { await ctx.saveSettings({selection:{provider:provider.value, model:model.value.trim(), parameters:{}}}); ctx.render(); }, {glyph:'check'}),
    button('Manage models', () => ctx.navigate('models'), {glyph:'cube', kind:'ghost'})));
  try {
    const result = selection.provider === 'ollama' ? await api('/models') : null;
    if (result) choices.replaceChildren(...result.models.map(item => el('option', {value:item.name})));
  } catch { /* The editable model field remains available while services are offline. */ }
  provider.addEventListener('change', () => { model.value = ''; choices.replaceChildren(); });
  try {
    const fields = await parameterFields(selection, {compact:true});
    container.append(fields.root, el('div', {class:'settings-save'}, button('Save overrides', async () => {
      await ctx.saveSettings({selection:{...selection, parameters:fields.read()}});
      toast('Generation overrides saved for new jobs');
    }, {kind:'primary'})));
  } catch (error) { container.append(el('p', {class:'notice'}, error.message)); }
  return container;
}
