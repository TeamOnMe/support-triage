#!/usr/bin/env python3
"""Веб-панель триажа «ЭлектроПолка» — stdlib-only.

Адрес и порт панели, а также все пути — в config.json (по умолчанию 127.0.0.1:8777).

GET  /            — дашборд (все разобранные письма, фильтры, поиск, детали)
POST /api/run     — запустить triage.py (обработать новые письма)
POST /api/upload  — добавить письмо (text) в inbox и сразу разобрать
GET  /api/items   — JSON всех результатов
"""
import hashlib, json, os, subprocess, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import triage  # noqa: E402  — переиспользуем read_email/strip_quotes и загрузку настроек

_cfg = triage.load_config()
_paths = triage.resolve_paths(_cfg)
OUT = _paths["output"]
INBOX = _paths["inbox"]
HOST = _cfg["web_host"] or "127.0.0.1"
PORT = _cfg["web_port"] or 8777


def load_items():
    items = {}
    for fname in sorted(os.listdir(OUT)):
        if not fname.startswith("triage_") or not fname.endswith(".jsonl"):
            continue
        for line in open(os.path.join(OUT, fname), encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                it = json.loads(line)
            except json.JSONDecodeError:
                continue
            src = it.get("file")
            if src and os.path.exists(os.path.join(INBOX, src)):
                em = triage.read_email(os.path.join(INBOX, src))
                if em is not None:
                    it["_body"] = triage.strip_quotes(em["text"])
            items.setdefault(it.get("content_hash", it.get("file", line)), it)
    return sorted(items.values(),
                  key=lambda r: ({"critical": 0, "high": 1, "normal": 2, "low": 3}.get(r["urgency"], 9),
                                 r.get("file", "")))


def run_triage():
    # triage.py сам читает настройки (config.json) и ключ — здесь ничего подставлять не нужно
    r = subprocess.run([sys.executable, os.path.join(BASE, "triage.py")],
                       capture_output=True, text=True, timeout=900)
    return (r.stdout or "") + (r.stderr or "")


PAGE = """<!doctype html><html lang=ru><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>ЭлектроПолка — письма поддержки</title>
<style>
:root{--bg:#f5f7fb;--card:#ffffff;--line:#dde4ef;--tx:#1c2333;--dim:#5d6b85;--acc:#2563eb}
*{box-sizing:border-box}body{margin:0;font:17px/1.55 system-ui,sans-serif;background:var(--bg);color:var(--tx)}
header{background:#1c2333;color:#fff;padding:16px 22px;display:flex;flex-wrap:wrap;gap:12px;align-items:center}
h1{font-size:21px;margin:0}h1 span{color:#9fb0cd;font-weight:400;font-size:15px}
main{max-width:1050px;margin:0 auto;padding:18px 14px 70px}
button{background:var(--acc);color:#fff;border:0;border-radius:10px;padding:12px 20px;font-weight:700;cursor:pointer;font-size:16px}
button:disabled{opacity:.55}
button.ghost{background:#fff;color:var(--acc);border:2px solid var(--acc)}
.hero{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin:14px 0;font-size:18px}
.hero .warn{color:#b42318;font-weight:700}
.chips{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.chip{border-radius:10px;padding:6px 14px;font-size:15px;background:#eef2f9;border:1px solid var(--line)}
.chip b{font-size:19px;margin-right:6px}
.chip.c0{background:#fee2e2;border-color:#fca5a5}.chip.c1{background:#ffedd5;border-color:#fdba74}
.chip.c2{background:#fef9c3;border-color:#fde047}.chip.c3{background:#e5e7eb;border-color:#cbd5e1}
details.help{background:#eef6ff;border:1px solid #bfdbfe;border-radius:12px;padding:12px 18px;margin:10px 0;font-size:15px}
details.help summary{cursor:pointer;font-weight:700;color:var(--acc)}
details.help ol{margin:8px 0 4px}
.frow{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}
.frow .lbl{color:var(--dim);font-size:15px;min-width:86px}
.frow button{background:#fff;color:var(--tx);border:1px solid var(--line);padding:8px 14px;font-weight:400;font-size:15px}
.frow button.on{border-color:var(--acc);color:var(--acc);font-weight:700}
#search{width:100%;max-width:420px;border:1px solid var(--line);border-radius:10px;padding:11px 14px;font-size:16px}
.card{background:var(--card);border:1px solid var(--line);border-left:8px solid #cbd5e1;border-radius:12px;padding:14px 18px;margin:12px 0;cursor:pointer}
.card:hover{border-color:var(--acc)}
.card.u0{border-left-color:#dc2626}.card.u1{border-left-color:#ea580c}.card.u2{border-left-color:#ca8a04}
.card .top{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;font-size:17px}
.card .top b{font-size:17px}
.chip.cat{background:#eef2f9;border:1px solid var(--line);border-radius:8px;padding:1px 10px;font-size:14px;color:var(--tx)}
.badge{border-radius:8px;padding:2px 10px;font-size:14px;font-weight:700}
.badge.b0{background:#fee2e2;color:#b91c1c}
.badge.b1{background:#fef3c7;color:#92400e}
.action{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:9px 14px;margin-top:10px;font-size:16px}
.action b{color:#15803d}
.letter{white-space:pre-wrap;color:var(--tx);font-size:15px;background:#f8fafc;border-top:1px dashed var(--line);margin-top:12px;padding-top:12px;display:none}
.card.open .letter{display:block}
#msg{background:#ecfdf5;border:1px solid #a7f3d0;border-radius:12px;padding:12px 16px;margin:12px 0;font-size:16px;display:none}
#msg pre{white-space:pre-wrap;font:13px monospace;color:var(--dim);margin:8px 0 0}
#stext{white-space:pre-wrap;font-size:15px;line-height:1.55;background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:16px;max-height:60vh;max-height:60dvh;overflow:auto}
.srange{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 12px}
.srange span{font-size:14px;color:var(--dim)}
.srange input[type=date]{flex:1 1 120px;border:1px solid var(--line);border-radius:10px;padding:8px 10px;font-size:16px;background:#fff;color:var(--tx)}
.srange button{background:#fff;color:var(--acc);border:1px solid var(--acc);border-radius:10px;padding:8px 12px;font-size:13px;font-weight:700}
@media (max-width:640px){
 header{padding:12px 14px;gap:8px}
 header button{flex:1 1 100%;padding:11px 12px;font-size:15px}
 main{padding:14px 10px 50px}
 .hero{font-size:16px;padding:12px 14px}
 .frow .lbl{min-width:64px}
 dialog{padding:14px;max-width:100%}
 dialog h3{font-size:18px}
 #stext{max-height:45vh;max-height:45dvh;font-size:14px;padding:12px}
 .row{flex-direction:column;gap:8px}
 .row button{width:100%}
 .srange button{padding:9px 12px;font-size:13px}
}
dialog{background:var(--card);border:0;border-radius:14px;padding:22px;max-width:620px;width:94%}
dialog::backdrop{background:#000a}
dialog h3{margin:0 0 10px;font-size:20px}
textarea{width:100%;border:1px solid var(--line);border-radius:10px;padding:12px;font:16px/1.5 inherit;min-height:180px}
label{font-size:15px;color:var(--dim)}
.row{display:flex;gap:10px;justify-content:flex-end;margin-top:14px}
.empty{text-align:center;color:var(--dim);padding:36px 10px;font-size:17px}
</style></head><body>
<header><h1>ЭлектроПолка <span>· письма поддержки</span></h1>
<button onclick=doRun(this)>🔄 Проверить письма</button>
<button class=ghost onclick=showSummary()>📄 Сводка по письмам</button>
<button class=ghost onclick="document.getElementById('dlg').showModal()">✍️ Добавить письмо</button></header>
<main>
<details class=help open><summary>Как пользоваться — 3 шага</summary>
<ol><li>Нажмите <b>«Проверить письма»</b> — программа прочитает новые письма и разложит их по важности.</li>
<li>Сверху списка — самые важные. У каждого письма написано <b>«Что делать»</b>.</li>
<li>Нажмите на письмо, чтобы прочитать его целиком. Красное — реагируем сразу.</li></ol></details>
<div class=hero id=hero></div>
<div class=frow><span class=lbl>Поиск:</span><input id=search placeholder="например: возврат или TD-48215" oninput=render()></div>
<div class=frow><span class=lbl>Важность:</span><span id=furg></span></div>
<div class=frow><span class=lbl>Отдел:</span><span id=fcat></span></div>
<div id=msg></div><div id=list></div>
</main>
<dialog id=dlg><h3>Новое письмо от клиента</h3>
<label>Вставьте текст письма — программа сразу его разберёт</label>
<textarea id=txt placeholder="Например: Здравствуйте! Заказ TD-48215 до сих пор не пришёл, когда ждать?"></textarea>
<div class=row><button class=ghost onclick="dlg.close()">Отмена</button>
<button onclick=doUpload(this)>Разобрать письмо</button></div></dialog>
<dialog id=sdlg><h3>Сводка по письмам</h3>
<div class=srange><span>С</span><input type=date id=ds onchange=applyRange()><span>по</span><input type=date id=de onchange=applyRange()><button onclick=resetRange()>Всё время</button></div>
<div id=stext></div>
<div class=row><button class=ghost onclick="sdlg.close()">Закрыть</button>
<button class=ghost onclick=doCopy(this)>Скопировать текст</button>
<button onclick=doDownload()>Скачать файлом</button></div></dialog>
<script>
let ALL=[],F='all',D='all',Q='';
const URG={critical:{e:'🔴',t:'Горит',l:'действуем сейчас'},high:{e:'🟠',t:'Срочно',l:'сегодня'},
 normal:{e:'🟡',t:'Обычные',l:''},low:{e:'⚪',t:'Спам и ожидание',l:''}};
const CAT={billing:'💰 Оплата и возвраты',tech:'🔧 Техподдержка',delivery:'🚚 Доставка',other:'📩 Другое',spam:'🗑 Спам'};
async function load(){const r=await fetch('api/items');ALL=await r.json();render();}
function render(){
 const h=document.getElementById('hero'),c={};ALL.forEach(x=>c[x.urgency]=(c[x.urgency]||0)+1);
 const hot=(c.critical||0)+(c.high||0);
 h.innerHTML=ALL.length
  ?`Писем разобрано: <b>${ALL.length}</b>. ${hot?`Требуют внимания сегодня: <span class=warn>${hot}</span> (горит: ${c.critical||0}, срочно: ${c.high||0}).`:'Ничего срочного нет — можно работать спокойно.'}`
  :'Пока ни одного разобранного письма. Нажмите «Проверить письма» — и они появятся.';
 const fu=document.getElementById('furg');
 fu.innerHTML=['all',...Object.keys(URG)].map(k=>{
  const n=k=='all'?ALL.length:(c[k]||0);
  const t=k=='all'?'Все':URG[k].e+' '+URG[k].t;
  return `<button class="${F==k?'on':''}" onclick="F='${k}';render()">${t} (${n})</button>`}).join('');
 const fc=document.getElementById('fcat'),cc={};ALL.forEach(x=>cc[x.category]=(cc[x.category]||0)+1);
 fc.innerHTML=['all',...Object.keys(CAT)].map(k=>{
  const n=k=='all'?ALL.length:(cc[k]||0);
  const t=k=='all'?'Все отделы':CAT[k];
  return `<button class="${D==k?'on':''}" onclick="D='${k}';render()">${t} (${n})</button>`}).join('');
 const q=Q.trim().toLowerCase();
 const list=document.getElementById('list');
 const shown=ALL.filter(x=>(F=='all'||x.urgency==F)&&(D=='all'||x.category==D)
  &&(!q||((x.summary||'')+' '+(x._body||'')+' '+(x.required_action||'')).toLowerCase().includes(q)));
 list.innerHTML=shown.map(x=>{
  const u=x.urgency=='critical'?0:x.urgency=='high'?1:x.urgency=='normal'?2:3;
  const w=[];
  if(x.injection_attempt)w.push('<span class="badge b0">🚨 В письме спрятана команда-обманка — читать внимательно</span>');
  if(x.order_not_found)w.push('<span class="badge b1">⚠️ Такого заказа нет в базе</span>');
  if(x.order_ambiguous)w.push('<span class="badge b1">⚠️ Номер заказа неполный</span>');
  if(x.degraded)w.push('<span class="badge b1">⚠️ Разобрано без ИИ — проверить глазами</span>');
  if(x.followup)w.push('<span class="badge b1">🔁 Клиент уже писал</span>');
  const ord=x.order_ids_matched&&x.order_ids_matched.length
   ?`Заказ ${x.order_ids_matched.join(', ')}${x.order_status?' · статус: '+x.order_status:''}`:'';
  return `<div class="card u${u}" onclick=this.classList.toggle('open')>
   <div class=top><span style=font-size:20px>${URG[x.urgency]?URG[x.urgency].e:'❓'}</span>
   <b>${esc(x.summary)}</b><span class="chip cat">${esc(CAT[x.category]||x.category)}</span></div>
   ${w.length?`<div style=margin-top:8px>${w.join(' ')}</div>`:''}
   ${ord?`<div style=color:var(--dim);margin-top:6px>${esc(ord)}</div>`:''}
   ${x.required_action?`<div class=action><b>Что делать:</b> ${esc(x.required_action)}</div>`:''}
   <div class=letter>${esc(x._body||'(текст письма недоступен)')}</div></div>`}).join('')
  ||`<div class=empty>${ALL.length?'По этому фильтру писем нет.<br>Выберите «Все» выше.':'Здесь появятся разобранные письма.'}</div>`;
}
function esc(s){return String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]))}
function show(t,detail){const l=document.getElementById('msg');l.style.display='block';
 l.innerHTML=esc(t)+(detail?`<details><summary>Подробности</summary><pre>${esc(detail)}</pre></details>`:'')}
async function doRun(b){b.disabled=true;b.textContent='Читаю письма…';
 show('⏳ Разбираю письма. Обычно это занимает меньше минуты — не закрывайте страницу.');
 const r=await fetch('api/run',{method:'POST'});const j=await r.json();const out=j.output||j.error||'';
 const m=out.match(/OK:\\s*разобрано\\s*(\\d+),\\s*пропущено\\s*(\\d+)/);
 if(m){const n=+m[1];show(n?`✅ Готово! Разобрано новых писем: ${n}. Список ниже обновлён.`:'✅ Готово. Новых писем нет — всё уже разобрано.',out);}
 else show('✅ Готово. Список ниже обновлён.',out);
 b.disabled=false;b.textContent='🔄 Проверить письма';load();}
async function doUpload(b){const t=document.getElementById('txt').value.trim();
 if(t.length<15)return alert('Слишком короткий текст — вставьте письмо целиком');
 b.disabled=true;b.textContent='Разбираю…';
 const r=await fetch('api/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})});
 const j=await r.json();b.disabled=false;b.textContent='Разобрать письмо';
 if(j.error)return alert(j.error);
 document.getElementById('dlg').close();document.getElementById('txt').value='';
 const m=(j.output||'').match(/OK:\\s*разобрано\\s*(\\d+)/);
 show(m?'✅ Письмо добавлено и разобрано. Оно уже в списке ниже.':'✅ Письмо добавлено.',j.output||'');
 F='all';D='all';load();}
document.getElementById('search').addEventListener('input',e=>{Q=e.target.value;render()});
let DS='',DE='';
function fmtDay(iso){const p=iso.split('-');return p[2]+'.'+p[1]+'.'+p[0]}
function plabel(){
 if(!DS&&!DE)return 'за всё время';
 if(DS&&DE)return `с ${fmtDay(DS)} по ${fmtDay(DE)}`;
 if(DS)return `с ${fmtDay(DS)}`;
 return `по ${fmtDay(DE)}`;
}
function inPeriod(x){const d=x.triage_date||'';return (!DS||d>=DS)&&(!DE||d<=DE)}
function applyRange(){
 DS=document.getElementById('ds').value||'';
 DE=document.getElementById('de').value||'';
 if(DS&&DE&&DS>DE){const t=DS;DS=DE;DE=t;
  document.getElementById('ds').value=DS;document.getElementById('de').value=DE;}
 document.getElementById('stext').textContent=buildSummary();
}
function resetRange(){DS='';DE='';
 document.getElementById('ds').value='';document.getElementById('de').value='';
 document.getElementById('stext').textContent=buildSummary();}
function buildSummary(){
 const items=ALL.filter(inPeriod);
 const d=new Date().toLocaleDateString('ru-RU');
 const head=`СВОДКА ПО ПИСЬМАМ ПОДДЕРЖКИ — ${d} (${plabel()})`;
 if(!items.length)return `${head}\n\nЗа выбранный период разобранных писем нет.\nИзмените даты сверху или нажмите «Проверить письма».`;
 const c={};items.forEach(x=>c[x.urgency]=(c[x.urgency]||0)+1);
 let t=`${head}\nВсего разобрано: ${items.length}`;
 ['critical','high','normal','low'].forEach(k=>{if(c[k])t+=`, ${URG[k].e} ${URG[k].t}: ${c[k]}`});
 t+=`\n`;
 [['critical','🔴 ГОРЯТ — ДЕЙСТВУЕМ СЕЙЧАС'],['high','🟠 СРОЧНО — СЕГОДНЯ'],
  ['normal','🟡 ОБЫЧНЫЙ ПОТОК'],['low','⚪ СПАМ И ОЖИДАНИЕ']].forEach(([k,ttl])=>{
  const its=items.filter(x=>x.urgency==k);if(!its.length)return;
  t+=`\n${ttl} (${its.length})\n`;
  its.forEach((x,i)=>{
   t+=`${i+1}. ${x.summary}\n   ${CAT[x.category]||x.category}`;
   if(x.order_ids_matched&&x.order_ids_matched.length)t+=` · заказ ${x.order_ids_matched.join(', ')}`;
   if(x.order_status)t+=` · статус: ${x.order_status}`;
   t+=`\n`;
   const w=[];
   if(x.injection_attempt)w.push('🚨 спрятанная команда-обманка');
   if(x.order_not_found)w.push('⚠️ заказа нет в базе');
   if(x.order_ambiguous)w.push('⚠️ номер неполный');
   if(x.degraded)w.push('⚠️ разобрано без ИИ');
   if(x.followup)w.push('🔁 повторное письмо');
   if(w.length)t+=`   ${w.join(', ')}\n`;
   if(x.required_action)t+=`   Что делать: ${x.required_action}\n`;
  });
 });
 return t;
}
function showSummary(){
 if(!ALL.length)return alert('Сначала нажмите «Проверить письма» — список пуст');
 document.getElementById('stext').textContent=buildSummary();
 document.getElementById('sdlg').showModal();
}
function doCopy(b){
 const t=document.getElementById('stext').textContent;
 const ok=()=>{b.textContent='Скопировано ✓';setTimeout(()=>b.textContent='Скопировать текст',1500)};
 if(navigator.clipboard&&window.isSecureContext)navigator.clipboard.writeText(t).then(ok);
 else{const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove();ok();}
}
function doDownload(){
 const b=new Blob([document.getElementById('stext').textContent],{type:'text/plain;charset=utf-8'});
 const a=document.createElement('a');a.href=URL.createObjectURL(b);
 a.download=`сводка_писем_${new Date().toLocaleDateString('ru-RU').replaceAll('.','-')}${DS?'_с_'+DS:''}${DE?'_по_'+DE:''}.txt`;
 a.click();URL.revokeObjectURL(a.href);
}
load();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, PAGE)
        elif path == "/api/items":
            items = load_items()
            self._send(200, json.dumps(items, ensure_ascii=False), "application/json; charset=utf-8")
        else:
            self._send(404, "not found")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {}
        if self.path == "/api/run":
            self._send(200, json.dumps({"output": run_triage()}, ensure_ascii=False),
                       "application/json; charset=utf-8")
        elif self.path == "/api/upload":
            text = str(payload.get("text", "")).strip()
            if len(text) < 15:
                self._send(400, json.dumps({"error": "Слишком короткий текст — вставьте письмо целиком"}),
                           "application/json; charset=utf-8")
                return
            fname = f"web_{hashlib.sha1(text.encode()).hexdigest()[:8]}.txt"
            open(os.path.join(INBOX, fname), "w", encoding="utf-8").write(text + "\n")
            out = run_triage()
            self._send(200, json.dumps({"output": f"Сохранено как {fname}\n" + out}, ensure_ascii=False),
                       "application/json; charset=utf-8")
        else:
            self._send(404, "not found")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
