export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === undefined || value === null) continue;
    if (key === 'class') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'text') node.textContent = value;
    else if (['value', 'checked', 'disabled', 'selected', 'hidden', 'open'].includes(key)) node[key] = value;
    else node.setAttribute(key, String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child !== null && child !== undefined && child !== false) node.append(child instanceof Node ? child : String(child));
  }
  return node;
}
const paths = {
  folder: 'M3 7V4h6l2 3h10v13H3V7Z',
  file: 'M14 2H5v20h14V7l-5-5Zm0 0v6h5M8 13h8m-8 4h6',
  edit: 'm15 4 5 5M4 20l5-1L21 7a2 2 0 0 0-4-4L5 15l-1 5Z',
  chat: 'M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9H13a8.5 8.5 0 0 1 8 8v.5Z',
  cube: 'm12 3 9 5v8l-9 5-9-5V8l9-5Zm0 9 9-4m-9 4L3 8m9 4v9',
  activity: 'M3 12h4l3-8 4 16 3-8h4',
  settings: 'M4 7h16M4 17h16M8 4v6m8 4v6',
  plus: 'M12 5v14M5 12h14',
  arrow: 'M12 19V5m-6 6 6-6 6 6',
  chevron: 'm9 5 7 7-7 7',
  shield: 'm12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6',
  search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  close: 'm6 6 12 12M6 18 18 6',
  download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
  trash: 'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',
  check: 'm5 12 4 4L19 6',
  cloud: 'M7 18a5 5 0 0 1-1-10 7 7 0 0 1 13-1 5.5 5.5 0 0 1-1 11H7Z',
  cpu: 'M7 7h10v10H7zM9 1v3m6-3v3M9 20v3m6-3v3M1 9h3m-3 6h3m16-6h3m-3 6h3',
  menu: 'M4 6h16M4 12h16M4 18h16',
  copy: 'M8 8h13v13H8zM16 8V3H3v13h5',
  refresh: 'M20 7v5h-5M4 17v-5h5M5 8a7 7 0 0 1 12-3l3 4M4 15l3 4a7 7 0 0 0 12-3',
  book: 'M4 3h6l2 2 2-2h6v16h-6l-2 2-2-2H4V3Zm8 2v16',
};
export function icon(name, size = 18) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  for (const [key, value] of Object.entries({viewBox: '0 0 24 24', width: size, height: size, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true'})) svg.setAttribute(key, value);
  const path = document.createElementNS(svg.namespaceURI, 'path');
  path.setAttribute('d', paths[name] || paths.cube); svg.append(path); return svg;
}
export function button(label, action, {kind = '', glyph, title, ...props} = {}) {
  return el('button', {type: 'button', class: `button ${kind}`, title, ...props, onclick: async event => {
    try { await action?.(event); } catch (error) { toast(error.message, true); }
  }}, glyph && icon(glyph), label);
}
export function toast(message, error = false) {
  const node = el('div', {class: `toast ${error ? 'error' : ''}`, role: error ? 'alert' : 'status'}, el('span', {}, message), button('', () => node.remove(), {glyph: 'close', kind: 'icon-button', 'aria-label': 'Dismiss notification'}));
  document.querySelector('#toasts').append(node);
  setTimeout(() => node.remove(), error ? 15000 : 6000);
}
export function field(label, input, hint) {
  return el('label', {class: 'field'}, el('span', {class: 'field-label'}, label), input, hint && el('span', {class: 'hint'}, hint));
}
export function badge(text, tone = '') { return el('span', {class: `badge ${tone}`}, text); }
export function pretty(value) { return el('pre', {class: 'json'}, JSON.stringify(value, null, 2)); }
export function empty(title, text, action) { return el('div', {class: 'empty'}, icon('cube', 28), el('h3', {}, title), el('p', {}, text), action); }
export function bytes(value) { if (!value) return '—'; const units = ['B', 'KB', 'MB', 'GB', 'TB']; const i = Math.min(4, Math.floor(Math.log(value) / Math.log(1024))); return `${(value / 1024 ** i).toFixed(i > 1 ? 1 : 0)} ${units[i]}`; }
export function date(value) { return new Date(value).toLocaleString(undefined, {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}); }
export function modal(title, content, actions = []) {
  const dialog = document.querySelector('#dialog');
  dialog.replaceChildren(el('div', {class: 'dialog-heading'}, el('h2', {id: 'dialog-title'}, title), button('', () => dialog.close(), {glyph:'close', kind:'icon-button', 'aria-label':'Close dialog'})), el('div', {class:'dialog-content'}, content), el('div', {class: 'dialog-actions'}, ...actions));
  if (!dialog.open) dialog.showModal();
  return dialog;
}
export function confirm(title, content, label = 'Confirm', danger = false) {
  return new Promise(resolve => {
    const dialog = modal(title, content, [button('Cancel', () => dialog.close()), button(label, () => { resolve(true); dialog.close(); }, {kind: danger ? 'danger' : 'primary'})]);
    dialog.addEventListener('close', () => resolve(false), {once: true});
  });
}
export async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {credentials:'same-origin', ...options, headers:{'Content-Type':'application/json', ...options.headers}, body: options.body === undefined ? undefined : JSON.stringify(options.body)});
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(item => `${item.loc.slice(1).join('.')}: ${item.msg}`).join('\n') : data.detail;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return data;
}
export async function grant(purpose, destination) {
  const existing = await api('/consents');
  const review = await api('/consents/proposal', {method:'POST', body:{purpose, destination}});
  if (existing.grants.some(item => item.purpose === purpose && item.destination === review.proposal.destination && item.disclosure_sha256 === review.accepted_digest)) return true;
  const accepted = await confirm('Review external access', el('div', {class:'stack'}, badge('Your permission', 'amber'), el('strong', {class:'break'}, review.proposal.destination), el('p', {}, review.proposal.disclosure), el('p', {class:'hint'}, 'This permission lasts until you revoke it in Settings → Privacy.')), 'Allow this destination');
  if (accepted) await api('/consents', {method:'POST', body:{purpose, destination, accepted_digest:review.accepted_digest}});
  return accepted;
}
