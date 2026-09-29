import {el, icon, button, field, badge, pretty, empty, bytes, date, modal, confirm, api, toast} from './ui.js';

const join=(parent,name)=>[parent,name].filter(Boolean).join('/');
const query=(root,path)=>`root=${encodeURIComponent(root)}&path=${encodeURIComponent(path)}`;
export async function filesView(ctx){
  const state=ctx.state;
  state.files ||= {root:'files',path:'',query:'',offset:0};
  const location=state.files;
  const roots=(await api('/files/roots')).roots;
  const selected=roots.find(root=>root.id===location.root)||roots[0];location.root=selected.id;
  const content=el('div',{class:'content'});
  const root=el('div',{},el('header',{class:'view-header'},el('div',{},el('div',{class:'eyebrow'},'A place for everything'),el('h1',{},'Files'),el('p',{class:'subtitle'},'Your persistent files, source material, and runtime records. Always on your machine.')),el('div',{class:'row'},button('File activity',()=>fileHistory(ctx),{glyph:'activity'}),button('Add local folder',()=>addRoot(ctx),{glyph:'plus'}))),content);
  const picker=el('select',{'aria-label':'File workspace'},...roots.map(item=>el('option',{value:item.id},item.label+(item.writable?'':' · read-only'))));picker.value=selected.id;
  picker.addEventListener('change',()=>{state.files={root:picker.value,path:'',query:'',offset:0};ctx.render();});
  const search=el('input',{type:'search',value:location.query,placeholder:'Search names within this folder…','aria-label':'Search files',maxlength:200});
  const runSearch=()=>{location.query=search.value.trim();location.offset=0;ctx.render();};
  search.addEventListener('keydown',event=>{if(event.key==='Enter')runSearch();});
  const upload=el('input',{type:'file',multiple:true,hidden:true,'aria-label':'Choose files to upload'});
  upload.addEventListener('change',()=>uploadFiles(ctx,[...upload.files],{...location}).catch(error=>toast(error.message,true)));
  content.append(el('div',{class:'file-location'},el('div',{class:'row spread'},el('div',{class:'row'},picker,badge(selected.writable?'Read & write':'Read-only',selected.writable?'green':'')),el('span',{class:'hint break'},selected.path)),el('div',{class:'row'},button('New folder',()=>createEntry(ctx,'folder'),{glyph:'plus',disabled:!selected.writable}),button('New text file',()=>createEntry(ctx,'text'),{glyph:'book',disabled:!selected.writable}),button('Upload files',()=>upload.click(),{glyph:'arrow',disabled:!selected.writable}),upload,button('Refresh',ctx.render,{glyph:'refresh',kind:'ghost'}),!['files','runtime'].includes(selected.id)?button('Remove access',async()=>{if(await confirm('Remove this folder from Files?',el('p',{},'The files themselves will stay where they are. This removes the app’s access through this folder scope.'),'Remove access')){await api(`/files/roots/${selected.id}`,{method:'DELETE',body:{}});state.files={root:'files',path:'',query:'',offset:0};ctx.render();}},{kind:'ghost'}):null)),
    el('div',{class:'searchbar'},search,button('Search',runSearch,{glyph:'search'}),location.query?button('Clear',()=>{location.query='';location.offset=0;ctx.render();},{kind:'ghost'}):null));
  const crumbs=el('nav',{class:'file-breadcrumbs','aria-label':'Folder path'},button(selected.label,()=>openFolder(ctx,''),{kind:'ghost'}));
  let path='';for(const part of location.path.split('/').filter(Boolean)){path=join(path,part);const destination=path;crumbs.append(icon('chevron',12),button(part,()=>openFolder(ctx,destination),{kind:'ghost'}));}
  content.append(crumbs);
  let data;
  try{data=await api(`/files?${query(location.root,location.path)}&offset=${location.offset}&q=${encodeURIComponent(location.query)}`);}catch(error){content.append(empty('This folder cannot be opened',error.message,button('Go to workspace root',()=>openFolder(ctx,''))));return root;}
  content.append(el('div',{class:'row spread file-summary'},el('span',{class:'hint'},`${data.total} ${location.query?'matches':'items'}${data.truncated?' · scan limit reached; narrow this folder':''}`),el('span',{class:'hint'},`${bytes(data.free_bytes)} available on this volume`)));
  if(!data.items.length){content.append(empty(location.query?'No matching filenames':'This folder is ready','Files you add here stay local. Viewing a file does not add it to memory or send it to a model.',selected.writable?button('Create a note',()=>createEntry(ctx,'text'),{glyph:'plus'}):null));return root;}
  const body=el('tbody',{});
  for(const item of data.items){
    const fileButton=button(item.name,()=>item.kind==='folder'?openFolder(ctx,item.path):preview(ctx,item),{glyph:item.kind==='folder'?'folder':'file',kind:'file-name ghost',disabled:!['file','folder'].includes(item.kind)});
    const actions=el('div',{class:'row file-actions'});
    if(item.kind==='file')actions.append(el('a',{class:'button icon-button ghost',href:`/api/files/download?${query(location.root,item.path)}`,'aria-label':`Download ${item.name}`,title:'Download',download:item.name},icon('download',16)));
    if(['file','folder'].includes(item.kind))actions.append(button('',()=>relocate(ctx,item,true),{glyph:'copy',kind:'icon-button ghost','aria-label':`Copy ${item.name}`,title:'Copy'}));
    if(selected.writable&&['file','folder'].includes(item.kind))actions.append(button('',()=>relocate(ctx,item,false),{glyph:'edit',kind:'icon-button ghost','aria-label':`Rename or move ${item.name}`,title:'Rename or move'}),button('',()=>trash(ctx,item),{glyph:'trash',kind:'icon-button ghost','aria-label':`Move ${item.name} to Trash`,title:'Move to Trash'}));
    body.append(el('tr',{},el('td',{},fileButton,location.query?el('div',{class:'hint break'},item.path):null),el('td',{class:'file-size'},item.kind==='file'?bytes(item.size):badge(item.kind)),el('td',{class:'file-date'},date(item.modified)),el('td',{},actions)));
  }
  content.append(el('div',{class:'table-wrap file-table'},el('table',{class:'data-table'},el('thead',{},el('tr',{},el('th',{},'Name'),el('th',{},'Size'),el('th',{},'Modified'),el('th',{},'Actions'))),body)),el('div',{class:'row file-pagination'},button('Previous',()=>{location.offset=Math.max(0,location.offset-250);ctx.render();},{disabled:location.offset===0}),el('span',{class:'hint'},`${location.offset+1}–${Math.min(location.offset+250,data.total)} of ${data.total}`),button('Next',()=>{location.offset=data.next_offset;ctx.render();},{disabled:data.next_offset===null})));
  return root;
}
function openFolder(ctx,path){ctx.state.files.path=path;ctx.state.files.offset=0;ctx.state.files.query='';ctx.render();}
function createEntry(ctx,kind){
  const location={...ctx.state.files};
  const name=el('input',{placeholder:kind==='folder'?'Folder name':'note.md','aria-label':kind==='folder'?'Folder name':'File name'});
  const text=el('textarea',{rows:12,placeholder:'Start writing…','aria-label':'New file content',class:'file-editor'});
  const dialog=modal(kind==='folder'?'New folder':'New text file',el('div',{class:'stack'},field('Name',name),kind==='text'?text:null),[button('Cancel',()=>document.querySelector('#dialog').close()),button('Create',async()=>{if(!name.value.trim()||name.value.includes('/'))throw new Error('Enter a single file or folder name');const payload={root:location.root,path:join(location.path,name.value.trim())};await api(kind==='folder'?'/files/folders':'/files/text',{method:kind==='folder'?'POST':'PUT',body:kind==='folder'?payload:{...payload,text:text.value}});dialog.close();toast(kind==='folder'?'Folder created':'File created');ctx.render();},{kind:'primary'})]);
}
async function preview(ctx,item){
  const location={...ctx.state.files};
  const data=await api(`/files/preview?${query(location.root,item.path)}`);
  const content=el('div',{class:'stack'},el('div',{class:'row'},badge(data.mime),badge(bytes(data.size)),badge(data.editable?'Editable':'Read-only')));
  const actions=[];
  if(data.text!==null){
    const editor=el('textarea',{rows:19,class:'file-editor','aria-label':`Contents of ${item.name}`,spellcheck:'false',readonly:!data.editable?'':undefined});editor.value=data.text;
    content.append(editor);
    if(data.editable)actions.push(button('Save changes',async()=>{await api('/files/text',{method:'PUT',body:{root:location.root,path:item.path,text:editor.value,revision:data.revision}});document.querySelector('#dialog').close();toast('Saved. The previous content is available in File activity.');ctx.render();},{kind:'primary'}));
  }else if(['image/png','image/jpeg','image/gif','image/webp'].includes(data.mime))content.append(el('img',{src:`/api/files/media?${query(location.root,item.path)}`,alt:item.name,class:'file-preview-image'}));
  else if(['audio/mpeg','audio/wav','video/mp4','video/webm'].includes(data.mime))content.append(el(data.mime.startsWith('video')?'video':'audio',{controls:'',src:`/api/files/media?${query(location.root,item.path)}`,class:'file-preview-media'}));
  else content.append(empty('Open with a local application',data.reason||'Download this file to open its original format.'));
  actions.unshift(el('a',{href:`/api/files/download?${query(location.root,item.path)}`,class:'button',download:item.name},icon('download'),'Download'),button('Close',()=>document.querySelector('#dialog').close(),{kind:'ghost'}));
  modal(item.name,content,actions);
}
async function relocate(ctx,item,copy){
  const location={...ctx.state.files};
  const roots=(await api('/files/roots')).roots.filter(root=>root.writable);
  const target=el('select',{'aria-label':'Destination workspace'},...roots.map(root=>el('option',{value:root.id},root.label)));target.value=roots.some(root=>root.id===location.root)?location.root:roots[0]?.id;
  const destination=el('input',{value:copy?join(location.path,`copy-${item.name}`):item.path,'aria-label':'Destination relative path'});
  const dialog=modal(copy?'Copy to a folder':'Rename or move',el('div',{class:'stack'},field('Destination workspace',target),field('New relative path',destination,'The parent folder must already exist. Existing files are never overwritten.')),[button('Cancel',()=>document.querySelector('#dialog').close()),button(copy?'Start copy':'Move',async()=>{await api('/files/relocate',{method:'POST',body:{root:location.root,path:item.path,revision:item.revision,destination_root:target.value,destination:destination.value,copy}});dialog.close();if(copy){await ctx.refreshJobs();ctx.navigate('activity');}else{toast('File moved');ctx.render();}},{kind:'primary'})]);
}
async function trash(ctx,item){
  if(!await confirm('Move to Trash?',el('p',{},`${item.name} will move to a private Trash folder on the same volume. Restore it from File activity.`),'Move to Trash',true))return;
  await api('/files/trash',{method:'POST',body:{root:ctx.state.files.root,path:item.path,revision:item.revision}});toast('Moved to Trash');ctx.render();
}
async function fileHistory(ctx){
  const operations=(await api('/files/history')).operations;
  const restored=new Set(operations.filter(item=>item.action==='restore'&&item.status==='completed').map(item=>item.details.original));
  const content=el('div',{class:'stack'},el('p',{class:'hint'},'Completed file actions have local receipts. An intent without completion may need inspection. Cancelled copies can leave a partial destination. Trash is never automatically emptied.'));
  for(const item of operations){
    const row=el('div',{class:'setting-row'},el('div',{},el('h3',{},item.action,' · ',item.details.path||item.details.original),el('p',{},date(item.created_at),' · ',item.status)),el('div',{class:'row'}));
    if(item.action==='trash'&&item.status==='completed'&&!restored.has(item.id))row.lastChild.append(button('Restore',async()=>{await api(`/files/restore/${item.id}`,{method:'POST',body:{}});toast('Restored to its original path');await fileHistory(ctx);ctx.render();},{glyph:'refresh'}));
    if(item.action==='write'&&item.details.previous_revision)row.lastChild.append(el('a',{class:'button',href:`/api/files/versions/${item.id}`,download:'previous-content.txt'},'Previous version'));
    row.lastChild.append(button('Receipt',()=>modal('File operation',pretty(item)),{kind:'ghost'}));content.append(row);
  }
  if(!operations.length)content.append(empty('No file operations yet','Browsing and previews do not modify your files.'));
  modal('File activity & Trash',content,[button('Close',()=>document.querySelector('#dialog').close())]);
}
function addRoot(ctx){
  const path=el('input',{placeholder:'C:\\Users\\you\\Documents','aria-label':'Local folder path'});
  const label=el('input',{placeholder:'Documents','aria-label':'Folder label',maxlength:80});
  const writable=el('input',{type:'checkbox',checked:false});
  const dialog=modal('Add a local folder',el('div',{class:'stack'},field('Existing absolute folder path',path),field('Display name',label),el('label',{class:'check-row'},writable,'Allow file changes in this folder'),el('p',{class:'hint'},'Access stays on this machine. No model receives the contents, and nothing is automatically admitted to memory.')),[button('Cancel',()=>document.querySelector('#dialog').close()),button('Review access',async()=>{
    const body={path:path.value,label:label.value||path.value.split(/[\\/]/).filter(Boolean).at(-1),writable:writable.checked};const review=await api('/files/roots/proposal',{method:'POST',body});dialog.close();
    if(await confirm('Review folder access',el('div',{class:'stack'},el('strong',{class:'break'},review.proposal.path),el('p',{},review.proposal.disclosure)),body.writable?'Allow read & write':'Allow read access')){
      const root=await api('/files/roots',{method:'POST',body:{...body,accepted_digest:review.accepted_digest}});ctx.state.files={root:root.id,path:'',query:'',offset:0};toast('Folder added');ctx.render();
    }
  },{kind:'primary'})]);
}
async function uploadFiles(ctx,files,location){
  if(!files.length)return;
  let stopped=false;
  const status=el('p',{},'Preparing upload…');const progress=el('progress',{value:0,max:100,'aria-label':'File upload progress'});
  const stop=button('Stop after current chunk',()=>{stopped=true;stop.disabled=true;});
  const dialog=modal('Upload to this computer',el('div',{class:'stack'},status,progress,el('p',{class:'hint'},'Files are transferred only to this local app, in bounded chunks. Keep this tab open until the transfer finishes.')),[stop]);
  for(const file of files){
    if(stopped)break;
    let manifest;
    try{
      manifest=await api('/files/uploads',{method:'POST',body:{root:location.root,path:join(location.path,file.name),size:file.size}});
      let offset=0;
      while(offset<file.size&&!stopped){
        const chunk=new Uint8Array(await file.slice(offset,offset+1048576).arrayBuffer());
        let binary='';for(let i=0;i<chunk.length;i+=8192)binary+=String.fromCharCode(...chunk.subarray(i,i+8192));
        await api(`/files/uploads/${manifest.id}`,{method:'PUT',body:{offset,data:btoa(binary)}});offset+=chunk.length;
        progress.value=file.size?offset/file.size*100:100;status.textContent=`${file.name} · ${bytes(offset)} / ${bytes(file.size)}`;
      }
      if(stopped)await api(`/files/uploads/${manifest.id}`,{method:'PUT',body:{offset:0,abort:true}});
      else await api(`/files/uploads/${manifest.id}`,{method:'PUT',body:{offset:file.size,finish:true}});
    }catch(error){
      if(manifest)await api(`/files/uploads/${manifest.id}`,{method:'PUT',body:{offset:0,abort:true}}).catch(()=>{});
      toast(`${file.name}: ${error.message}`,true);stopped=true;
    }
  }
  dialog.close();toast(stopped?'Upload stopped; already completed files remain available':'Upload complete');ctx.render();
}
