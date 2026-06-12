#!/usr/bin/env python3
"""
PhotoBeam v2 — Transferència de fitxers mòbil → PC via WiFi
Executa al PC: python3 servidor_fotos.py
"""

import http.server, socketserver, os, json, socket, threading, sys
import webbrowser, base64, mimetypes, io, subprocess, platform
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    import qrcode
    HAS_QR = True
except ImportError:
    print("  Instal·lant qrcode...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "qrcode[pil]", "--quiet"],
                       check=True)
        import qrcode
        HAS_QR = True
        print("  qrcode instal·lat correctament")
    except Exception:
        HAS_QR = False
        print("  No s'ha pogut instal·lar qrcode, el QR no estarà disponible")

PORT = 8765

# ── Tipus de fitxer ─────────────────────────────────────────────
IMAGE_EXTS = {'.jpg','.jpeg','.png','.gif','.webp','.heic','.heif','.bmp','.tiff','.tif'}
VIDEO_EXTS = {'.mp4','.mov','.avi','.mkv','.m4v','.3gp','.wmv'}

def file_category(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXTS: return 'foto'
    if ext in VIDEO_EXTS: return 'video'
    return 'doc'

FILE_ICONS = {
    'foto': '🖼️', 'video': '🎬',
    'doc': '📄', '.pdf': '📕', '.docx': '📘', '.doc': '📘',
    '.xlsx': '📗', '.xls': '📗', '.pptx': '📙', '.ppt': '📙',
    '.zip': '🗜️', '.rar': '🗜️', '.7z': '🗜️',
    '.mp3': '🎵', '.aac': '🎵', '.wav': '🎵',
}

def file_icon(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in FILE_ICONS: return FILE_ICONS[ext]
    cat = file_category(name)
    return FILE_ICONS.get(cat, '📄')

# ── Utilitats ───────────────────────────────────────────────────
def dest_folder() -> Path:
    desktop = Path.home() / "Desktop"
    if not desktop.exists(): desktop = Path.home()
    folder = desktop / f"PhotoBeam {datetime.now().strftime('%Y-%m-%d')}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def log_file(folder: Path) -> Path:
    return folder / "_historial.txt"

def write_log(folder: Path, name: str, size: int, category: str):
    entry = f"[{datetime.now().strftime('%H:%M:%S')}]  {category.upper():<5}  {name}  ({size//1024} KB)\n"
    try:
        with open(log_file(folder), "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

def notify_mac(name: str, category: str):
    if platform.system() != "Darwin": return
    icon = file_icon(name)
    msg = f"{icon} {name}"
    script = f'display notification "{msg}" with title "PhotoBeam" subtitle "Fitxer rebut"'
    try:
        subprocess.Popen(["osascript", "-e", script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def make_qr_png(url: str) -> bytes:
    if not HAS_QR: return b""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=2)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO(); img.save(buf); return buf.getvalue()

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception: return "127.0.0.1"

def open_folder(path: Path):
    try:
        sys = platform.system()
        if sys == "Darwin": subprocess.Popen(["open", str(path)])
        elif sys == "Windows": subprocess.Popen(["explorer", str(path)])
        else: subprocess.Popen(["xdg-open", str(path)])
    except Exception: pass

def unique_path(p: Path) -> Path:
    if not p.exists(): return p
    stem, suf = p.stem, p.suffix; i = 1
    while True:
        c = p.parent / f"{stem}_{i}{suf}"
        if not c.exists(): return c
        i += 1

def parse_multipart(data: bytes, boundary: bytes):
    parts = data.split(b"--" + boundary); results = []
    for part in parts[1:]:
        if part.strip() in (b"--", b""): continue
        sep = b"\r\n\r\n" if b"\r\n\r\n" in part else b"\n\n"
        if sep not in part: continue
        hdr_raw, body = part.split(sep, 1)
        body = body.rstrip(b"\r\n--"); fname = None
        for line in hdr_raw.decode("utf-8", errors="replace").splitlines():
            if "filename=" in line:
                fname = os.path.basename(line.split("filename=")[-1].strip().strip('"')); break
        if fname: results.append((fname, body))
    return results

# ═══════════════════════════════════════════════════════════════════
#  HTML — VISTA MÒBIL
# ═══════════════════════════════════════════════════════════════════
MOBILE_HTML = r"""<!DOCTYPE html>
<html lang="ca">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>PhotoBeam</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0a0a0f;--s1:#12121a;--s2:#1a1a26;--acc:#7c6fff;--acc2:#ff6fb0;--acc3:#6fffd4;--txt:#e8e6f0;--muted:#6b6880;--r:16px}
body{background:var(--bg);color:var(--txt);font-family:'Outfit',sans-serif;min-height:100dvh;display:flex;flex-direction:column;align-items:center;padding:1.5rem 1rem 4rem;gap:1.2rem;overflow-x:hidden}
body::before{content:'';position:fixed;top:-30%;left:-20%;width:70vw;height:70vw;background:radial-gradient(ellipse,rgba(124,111,255,.15) 0%,transparent 70%);pointer-events:none;z-index:0}
body::after{content:'';position:fixed;bottom:-20%;right:-20%;width:60vw;height:60vw;background:radial-gradient(ellipse,rgba(255,111,176,.12) 0%,transparent 70%);pointer-events:none;z-index:0}
header{text-align:center;z-index:1;padding-top:.5rem}
.logo{font-size:1rem;font-weight:600;letter-spacing:.12em;color:transparent;background:linear-gradient(90deg,var(--acc),var(--acc2));-webkit-background-clip:text;background-clip:text;margin-bottom:.3rem}
header h1{font-size:2.2rem;font-weight:700;line-height:1;background:linear-gradient(135deg,#fff 30%,var(--muted));-webkit-background-clip:text;background-clip:text;color:transparent}
header p{color:var(--muted);font-size:.82rem;margin-top:.4rem}

/* Botons d'acció principals */
.action-row{display:grid;grid-template-columns:1fr 1fr;gap:.75rem;width:100%;max-width:420px;z-index:1}
.action-btn{padding:1.2rem .5rem;border:none;border-radius:var(--r);font-family:'Outfit',sans-serif;font-weight:700;font-size:.95rem;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:.4rem;position:relative;overflow:hidden;transition:transform .1s,opacity .2s}
.action-btn input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer}
.action-btn:active{transform:scale(.97)}
.action-btn .icon{font-size:2rem;line-height:1}
.btn-photos{background:linear-gradient(135deg,var(--acc),#5b4fd4);color:#fff}
.btn-docs{background:linear-gradient(135deg,#2a6fff,#1a4fbb);color:#fff}

.card{background:var(--s1);border:1px solid rgba(255,255,255,.06);border-radius:var(--r);width:100%;max-width:420px;z-index:1}
.card-header{padding:.6rem .9rem;font-size:.72rem;letter-spacing:.08em;color:var(--muted);font-weight:600;border-bottom:1px solid rgba(255,255,255,.05)}

/* llista mixta */
.file-list{display:flex;flex-direction:column;gap:0}
.file-list:empty{display:none}
.fi-row{display:flex;align-items:center;gap:.7rem;padding:.6rem .9rem;border-bottom:1px solid rgba(255,255,255,.04)}
.fi-row:last-child{border-bottom:none}
.fi-thumb{width:44px;height:44px;border-radius:8px;overflow:hidden;flex-shrink:0;background:var(--s2);display:flex;align-items:center;justify-content:center;font-size:1.5rem}
.fi-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.fi-meta{flex:1;min-width:0}
.fi-name{font-size:.82rem;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fi-size{font-size:.7rem;color:var(--muted)}
.fi-rm{background:none;border:none;color:var(--muted);font-size:1.1rem;cursor:pointer;padding:.2rem .4rem;flex-shrink:0}
.fi-ov{font-size:1.1rem}

.btn-send{width:100%;max-width:420px;padding:.95rem;border:none;border-radius:var(--r);background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;font-family:'Outfit',sans-serif;font-size:1.05rem;font-weight:700;cursor:pointer;z-index:1;transition:opacity .2s,transform .1s}
.btn-send:active{transform:scale(.97)}.btn-send:disabled{opacity:.35;cursor:default}
.summary{width:100%;max-width:420px;background:var(--s1);border:1px solid rgba(255,255,255,.06);border-radius:var(--r);padding:.9rem 1.1rem;z-index:1;display:none;font-size:.88rem;line-height:1.7}
.ok{color:var(--acc3)}.er{color:#ff6b6b}
#bar{width:100%;max-width:420px;z-index:1;min-height:1.1rem;font-size:.75rem;color:var(--muted);text-align:center}
</style>
</head>
<body>
<header>
  <div class="logo">PHOTOBEAM</div>
  <h1>Envia fitxers</h1>
  <p>Es desen automàticament a l'Escriptori del PC</p>
</header>

<!-- Botons d'acció ràpida -->
<div class="action-row">
  <button class="action-btn btn-photos">
    <input type="file" id="fiPhotos" accept="image/*,video/*" multiple>
    <span class="icon">📸</span>
    <span>Fotos i vídeos</span>
  </button>
  <button class="action-btn btn-docs">
    <input type="file" id="fiDocs" accept="*/*" multiple>
    <span class="icon">📁</span>
    <span>Altres fitxers</span>
  </button>
</div>

<!-- Llista de fitxers seleccionats -->
<div class="card" id="listCard" style="display:none">
  <div class="card-header" id="listHeader">FITXERS SELECCIONATS</div>
  <div class="file-list" id="fileList"></div>
</div>

<button class="btn-send" id="btn" disabled>Enviar al PC →</button>
<div class="summary" id="sum"></div>
<div id="bar"></div>

<script>
const fiPhotos=document.getElementById('fiPhotos'),fiDocs=document.getElementById('fiDocs');
const fileList=document.getElementById('fileList'),listCard=document.getElementById('listCard');
const listHeader=document.getElementById('listHeader'),btn=document.getElementById('btn');
const sumEl=document.getElementById('sum'),bar=document.getElementById('bar');
let files=[];

const IMG_EXTS=new Set(['.jpg','.jpeg','.png','.gif','.webp','.heic','.heif','.bmp','.tiff']);
const FILE_ICONS={'.pdf':'📕','.docx':'📘','.doc':'📘','.xlsx':'📗','.xls':'📗',
  '.pptx':'📙','.ppt':'📙','.zip':'🗜️','.rar':'🗜️','.7z':'🗜️',
  '.mp3':'🎵','.aac':'🎵','.wav':'🎵','.mp4':'🎬','.mov':'🎬','.avi':'🎬'};
function fIcon(name){
  const ext=name.slice(name.lastIndexOf('.')).toLowerCase();
  return FILE_ICONS[ext]||'📄';
}
function isImage(name){
  const ext=name.slice(name.lastIndexOf('.')).toLowerCase();
  return IMG_EXTS.has(ext);
}

fiPhotos.addEventListener('change',()=>{addFiles(fiPhotos.files);fiPhotos.value=''});
fiDocs.addEventListener('change',()=>{addFiles(fiDocs.files);fiDocs.value=''});

function addFiles(list){
  [...list].forEach(f=>{
    if(files.find(x=>x.name===f.name&&x.size===f.size))return;
    files.push(f); renderRow(f);
  });
  sync();
}

function renderRow(f){
  const row=document.createElement('div');row.className='fi-row';row.dataset.n=f.name;
  const thumb=document.createElement('div');thumb.className='fi-thumb';
  if(isImage(f.name)){
    const img=document.createElement('img');img.src=URL.createObjectURL(f);
    thumb.appendChild(img);
  } else {
    thumb.textContent=fIcon(f.name);
  }
  const meta=document.createElement('div');meta.className='fi-meta';
  meta.innerHTML=`<div class="fi-name">${f.name}</div><div class="fi-size">${(f.size/1024).toFixed(0)} KB</div>`;
  const rm=document.createElement('button');rm.className='fi-rm';rm.textContent='✕';
  rm.onclick=()=>{files=files.filter(x=>x!==f);row.remove();sync()};
  row.append(thumb,meta,rm);fileList.appendChild(row);
}

function sync(){
  btn.disabled=!files.length;
  if(files.length){
    listCard.style.display='';
    listHeader.textContent=files.length+' FITXER'+(files.length>1?'S':'')+' SELECCIONAT'+(files.length>1?'S':'');
  } else {
    listCard.style.display='none';
  }
}

function setRowState(name, icon){
  const row=fileList.querySelector('[data-n="'+CSS.escape(name)+'"]');
  if(!row)return;
  let ov=row.querySelector('.fi-ov');
  if(!ov){ov=document.createElement('span');ov.className='fi-ov';row.querySelector('.fi-rm').replaceWith(ov)}
  ov.textContent=icon;
}

btn.addEventListener('click',async()=>{
  if(!files.length)return;
  btn.disabled=true;sumEl.style.display='none';
  let ok=0,err=0,dest='';
  for(const f of [...files]){
    setRowState(f.name,'⏳');bar.textContent='Enviant '+f.name+'…';
    const fd=new FormData();fd.append('file',f,f.name);
    try{
      const r=await fetch('/upload',{method:'POST',body:fd});
      const j=await r.json();
      if(j.ok){setRowState(f.name,'✅');ok++;dest=j.dest||'';}
      else throw new Error(j.error||'Error');
    }catch(e){setRowState(f.name,'❌');err++;}
  }
  bar.textContent='';
  const total=ok+err;
  sumEl.innerHTML='<span class="ok">✓ '+ok+' fitxer'+(ok!==1?'s':'')+' desat'+(ok!==1?'s':'')+'</span>'+
    (err?' <span class="er">· '+err+' error'+(err!==1?'s':'')+'</span>':'')+
    (dest?'<br><small style="color:var(--muted)">📂 '+dest+'</small>':'');
  sumEl.style.display='block';
  files=[];sync();fileList.innerHTML='';
});
</script>
</body>
</html>"""

# ═══════════════════════════════════════════════════════════════════
#  HTML — VISTA PC
# ═══════════════════════════════════════════════════════════════════
PC_HTML = r"""<!DOCTYPE html>
<html lang="ca">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PhotoBeam · PC</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#f5f3ef;--s1:#fff;--s2:#f0eee9;--acc:#2a2560;--txt:#1a1825;--muted:#888;--border:#e2dfd8;--r:12px}
body{background:var(--bg);color:var(--txt);font-family:'Outfit',sans-serif;min-height:100vh;
  display:grid;grid-template-columns:280px 1fr;grid-template-rows:1fr auto}

aside{grid-row:1/3;background:var(--acc);color:#fff;padding:2rem 1.5rem;
  display:flex;flex-direction:column;gap:1.3rem;min-height:100vh}
.logo-s{font-size:.7rem;letter-spacing:.18em;opacity:.45;font-weight:600}
aside h1{font-family:'DM Serif Display',serif;font-size:2rem;line-height:1.1}
aside p{font-size:.78rem;opacity:.5;line-height:1.5}
.info-card{background:rgba(255,255,255,.08);border-radius:var(--r);padding:.85rem 1rem;display:flex;flex-direction:column;gap:.35rem}
.info-card label{font-size:.62rem;letter-spacing:.1em;opacity:.45;font-weight:600}
.conn-url{font-size:.85rem;font-weight:600;word-break:break-all;background:rgba(255,255,255,.1);border-radius:8px;padding:.4rem .65rem;font-family:monospace;line-height:1.4}
.dest-path{font-size:.75rem;opacity:.65;word-break:break-all;line-height:1.4}
.qr-box{background:rgba(255,255,255,.08);border-radius:var(--r);padding:.85rem;text-align:center}
.qr-box label{font-size:.62rem;letter-spacing:.1em;opacity:.45;font-weight:600;display:block;margin-bottom:.5rem}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem}
.stat{background:rgba(255,255,255,.07);border-radius:10px;padding:.6rem .4rem;text-align:center}
.stat .n{font-size:1.4rem;font-weight:700}
.stat .l{font-size:.58rem;opacity:.4;letter-spacing:.05em}
.btn-folder{width:100%;padding:.65rem;border:none;border-radius:10px;background:rgba(255,255,255,.15);
  color:#fff;font-family:'Outfit',sans-serif;font-size:.85rem;font-weight:600;cursor:pointer;transition:background .15s}
.btn-folder:hover{background:rgba(255,255,255,.25)}
.btn-log{width:100%;padding:.55rem;border:none;border-radius:10px;background:rgba(255,255,255,.08);
  color:rgba(255,255,255,.6);font-family:'Outfit',sans-serif;font-size:.78rem;cursor:pointer;transition:background .15s}
.btn-log:hover{background:rgba(255,255,255,.15)}

main{grid-column:2;padding:1.75rem;overflow-y:auto}

/* filtres */
.filters{display:flex;gap:.5rem;margin-bottom:1.2rem;flex-wrap:wrap;align-items:center}
.filters h2{font-size:1.2rem;font-weight:600;flex:1}
.f-btn{padding:.3rem .8rem;border-radius:20px;border:1.5px solid var(--border);
  background:#fff;font-family:'Outfit',sans-serif;font-size:.78rem;font-weight:600;
  cursor:pointer;transition:all .15s;color:var(--muted)}
.f-btn.active{background:var(--acc);color:#fff;border-color:var(--acc)}

/* grid */
#photoGrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:.7rem}

/* card foto */
.ph{background:var(--s1);border:1.5px solid var(--border);border-radius:var(--r);overflow:hidden;position:relative}
.ph img{width:100%;aspect-ratio:1;object-fit:cover;display:block}
.ph-info{padding:.4rem .55rem}
.ph-name{font-size:.68rem;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ph-badge{position:absolute;top:6px;right:6px;background:rgba(42,37,96,.85);color:#fff;font-size:.6rem;padding:.12rem .38rem;border-radius:20px;font-weight:600}

/* card document */
.ph.doc-card{display:flex;flex-direction:column;align-items:center;justify-content:center;
  padding:1.2rem .75rem;gap:.5rem;aspect-ratio:1;text-align:center;cursor:default}
.doc-icon{font-size:2.6rem;line-height:1}
.doc-name{font-size:.68rem;font-weight:500;word-break:break-word;text-align:center;line-height:1.3}
.doc-size{font-size:.62rem;color:var(--muted)}
.doc-card .ph-badge{top:6px;right:6px}

.ph-new{animation:fadeIn .35s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

#empty{text-align:center;padding:5rem 2rem;color:var(--muted)}
#empty .big{font-size:3.5rem;margin-bottom:.5rem}
#empty h3{font-size:1.05rem;font-weight:600;color:var(--txt);margin-bottom:.3rem}

footer{grid-column:2;background:var(--s1);border-top:1.5px solid var(--border);
  padding:.55rem 1.75rem;font-size:.78rem;color:var(--muted);display:flex;align-items:center;gap:1rem}
#activity{flex:1}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#bbb;margin-right:.4rem;vertical-align:middle}
.dot.live{background:#4caf50;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
</style>
</head>
<body>
<aside>
  <div>
    <div class="logo-s">PHOTOBEAM v2</div>
    <h1>Receptor<br>de fitxers</h1>
    <p style="margin-top:.3rem">Els fitxers arriben i es desen automàticament.</p>
  </div>
  <div class="info-card">
    <label>URL PER AL MÒBIL</label>
    <div class="conn-url" id="mobileUrl">—</div>
  </div>
  <div class="qr-box">
    <label>ESCANEJA DES DEL MÒBIL</label>
    <img src="/qr.png" width="128" height="128" alt="QR"
      style="border-radius:6px;background:#fff;padding:5px;display:block;margin:0 auto">
  </div>
  <div class="info-card">
    <label>CARPETA DE DESTÍ</label>
    <div class="dest-path" id="destPath">—</div>
  </div>
  <button class="btn-folder" id="btnOpenFolder">📂 Obrir carpeta</button>
  <button class="btn-log" id="btnOpenLog">📋 Veure historial</button>
  <div class="stats">
    <div class="stat"><div class="n" id="cntN">0</div><div class="l">TOTAL</div></div>
    <div class="stat"><div class="n" id="cntF">0</div><div class="l">FOTOS</div></div>
    <div class="stat"><div class="n" id="cntMB">0</div><div class="l">MB</div></div>
  </div>
</aside>

<main>
  <div class="filters">
    <h2>Fitxers rebuts</h2>
    <button class="f-btn active" data-filter="tot">Tot</button>
    <button class="f-btn" data-filter="foto">📸 Fotos</button>
    <button class="f-btn" data-filter="video">🎬 Vídeo</button>
    <button class="f-btn" data-filter="doc">📄 Documents</button>
  </div>
  <div id="photoGrid"></div>
  <div id="empty">
    <div class="big">📭</div>
    <h3>Esperant fitxers…</h3>
    <p>Obre la URL al mòbil i envia els primers fitxers</p>
  </div>
</main>

<footer>
  <span class="dot live"></span>
  <span id="activity">Connectat · esperant fitxers</span>
</footer>

<script>
const IMG_EXTS=new Set(['.jpg','.jpeg','.png','.gif','.webp','.heic','.heif','.bmp','.tiff']);
const VID_EXTS=new Set(['.mp4','.mov','.avi','.mkv','.m4v','.3gp']);
const FILE_ICONS={'.pdf':'📕','.docx':'📘','.doc':'📘','.xlsx':'📗','.xls':'📗',
  '.pptx':'📙','.ppt':'📙','.zip':'🗜️','.rar':'🗜️','.7z':'🗜️',
  '.mp3':'🎵','.aac':'🎵','.wav':'🎵','.mp4':'🎬','.mov':'🎬','.avi':'🎬'};
function fExt(n){return n.slice(n.lastIndexOf('.')).toLowerCase()}
function fCat(n){const e=fExt(n);return IMG_EXTS.has(e)?'foto':VID_EXTS.has(e)?'video':'doc'}
function fIcon(n){return FILE_ICONS[fExt(n)]||'📄'}

let photos=[],totalBytes=0,lastId=0,photoCount=0,activeFilter='tot';

fetch('/meta').then(r=>r.json()).then(d=>{
  document.getElementById('mobileUrl').textContent=d.mobile_url;
  document.getElementById('destPath').textContent=d.dest;
  document.getElementById('btnOpenFolder').onclick=()=>fetch('/open-folder');
  document.getElementById('btnOpenLog').onclick=()=>fetch('/open-log');
});

// filtres
document.querySelectorAll('.f-btn').forEach(b=>{
  b.onclick=()=>{
    document.querySelectorAll('.f-btn').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    activeFilter=b.dataset.filter;
    document.querySelectorAll('.ph').forEach(c=>{
      const cat=c.dataset.cat||'doc';
      c.style.display=(activeFilter==='tot'||activeFilter===cat)?'':'none';
    });
  };
});

async function poll(){
  try{
    const r=await fetch('/photos?since='+lastId);
    const list=await r.json();
    list.forEach(p=>{
      photos.push(p);lastId=Math.max(lastId,p.id);totalBytes+=p.size;
      if(fCat(p.name)==='foto')photoCount++;
      addCard(p);
    });
    if(list.length){
      document.getElementById('empty').style.display='none';
      document.getElementById('cntN').textContent=photos.length;
      document.getElementById('cntF').textContent=photoCount;
      document.getElementById('cntMB').textContent=(totalBytes/1048576).toFixed(1);
      const last=list[list.length-1];
      document.getElementById('activity').textContent=
        'Últim: '+last.name+' · '+photos.length+' fitxer'+(photos.length>1?'s':'')+' en total';
    }
  }catch(e){}
  setTimeout(poll,1500);
}
poll();

function addCard(p){
  const g=document.getElementById('photoGrid');
  const cat=fCat(p.name);
  const d=document.createElement('div');
  d.className='ph ph-new';d.dataset.cat=cat;
  const kb=(p.size/1024).toFixed(0);

  if(cat==='foto'){
    d.innerHTML=`<img src="${p.dataUrl}" loading="lazy" alt="${p.name}">
      <div class="ph-badge">${kb} KB</div>
      <div class="ph-info"><div class="ph-name">${p.name}</div></div>`;
  } else {
    d.classList.add('doc-card');
    d.innerHTML=`<div class="doc-icon">${fIcon(p.name)}</div>
      <div class="doc-name">${p.name}</div>
      <div class="doc-size">${kb} KB</div>
      <div class="ph-badge">${cat==='video'?'VID':'DOC'}</div>`;
  }

  // aplica filtre actiu
  if(activeFilter!=='tot'&&activeFilter!==cat) d.style.display='none';
  g.appendChild(d);
}
</script>
</body>
</html>"""

# ═══════════════════════════════════════════════════════════════════
#  ESTAT GLOBAL
# ═══════════════════════════════════════════════════════════════════
photo_queue = []
photo_id_counter = 0
queue_lock = threading.Lock()
IP         = get_local_ip()
MOBILE_URL = f"http://{IP}:{PORT}/m"
PC_URL     = f"http://{IP}:{PORT}/"

# ── Watchdog: tanca el servidor si el PC deixa de fer polling ────
WATCHDOG_TIMEOUT = 12   # segons sense polling → atura
_last_poll = None
_watchdog_active = False

def _reset_watchdog():
    global _last_poll
    _last_poll = datetime.now()

def _start_watchdog(srv):
    global _watchdog_active
    _watchdog_active = True
    def check():
        if not _watchdog_active: return
        if _last_poll and (datetime.now() - _last_poll).total_seconds() > WATCHDOG_TIMEOUT:
            print("\n  Navegador tancat — aturant servidor...")
            threading.Thread(target=srv.shutdown, daemon=True).start()
            return
        threading.Timer(3, check).start()
    threading.Timer(3, check).start()

# ═══════════════════════════════════════════════════════════════════
#  HANDLER
# ═══════════════════════════════════════════════════════════════════
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        path = urlparse(self.path).path
        qs   = urlparse(self.path).query

        if path in ("/", "/index.html"):
            self._html(PC_HTML)
        elif path == "/m":
            self._html(MOBILE_HTML)
        elif path == "/qr.png":
            png = make_qr_png(MOBILE_URL)
            self._send(200,"image/png",png) if png else self._send(404,"text/plain",b"pip install qrcode")
        elif path == "/meta":
            self._json({"mobile_url": MOBILE_URL, "dest": str(dest_folder())})
        elif path == "/open-folder":
            open_folder(dest_folder()); self._json({"ok": True})
        elif path == "/open-log":
            lf = log_file(dest_folder())
            if not lf.exists(): lf.write_text("# Historial PhotoBeam\n\n", encoding="utf-8")
            open_folder(lf.parent)
            self._json({"ok": True})
        elif path == "/photos":
            _reset_watchdog()
            since = 0
            for part in qs.split("&"):
                if part.startswith("since="):
                    try: since = int(part[6:])
                    except: pass
            with queue_lock:
                out = []
                for p in photo_queue:
                    if p["id"] > since:
                        mime = mimetypes.guess_type(p["name"])[0] or "application/octet-stream"
                        is_img = file_category(p["name"]) == "foto"
                        b64 = base64.b64encode(p["data"]).decode() if is_img else ""
                        out.append({"id": p["id"], "name": p["name"],
                                    "size": len(p["data"]),
                                    "dataUrl": f"data:{mime};base64,{b64}" if is_img else ""})
            self._json(out)
        else:
            self._send(404, "text/plain", b"Not found")

    def do_POST(self):
        if urlparse(self.path).path == "/upload":
            self._handle_upload()
        else:
            self._send(404, "text/plain", b"Not found")

    def _handle_upload(self):
        global photo_id_counter
        ctype = self.headers.get("Content-Type", "")
        boundary = None
        for part in ctype.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[9:].strip().encode(); break
        if not boundary:
            self._json({"ok": False, "error": "Sense boundary"}); return

        data  = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        files = parse_multipart(data, boundary)
        if not files:
            self._json({"ok": False, "error": "Cap fitxer"}); return

        folder = dest_folder()
        with queue_lock:
            for fname, fdata in files:
                out = unique_path(folder / fname)
                out.write_bytes(fdata)
                cat = file_category(fname)
                print(f"  {'📸' if cat=='foto' else '📄'}  {out.name}  ({len(fdata)//1024} KB)")
                write_log(folder, fname, len(fdata), cat)
                notify_mac(fname, cat)
                photo_id_counter += 1
                photo_queue.append({"id": photo_id_counter, "name": fname, "data": fdata})

        self._json({"ok": True, "dest": str(folder)})

    def _html(self, h): self._send(200, "text/html; charset=utf-8", h.encode())
    def _json(self, o): self._send(200, "application/json", json.dumps(o).encode())

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

def main():
    global _watchdog_active
    folder = dest_folder()
    print()
    print("━"*56)
    print("  PhotoBeam v2 — Transferencia de fitxers via WiFi")
    print("━"*56)
    print(f"  PC  (receptor) ->  {PC_URL}")
    print(f"  Mobil (envia)  ->  {MOBILE_URL}")
    print(f"  Carpeta desti  ->  {folder}")
    print()
    print("  Prem Ctrl+C per aturar")
    print("━"*56)
    print()
    threading.Timer(1.2, lambda: webbrowser.open(PC_URL)).start()
    with socketserver.TCPServer(("", PORT), Handler) as srv:
        srv.allow_reuse_address = True
        _start_watchdog(srv)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            _watchdog_active = False
            print("\n  Servidor aturat. Fins aviat!\n")

if __name__ == "__main__":
    main()
