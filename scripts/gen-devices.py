#!/usr/bin/env python3
"""Generate device compatibility outputs from peacock-ports status.toml files.

Outputs:
  - site/devices/status.json     machine-readable (also feeds any live widget)
  - site/devices/index.html      public /devices page: brand-grouped cards, image +
                                  overall status only (NO detailed matrix — that's the wiki)
  - wiki `devices`               index page: brand-grouped links
  - wiki `devices/<codename>`    one page PER device with the detailed matrix in a
                                  marked block; author prose/photos around it are preserved

Device images: site/devices/img/<codename>.{webp,png,jpg} (git). Both site and wiki
reference the same file. Drop one in per device.

Source of truth + design: peacock-ports/device/STATUS.md
"""
import os, sys, json, glob, html, re, datetime, urllib.request, subprocess, shutil

PORTS = os.environ.get('PEACOCK_PORTS', os.path.expanduser('~/Documents/bro/PeacockProject/peacock-ports'))
SITE  = os.environ.get('PEACOCK_SITE',  os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE_URL = os.environ.get('SITE_URL', 'https://peacockos.org')
WIKI  = os.environ.get('WIKI_URL', 'https://wiki.peacockos.org')

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

GROUPS = [
    ('basics',       'Basics',        ['flashing', 'recovery', 'screen', 'touch', 'battery', 'usb_net']),
    ('multimedia',   'Multimedia',    ['accel_3d', 'audio', 'camera_rear', 'camera_front', 'camera_flash']),
    ('connectivity', 'Connectivity',  ['wifi', 'bluetooth', 'gps']),
    ('modem',        'Modem',         ['calls', 'sms', 'data']),
    ('misc',         'Miscellaneous', ['usb_otg', 'fingerprint', 'fde']),
    ('sensors',      'Sensors',       ['accelerometer', 'ambient_light', 'proximity', 'gyroscope', 'haptics']),
]
LABELS = {'recovery': 'Recovery (PRP)', 'usb_net': 'USB networking', 'accel_3d': '3D acceleration',
          'camera_rear': 'Rear camera', 'camera_front': 'Front camera', 'camera_flash': 'Camera flash',
          'gps': 'GPS', 'sms': 'SMS', 'data': 'Mobile data', 'usb_otg': 'USB OTG',
          'fde': 'Full-disk encryption', 'ambient_light': 'Ambient light', 'fingerprint': 'Fingerprint'}
EMOJI = {'works': '✅', 'partial': '🟡', 'broken': '❌', 'untested': '⚪'}
WORD  = {'works': 'Works', 'partial': 'Partial', 'broken': 'Broken', 'untested': 'Untested'}
MARK_START = '<!-- peacock:status:start (generated — do not edit inside) -->'
MARK_END   = '<!-- peacock:status:end -->'
VERIFIED_NOTE = ('Verified so far on each phone: the bootloader, PRP recovery (SSH + touch), '
                 'and boot through to the XFCE desktop with working touch. Everything else is **untested**, not broken.')

def label(k): return LABELS.get(k, k.replace('_', ' ').capitalize())
def esc(s):   return html.escape(str(s))
def codename(d): return d.get('device', {}).get('codename', d['_port'])
def name(d):     return d.get('device', {}).get('name', codename(d))

def platform(dev):
    soc = (dev.get('hardware', {}).get('chipset', '') or '').lower()
    if 'mediatek' in soc or soc.startswith('mt'): return ('MediaTek', 'MinKernel')
    if 'qualcomm' in soc or 'snapdragon' in soc or 'msm' in soc or 'apq' in soc: return ('Qualcomm', 'lk2nd')
    if 'qemu' in soc or dev.get('device', {}).get('type') == 'vm': return ('Virtual', '—')
    return (dev.get('hardware', {}).get('architecture', '—'), '—')

def load():
    devs = []
    for p in sorted(glob.glob(os.path.join(PORTS, 'device', '*', 'status.toml'))):
        with open(p, 'rb') as f:
            d = tomllib.load(f)
        d['_port'] = os.path.basename(os.path.dirname(p))
        devs.append(d)
    return devs

def by_brand(devs):
    brands = {}
    for d in devs:
        brands.setdefault(d.get('device', {}).get('manufacturer', 'Other'), []).append(d)
    order = sorted(brands, key=lambda b: (b.lower() == 'qemu', b.lower()))   # QEMU last
    return [(b, sorted(brands[b], key=lambda d: name(d))) for b in order]

def support_items(dev):
    sup = dev.get('support', {})
    for gkey, glabel, keys in GROUPS:
        g = sup.get(gkey, {})
        rows = [(k, label(k), g[k], g.get(k + '_note')) for k in keys if k in g]
        if rows:
            yield glabel, rows

def device_img(code):
    for ext in ('webp', 'png', 'jpg', 'jpeg', 'avif'):
        if os.path.exists(os.path.join(SITE, 'devices', 'img', f'{code}.{ext}')):
            return f'/devices/img/{code}.{ext}'
    return None

def build_images(devs):
    """Convert each device package's image.* (peacock-ports/device/<port>/) into an
    optimized webp at site/devices/img/<codename>.webp. Devs drop the source photo in
    the port; CI does the conversion."""
    os.makedirs(os.path.join(SITE, 'devices', 'img'), exist_ok=True)
    magick = shutil.which('magick') or shutil.which('convert')
    cwebp = shutil.which('cwebp')
    for d in devs:
        src = next((p for ext in ('png', 'jpg', 'jpeg', 'webp', 'avif')
                    for p in [os.path.join(PORTS, 'device', d['_port'], f'image.{ext}')]
                    if os.path.exists(p)), None)
        if not src:
            continue
        code = codename(d)
        out = os.path.join(SITE, 'devices', 'img', f'{code}.webp')
        if magick:
            subprocess.run([magick, src, '-resize', '800x800>', '-strip', '-quality', '82', out], check=True)
        elif cwebp:
            subprocess.run([cwebp, '-quiet', '-q', '82', '-resize', '800', '0', src, '-o', out], check=True)
        else:
            shutil.copy(src, os.path.join(SITE, 'devices', 'img', f"{code}.{src.rsplit('.', 1)[1]}"))
            print(f'  image {code}: no webp tool, copied source as-is'); continue
        print(f'  image {code}: {os.path.relpath(src, PORTS)} -> {code}.webp')

# ---------------------------------------------------------------- site (cards only)
def render_site(devs):
    chrome = open(os.path.join(SITE, 'index.html'), encoding='utf-8').read()
    sections = ''
    for brand, ds in by_brand(devs):
        cards = ''
        for d in ds:
            code = codename(d); plat, _ = platform(d); mat = d.get('software', {}).get('maturity', '')
            img = device_img(code)
            imghtml = (f'<div class="dc-img" style="background-image:url({img})"></div>' if img
                       else f'<div class="dc-img ph"><span>{esc(name(d)[:1])}</span></div>')
            sdata = esc((f'{name(d)} {code} {brand} {plat}').lower())
            cards += (f'<a class="dev-card" data-s="{sdata}" href="{WIKI}/devices/{esc(code)}">{imghtml}'
                      f'<div class="dc-body"><h4>{esc(name(d))}</h4>'
                      f'<div class="dc-meta"><code>{esc(code)}</code><span>{esc(plat)}</span>'
                      f'<span class="badge {esc(mat)}">{esc(mat)}</span></div></div></a>')
        sections += f'<div class="dv-brand reveal"><h3>{esc(brand)}</h3><div class="dev-grid">{cards}</div></div>'

    style = """
<style>
.dv-wrap{max-width:1080px;margin:0 auto;padding:0 24px}
.dv-brand h3{font-family:var(--serif,'Instrument Serif',serif);font-size:26px;color:var(--ink-dim);border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:8px;margin:44px 0 0}
.dev-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:20px;margin-top:22px}
.dev-card{display:block;border:1px solid rgba(255,255,255,.08);border-radius:14px;overflow:hidden;background:rgba(255,255,255,.02);text-decoration:none;color:inherit;transition:border-color .2s,transform .2s}
.dev-card:hover{border-color:rgba(43,212,196,.5);transform:translateY(-2px)}
.dc-img{aspect-ratio:4/3;background-size:cover;background-position:center;background-color:#0b1219}
.dc-img.ph{display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,rgba(43,212,196,.12),rgba(142,123,240,.14))}
.dc-img.ph span{font-family:var(--serif,'Instrument Serif',serif);font-size:52px;color:rgba(244,241,232,.45)}
.dc-body{padding:14px 16px}
.dc-body h4{margin:0 0 8px;font-size:16px}
.dc-meta{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-family:var(--mono);font-size:11px;color:var(--ink-dim)}
.badge{text-transform:uppercase;letter-spacing:.07em;padding:.15em .6em;border-radius:999px;border:1px solid rgba(255,255,255,.18);color:var(--ink-dim)}
.badge.stable{color:#2BD4C4;border-color:rgba(43,212,196,.5)}
.badge.testing{color:#E8B84B;border-color:rgba(232,184,75,.5)}
.badge.experimental{color:#E8685B;border-color:rgba(232,104,91,.5)}
.dev-search{width:100%;max-width:440px;margin:26px 0 4px;padding:12px 16px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.12);border-radius:10px;color:var(--ink,#f4f1e8);font-family:var(--mono);font-size:14px;outline:none}
.dev-search:focus{border-color:rgba(43,212,196,.6)}
.dev-search::placeholder{color:var(--ink-dim)}
.dv-noresult{color:var(--ink-dim);font-family:var(--mono);font-size:14px;margin:30px 0;display:none}
</style>"""
    body = f"""  <section class="module" style="padding-top:clamp(110px,16vh,170px);">
    <div class="wrap dv-wrap">
      <div class="reveal">
        <span class="eyebrow"><span class="pip"></span>Supported devices</span>
        <h2>What runs <span class="grad">PeacockOS.</span></h2>
      </div>
      <div class="stmt reveal"><p>Phones we have PeacockOS on, grouped by maker. {VERIFIED_NOTE.replace('**','')}
      Tap a device for the full compatibility breakdown on the
      <a href="{WIKI}/devices" style="border-bottom:1px solid var(--line2)">wiki</a>.</p></div>
      {style}
      <input id="dev-search" class="dev-search reveal" type="search" placeholder="Search by device or brand…" autocomplete="off" aria-label="Search devices">
      {sections}
      <p class="dv-noresult" id="dv-noresult">No device matches that.</p>
      <script>
      (function(){{var i=document.getElementById('dev-search'),nr=document.getElementById('dv-noresult');if(!i)return;
        i.addEventListener('input',function(){{var q=i.value.toLowerCase().trim(),hits=0;
          document.querySelectorAll('.dv-brand').forEach(function(s){{var a=false;
            s.querySelectorAll('.dev-card').forEach(function(c){{var m=!q||c.dataset.s.indexOf(q)>-1;c.style.display=m?'':'none';if(m){{a=true;hits++;}}}});
            s.style.display=a?'':'none';}});
          if(nr)nr.style.display=hits?'none':'block';}});}})();
      </script>
    </div>
  </section>
"""
    out = re.sub(r'</header>.*?<footer', '</header>\n' + body + '\n\n  <footer', chrome, count=1, flags=re.DOTALL)
    out = out.replace('<title>Peacock // OS: your device, unshackled</title>', '<title>Supported devices · Peacock // OS</title>')
    out = out.replace('<a class="word" href="#">', '<a class="word" href="/">')
    os.makedirs(os.path.join(SITE, 'devices'), exist_ok=True)
    open(os.path.join(SITE, 'devices', 'index.html'), 'w', encoding='utf-8').write(out)
    return len(out)

# ---------------------------------------------------------------- wiki
def matrix_md(dev):
    dd, hw, sw = dev['device'], dev.get('hardware', {}), dev.get('software', {})
    lines = ['| | |', '|---|---|']
    specs = [('Codename', codename(dev)), ('Chipset', hw.get('chipset')), ('Architecture', hw.get('architecture')),
             ('Display', hw.get('display')), ('Memory', hw.get('memory')), ('Storage', hw.get('storage')),
             ('Released', dd.get('released')), ('Ships with', sw.get('original_android')),
             ('Kernel', sw.get('kernel')), ('Maturity', sw.get('maturity'))]
    for k, v in specs:
        if v and str(v) not in ('TODO', 'n/a', '0'):
            lines.append(f'| **{k}** | {v} |')
    lines += ['', '| Feature | Status |', '|---|---|']
    for glabel, rows in support_items(dev):
        lines.append(f'| **{glabel}** | |')
        for k, lab, status, note in rows:
            cell = f"{EMOJI.get(status, '')} {WORD.get(status, status)}"
            if note:
                cell += f" — {note}"
            lines.append(f'| {lab} | {cell} |')
    return '\n'.join(lines)

def device_stub(dev, block):
    n, code = name(dev), codename(dev)
    return (f"# {n}\n\n"
            f"_Add an overview, install notes and quirks for the {n} here. "
            f"Device photo: drop `image.png` (or .jpg) into this device's package in "
            f"`peacock-ports/device/{dev['_port']}/` — CI converts it to webp automatically. "
            f"The compatibility block below is generated — edit around it, not between the markers._\n\n"
            f"{MARK_START}\n{block}\n{MARK_END}\n")

def replace_marked(content, block):
    if MARK_START in content and MARK_END in content:
        pre = content.split(MARK_START)[0]
        post = content.split(MARK_END, 1)[1]
        return f"{pre}{MARK_START}\n{block}\n{MARK_END}{post}"
    return f"{content.rstrip()}\n\n{MARK_START}\n{block}\n{MARK_END}\n"

def index_md(devs):
    lines = ['# Supported devices', '', f'> {VERIFIED_NOTE}', '',
             'Each device has its own page with the full compatibility breakdown.', '']
    for brand, ds in by_brand(devs):
        lines.append(f'## {brand}')
        for d in ds:
            plat, boot = platform(d)
            lines.append(f"- [{name(d)}](/devices/{codename(d)}) — `{codename(d)}` · {plat} · "
                         f"{boot} · {d.get('software',{}).get('maturity','')}")
        lines.append('')
    return '\n'.join(lines)

def token():
    t = os.environ.get('WIKI_API_TOKEN')
    if not t:
        sf = os.path.expanduser('~/Documents/bro/PeacockProject/infra/peacock-community/SECRETS.api-tokens.txt')
        if os.path.exists(sf):
            m = re.search(r'## Wiki\.js.*?TOKEN=(\S+)', open(sf).read(), re.DOTALL)
            t = m and m.group(1)
    return t

def gql(tok, query, variables=None):
    req = urllib.request.Request(WIKI + '/graphql',
        data=json.dumps({'query': query, 'variables': variables or {}}).encode(),
        headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read().decode())

def wiki_save(tok, pid, path, title, content, desc):
    common = (f'content:$content,description:$description,editor:"markdown",isPrivate:false,'
              f'isPublished:true,locale:"en",path:$path,tags:[],title:$title')
    if pid:
        q = (f'mutation($content:String!,$description:String!,$path:String!,$title:String!)'
             f'{{pages{{update(id:{pid},{common}){{responseResult{{succeeded message}}}}}}}}')
    else:
        q = (f'mutation($content:String!,$description:String!,$path:String!,$title:String!)'
             f'{{pages{{create({common}){{responseResult{{succeeded message}} page{{id path}}}}}}}}')
    r = gql(tok, q, {'content': content, 'description': desc, 'path': path, 'title': title})
    node = r['data']['pages']['update' if pid else 'create']
    return node['responseResult'], node.get('page')

def sync_wiki(devs):
    tok = token()
    if not tok:
        print('  (no WIKI_API_TOKEN — skipping wiki)'); return
    pages = gql(tok, '{ pages { list { id path } } }')['data']['pages']['list']
    pmap = {p['path']: p['id'] for p in pages}
    rr, _ = wiki_save(tok, pmap.get('devices'), 'devices', 'Supported devices',
                      index_md(devs), 'Devices that run PeacockOS, by brand.')
    print('  wiki devices (index):', rr['succeeded'])
    for d in devs:
        path = f'devices/{codename(d)}'; block = matrix_md(d)
        if path in pmap:
            cur = gql(tok, f'{{ pages {{ single(id:{pmap[path]}) {{ content }} }} }}')['data']['pages']['single']['content']
            content = replace_marked(cur, block)
        else:
            content = device_stub(d, block)
        rr, _ = wiki_save(tok, pmap.get(path), path, name(d), content, f'{name(d)} on PeacockOS.')
        print(f'  wiki {path}:', rr['succeeded'], '' if rr['succeeded'] else rr.get('message'))

def main():
    devs = load()
    print('loaded %d devices: %s' % (len(devs), ', '.join(codename(d) for d in devs)))
    payload = {'generated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'devices': [{k: v for k, v in d.items() if not k.startswith('_')} | {'port': d['_port']} for d in devs]}
    os.makedirs(os.path.join(SITE, 'devices', 'img'), exist_ok=True)
    open(os.path.join(SITE, 'devices', 'status.json'), 'w').write(json.dumps(payload, indent=1))
    print('  wrote devices/status.json')
    build_images(devs)
    print('  wrote devices/index.html (%d bytes)' % render_site(devs))
    sync_wiki(devs)

if __name__ == '__main__':
    main()
