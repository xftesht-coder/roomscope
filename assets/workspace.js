import { validateProfile, compareProfiles, demoProfile } from './profiles.js';
const key = 'roomscope.profiles.v1';
const state = { a: null, b: null };
const status = document.getElementById('status');
const format = n => `${n > 0 ? '+' : ''}${n.toFixed(2)}`;
function notify(message, error = false) { status.textContent = message; status.classList.toggle('error', error); }
function persist() {
  try { localStorage.setItem(key, JSON.stringify(state)); return true; }
  catch { notify('Профили открыты, но браузер не разрешил сохранение. Скачайте JSON перед закрытием.', true); return false; }
}
function svgNode(tag, attributes, text) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key,value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (text != null) node.textContent = text;
  return node;
}
function renderChart() {
  const chart = document.getElementById('chart'); chart.replaceChildren();
  const profiles = Object.values(state).filter(Boolean);
  chart.toggleAttribute('hidden', profiles.length === 0); document.getElementById('empty').hidden = profiles.length > 0;
  if (!profiles.length) return;
  const values = profiles.flatMap(p => p.response.smoothed_db);
  const low = Math.floor((Math.min(...values)-2)/5)*5;
  const high = Math.ceil((Math.max(...values)+2)/5)*5;
  const frequencies = profiles.flatMap(p => p.response.centers_hz);
  const fLow = Math.min(20, ...frequencies), fHigh = Math.max(20000, ...frequencies);
  const x = f => 62+868*Math.log(f/fLow)/Math.log(fHigh/fLow);
  const y = v => 290-(v-low)/(high-low)*265;
  for (let i=0;i<=4;i++) {
    const value=low+(high-low)*i/4;
    chart.append(svgNode('line',{x1:62,x2:930,y1:y(value),y2:y(value),stroke:'#293743'}));
    chart.append(svgNode('text',{x:50,y:y(value)+5,fill:'#a4b0bd','text-anchor':'end','font-size':13},`${value.toFixed(0)}`));
  }
  for (const f of [20,50,100,200,500,1000,2000,5000,10000,20000]) {
    chart.append(svgNode('line',{x1:x(f),x2:x(f),y1:25,y2:290,stroke:'#202c36'}));
    chart.append(svgNode('text',{x:x(f),y:320,fill:'#a4b0bd','text-anchor':'middle','font-size':13},f>=1000?`${f/1000}k`:f));
  }
  for (const [slot, profile] of Object.entries(state)) {
    if (!profile) continue;
    const points=profile.response.centers_hz.map((f,i)=>`${x(f)},${y(profile.response.smoothed_db[i])}`).join(' ');
    chart.append(svgNode('polyline',{points,fill:'none',stroke:slot==='a'?'#70ddba':'#f1b66c','stroke-width':2.5,'vector-effect':'non-scaling-stroke',...(slot==='b'?{'stroke-dasharray':'7 4'}:{})}));
  }
}
function render() {
  for (const slot of ['a','b']) {
    const profile=state[slot], card=document.querySelector(`[data-slot="${slot}"]`);
    const input=document.getElementById(`label-${slot}`); input.disabled=!profile; input.value=profile?.label || '';
    document.getElementById(`export-${slot}`).disabled=!profile;
    card.querySelector('.source').textContent=profile ? {synthetic:'Синтетика',real:'Измерение',unknown:'Источник не указан'}[profile.source] : 'Нет данных';
    card.querySelector('.meta').textContent=profile ? `${profile.response.centers_hz.length} полос · ${profile.response.reference==='sweep-relative'?'относительно sweep':'старый формат · нормировано к пику'}` : 'Профиль не загружен';
  }
  renderChart();
  const rows=document.getElementById('band-rows'); rows.replaceChildren();
  document.getElementById('rms').textContent='—'; document.getElementById('mean').textContent='—';
  if (state.a && state.b) {
    try {
      const result=compareProfiles(state.a,state.b);
      document.getElementById('rms').textContent=`${result.rms.toFixed(2)} дБ`;
      document.getElementById('mean').textContent=`${format(result.mean)} дБ`;
      for (const band of result.bands) {
        const row=document.createElement('tr');
        for (const value of [band.frequency,format(band.a),format(band.b),format(band.delta)]) { const cell=document.createElement('td');cell.textContent=value;row.append(cell); }
        rows.append(row);
      }
    } catch(error) { notify(error.message,true); }
  }
  document.getElementById('peq').textContent=Object.entries(state).filter(([,p])=>p).map(([slot,p])=>`${slot.toUpperCase()}: ${p.peq_filters.length ? p.peq_filters.map(f=>`${f.freq_hz} Гц / ${format(f.gain_db)} дБ / Q ${f.q_factor}`).join('; ') : 'PEQ-фильтров нет'}`).join('\n') || 'PEQ-предложения появятся после загрузки профиля.';
}
for (const slot of ['a','b']) {
  let generation=0;
  document.getElementById(`file-${slot}`).addEventListener('change',async event=>{
    const file=event.target.files[0];if(!file)return;
    const current=++generation;
    try {
      if(file.size>1024*1024)throw new Error('Файл слишком большой. Максимум 1 МБ.');
      const profile=validateProfile(JSON.parse(await file.text()));
      if(current!==generation)return;
      state[slot]=profile; notify(`Профиль ${slot.toUpperCase()} загружен.`); render(); persist();
    } catch(error) { notify(error instanceof SyntaxError ? 'Не удалось прочитать JSON. Проверьте файл; предыдущий профиль сохранён.' : error.message,true); }
    finally { event.target.value=''; }
  });
  document.getElementById(`label-${slot}`).addEventListener('change',event=>{
    if(!state[slot])return;
    state[slot].label=event.target.value.trim() || 'Без названия';render();persist();
  });
  document.getElementById(`export-${slot}`).addEventListener('click',()=>{
    if(!state[slot])return;
    const blob=new Blob([JSON.stringify(state[slot],null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob), anchor=document.createElement('a');anchor.href=url;anchor.download=`roomscope-${slot}.json`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
}
document.getElementById('demo').addEventListener('click',()=>{
  state.a=demoProfile('A');state.b=demoProfile('B');notify('Демо загружено. Оба профиля синтетические; это не замер вашей комнаты.');render();persist();
});
document.getElementById('clear').addEventListener('click',()=>{
  state.a=null;state.b=null;notify('Профили очищены. Загрузите JSON или демо, чтобы начать.');render();persist();
});
try {
  const saved=JSON.parse(localStorage.getItem(key) || 'null');
  if(saved) {
    // Validate both slots before accepting either, so corrupt storage cannot half-restore.
    const a=saved.a?validateProfile(saved.a):null,b=saved.b?validateProfile(saved.b):null;
    Object.assign(state,{a,b});if(a||b)notify('Восстановлены профили из этого браузера.');
  }
} catch { notify('Сохранённые данные недоступны или повреждены. Загрузите профили из JSON.',true); }
render();
