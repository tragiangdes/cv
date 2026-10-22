#!/usr/bin/env python3
"""JIZURA Auto — mp3 + lời bài hát  ->  timing chuẩn từng chữ  ->  script After Effects dựng sẵn motion.

    python jizura_auto.py song.mp3 lyrics.txt                    # căn lời + tạo script AE
    python jizura_auto.py song.mp3 lyrics.txt --style auto --seed 7 --separate
    python jizura_auto.py song.mp3 --from-timing out/song.timing.json   # sửa timing tay rồi tạo lại script

Kết quả (thư mục --out, mặc định ./out):
    <tên>.timing.json   timing từng dòng + từng ký tự (có thể sửa tay)
    <tên>.lrc           lời có mốc [mm:ss.xx] — dán thẳng vào JIZURA web / panel AE cũng được
    <tên>_JIZURA.jsx    chạy trong AE: File > Scripts > Run Script File...  -> import nhạc, dựng comp hoàn chỉnh
    <tên>.mp3           bản sao file nhạc (script tự tìm file này cạnh nó)
"""
import argparse, difflib, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
JIZURA_GIT = 'https://github.com/852wa/JIZURA'

# ---------------------------------------------------------------- lyric parsing (mirror of jzParseLyrics in ae/00_core.jsx)
TIME_RE = re.compile(r'^\[(\d+):(\d+(?:[.:]\d+)?)\]')
META_RE = re.compile(r'^\[(ti|ar|al|by|offset):(.*)\]$', re.I)
INTERLUDE_RE = re.compile(r'^\[\s*(間奏|间奏|interlude|instrumental|inst|간주)(?:\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:s|sec|秒|초)?)?\s*\]$', re.I)
WS_RE = re.compile(r'[\s　]+')


def parse_lyrics(raw):
    """Rows of the lyric sheet -> list of dicts, one per JIZURA line (same order as the AE planner's lines).
    row: the original row without LRC tags (markup kept), sung: the text JIZURA shows (what gets aligned)."""
    lines, meta = [], {}
    for row in raw.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        s0 = row.strip()
        if not s0 or s0.startswith('#'):
            continue
        m = META_RE.match(s0)
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()
            continue
        s = s0
        while True:                                   # drop existing LRC stamps: we re-time everything
            m = TIME_RE.match(s)
            if not m: break
            s = s[m.end():]
        s = s.strip()
        if INTERLUDE_RE.match(s):
            lines.append({'row': s, 'sung': '', 'interlude': True})
            continue
        t = s
        bar = t.find('|')
        if bar >= 0: t = t[:bar].strip()
        if len(t) > 1 and t.endswith('!'): t = t[:-1].strip()
        t = re.sub(r'\*([^*]+)\*', r'\1', t)
        if '/' in t:
            parts = [p.strip() for p in t.split('/') if p.strip()]
            t = (' ' if re.search(r'[A-Za-z]', t) else '').join(parts)
        if not t:
            continue
        lines.append({'row': s, 'sung': t, 'interlude': False})
    return lines, meta


def guess_lang(text):
    """Whisper needs the language for forced alignment; guess it from the script of the lyrics"""
    if re.search(r'[぀-ヿ]', text): return 'ja'
    if re.search(r'[가-힯]', text): return 'ko'
    if re.search(r'[一-鿿]', text): return 'zh'
    if re.search(r'[ăâđêôơưĂÂĐÊÔƠƯạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]', text): return 'vi'
    return 'en'


def chars_of(text):
    """non-space characters, the unit JIZURA counts with jzCount()"""
    return list(WS_RE.sub('', text))


# ---------------------------------------------------------------- alignment
def align(audio, lines, args):
    try:
        import stable_whisper
    except ImportError:
        sys.exit('Thiếu stable-ts. Cài: pip install -r requirements.txt  (xem README)')
    sung = [L['sung'] for L in lines if not L['interlude']]
    text = '\n'.join(sung)
    print(f'[1/3] Tải model Whisper "{args.model}"…', flush=True)
    model = stable_whisper.load_model(args.model, device=args.device)
    print('[2/3] Căn lời theo giọng hát' + (' (tách vocal bằng demucs)' if args.separate else '') + '…', flush=True)
    lang = args.lang or guess_lang(text)
    print('      ngôn ngữ:', lang, flush=True)
    kw = dict(language=lang, original_split=True)
    if args.separate: kw['denoiser'] = 'demucs'
    result = model.align(audio, text, **kw)
    if args.refine:
        print('      refine timestamps…', flush=True)
        model.refine(audio, result, word_level=True)
    words = [(w.word, float(w.start), float(w.end)) for seg in result.segments for w in seg.words]
    return words


def char_times(words, lines):
    """Spread each aligned word over its characters, then map those onto the lyric characters with difflib
    (robust to whatever spacing / normalisation the aligner applied)."""
    A, At = [], []
    for w, s, e in words:
        cs = chars_of(w)
        if not cs: continue
        e = max(e, s + 0.01)
        for i, c in enumerate(cs):
            A.append(c.lower())
            At.append((s + (e - s) * i / len(cs), s + (e - s) * (i + 1) / len(cs)))
    B, owner = [], []
    for li, L in enumerate(lines):
        for c in chars_of(L['sung']):
            B.append(c.lower()); owner.append(li)
    Bt = [None] * len(B)
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
            for k in range(j2 - j1): Bt[j1 + k] = At[i1 + k]
        elif tag == 'replace' and i2 > i1:            # different length: stretch the aligned span over the lyric span
            s, e = At[i1][0], At[i2 - 1][1]
            n = j2 - j1
            for k in range(n): Bt[j1 + k] = (s + (e - s) * k / n, s + (e - s) * (k + 1) / n)
    fill_gaps(Bt, owner)
    per = [[] for _ in lines]
    for b, li in enumerate(owner): per[li].append(Bt[b])
    return per


def fill_gaps(T, owner, step=0.15):
    """Place characters the aligner missed. Inside one line: interpolate between the neighbours. Across a line
    break (the gap holds a pause): continue the earlier line / lead into the later one at ~step s per character,
    so a missed word never stretches a line over the pause."""
    known = [i for i, t in enumerate(T) if t is not None]
    if not known: raise SystemExit('Không căn được chữ nào — kiểm tra lời có khớp bài hát / thử --separate / --model large-v3')
    for i in range(len(T)):
        if T[i] is not None: continue
        a = max((k for k in known if k < i), default=None)
        b = min((k for k in known if k > i), default=None)
        if a is not None and b is not None and owner[a] == owner[i] == owner[b]:
            f = (i - a) / (b - a); t = T[a][1] + (T[b][0] - T[a][1]) * f
        elif a is not None and owner[a] == owner[i]:
            t = T[a][1] + step * (i - a - 1)
            if b is not None: t = min(t, T[b][0] - step * (b - i))
        elif b is not None:
            t = T[b][0] - step * (b - i)
            if a is not None: t = max(t, T[a][1])
        else:
            t = T[a][1] + step * (i - a)
        t = max(0.0, t)
        T[i] = (t, t + step * 0.8)


def build_timing(lines, per, lead):
    """per-line {s, e, c[]}; enforces monotonic line starts, gives interludes a slot"""
    out, prev_end = [], 0.0
    for li, L in enumerate(lines):
        if L['interlude']:
            out.append(None); continue
        ts = per[li]
        c = [max(0.0, round(t[0] - lead, 3)) for t in ts]
        for k in range(1, len(c)): c[k] = max(c[k], c[k - 1])
        s = c[0] if c else prev_end
        s = max(s, prev_end - lead)
        c = [max(x, s) for x in c]
        e = round(max(ts[-1][1] if ts else s + 1, s + 0.3), 3)
        out.append({'s': round(s, 3), 'e': e, 'c': c})
        prev_end = e
    # interludes start just after the previous sung line ends
    for li, L in enumerate(lines):
        if not L['interlude']: continue
        pe = next((out[k]['e'] for k in range(li - 1, -1, -1) if out[k]), 0.0)
        out[li] = {'s': round(pe + 0.3, 3), 'e': None, 'c': [], 'interlude': True}
    return out


def fmt_lrc(t):
    m = int(t // 60); return '[%02d:%05.2f]' % (m, t - m * 60)


def detect_bpm(audio):
    try:
        import librosa
        y, sr = librosa.load(audio, sr=22050, mono=True)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo[0] if hasattr(tempo, '__len__') else tempo)
        return round(bpm, 1) if 40 < bpm < 260 else 0
    except Exception as e:
        print('      (bỏ qua BPM:', e, ')')
        return 0


# ---------------------------------------------------------------- After Effects script
PLAN_ANCHOR_VIS = "var nch = jzCount(ln.text), visEnd = Math.min(e0, s0 + Math.max(3.6, nch * 0.5 + 1.2)), D = visEnd - s0;"
PLAN_PATCH_VIS = PLAN_ANCHOR_VIS + """
        // JIZURA Auto: real vocal timing -> keep the line up until the singer finishes it (plus a short tail)
        var TM = o.timing && o.timing[li] && o.timing[li].c && o.timing[li].c.length ? o.timing[li] : null;
        if (TM) { visEnd = Math.min(e0, Math.max(TM.e + jzClamp((e0 - TM.e) * 0.3, 0.2, 0.8), s0 + 0.6)); D = visEnd - s0; }"""
PLAN_ANCHOR_BOUNDS = "var bounds = [s0], acc = s0;"
PLAN_PATCH_BOUNDS = "if (TM && recap && visEnd - TM.e < 0.7) { units.pop(); recap = false; }\n        " + PLAN_ANCHOR_BOUNDS
PLAN_ANCHOR_BOUNDS_END = "bounds.push(i === units.length - 1 ? visEnd : acc); }"
PLAN_PATCH_BOUNDS_END = PLAN_ANCHOR_BOUNDS_END + "\n        if (TM) bounds = jzAutoBounds(units, TM, s0, visEnd, bounds);"


def build_core(jizura):
    """JIZURA's own build_ae.py --core (engine without the ScriptUI panel)"""
    tmp = tempfile.mkdtemp(prefix='jzauto')
    out = os.path.join(tmp, 'core.jsx')
    subprocess.check_call([sys.executable, 'build_ae.py', '--core', '--out', out], cwd=jizura, stdout=subprocess.DEVNULL)
    src = open(out, encoding='utf-8').read()
    shutil.rmtree(tmp, ignore_errors=True)
    for a, b in ((PLAN_ANCHOR_VIS, PLAN_PATCH_VIS), (PLAN_ANCHOR_BOUNDS, PLAN_PATCH_BOUNDS), (PLAN_ANCHOR_BOUNDS_END, PLAN_PATCH_BOUNDS_END)):
        if src.count(a) != 1:
            sys.exit('Phiên bản JIZURA này khác với bản tool hỗ trợ (không tìm thấy: %s…). Thử --jizura với bản v0.10.x.' % a[:40])
        src = src.replace(a, b)
    return src


def esc_ascii(s):
    """same escaping as build_ae.py: the .jsx stays pure ASCII so ExtendScript reads it under any locale"""
    out = []
    for ch in s:
        o = ord(ch)
        if o < 128: out.append(ch)
        elif o <= 0xFFFF: out.append('\\u%04X' % o)
        else:
            o -= 0x10000; out.append('\\u%04X\\u%04X' % (0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)))
    return ''.join(out)


def make_ae_script(jizura, cfg):
    core = build_core(jizura)
    driver = open(os.path.join(HERE, 'ae_driver.jsx'), encoding='utf-8').read()
    driver = driver.replace('__JA_CFG__', json.dumps(cfg, ensure_ascii=False))
    marker = '\n$.global.JZ_CORE = {'
    if core.count(marker) != 1: sys.exit('Không nhận ra file core của JIZURA')
    src = core.replace(marker, '\n' + driver + marker)
    src = '#target aftereffects\n' + src.replace('JIZURA 字面 — After Effects build engine for the CEP panel', 'JIZURA Auto — one-click lyric video build (engine: JIZURA)', 1)
    return esc_ascii(src)


def ensure_jizura(path):
    if path and os.path.isfile(os.path.join(path, 'build_ae.py')): return path
    path = path or os.path.join(HERE, 'JIZURA')
    if not os.path.isfile(os.path.join(path, 'build_ae.py')):
        print('      tải mã nguồn JIZURA →', path, flush=True)
        subprocess.check_call(['git', 'clone', '--depth', '1', JIZURA_GIT, path])
    return path


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description='mp3 + lời -> timing + script After Effects (JIZURA)')
    ap.add_argument('audio', help='file nhạc (mp3/wav/m4a…)')
    ap.add_argument('lyrics', nargs='?', help='file lời .txt (mỗi dòng một câu, cú pháp JIZURA: / * ! |note [interlude 8])')
    ap.add_argument('-o', '--out', default='out')
    ap.add_argument('--from-timing', help='bỏ qua bước căn lời, dùng .timing.json đã có (vd. sau khi sửa tay)')
    ap.add_argument('--timing-only', action='store_true', help='chỉ xuất timing/LRC, không tạo script AE')
    # alignment
    ap.add_argument('--lang', default=None, help='ngôn ngữ lời: ja, en, vi, ko, zh… (mặc định: đoán từ chữ viết)')
    ap.add_argument('--model', default='medium', help='model Whisper: small / medium / large-v3 (chính xác hơn, chậm hơn)')
    ap.add_argument('--device', default=None, help='cuda / cpu (mặc định tự chọn)')
    ap.add_argument('--separate', action='store_true', help='tách vocal bằng demucs trước khi căn (nên bật với nhạc dày)')
    ap.add_argument('--refine', action='store_true', help='tinh chỉnh timestamp thêm một lượt (chậm gấp ~2)')
    ap.add_argument('--lead', type=float, default=0.12, help='hiện chữ sớm hơn giọng hát bao nhiêu giây (mặc định 0.12)')
    ap.add_argument('--bpm', default='auto', help='"auto" (librosa), số, hoặc 0 để tắt')
    # look
    ap.add_argument('--style', default='auto', help='"auto" = おまかせ (random theo seed) hoặc key style của JIZURA, vd. noir, neon…')
    ap.add_argument('--mood', default=None, help='key mood của JIZURA (tuỳ chọn)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--size', default='1920x1080')
    ap.add_argument('--fps', type=float, default=24)
    ap.add_argument('--title', default=''); ap.add_argument('--artist', default='')
    ap.add_argument('--key', choices=['green', 'black'], default=None, help='nền chroma key (giống workflow cũ) — bỏ trống để có nền đầy đủ')
    ap.add_argument('--light', action='store_true', help='chế độ nhẹ (ít layer hơn ~40%%)')
    for k, d in (('motion', .7), ('glitch', .55), ('chroma', .7), ('decor', .5), ('density', .55), ('texture', .6), ('bgswitch', .35)):
        ap.add_argument('--' + k, type=float, default=None, help='0..1 (mặc định %s; với --style auto lấy theo mood)' % d)
    ap.add_argument('--extra', action='store_true', help='bật bộ hiệu ứng 追加分'); ap.add_argument('--no-wa', action='store_true', help='tắt bộ 和風')
    ap.add_argument('--typo', action='store_true'); ap.add_argument('--kinetic', action='store_true'); ap.add_argument('--horror', action='store_true')
    ap.add_argument('--jizura', default=None, help='đường dẫn repo JIZURA (mặc định: tự clone vào jizura-auto/JIZURA)')
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    name = os.path.splitext(os.path.basename(a.audio))[0]
    if a.from_timing:
        T = json.load(open(a.from_timing, encoding='utf-8'))
        lines, meta, timing, bpm = T['lines'], T.get('meta', {}), T['timing'], T.get('bpm', 0)
    else:
        if not a.lyrics: ap.error('cần file lời (hoặc --from-timing)')
        lines, meta = parse_lyrics(open(a.lyrics, encoding='utf-8-sig').read())
        if not any(not L['interlude'] for L in lines): sys.exit('File lời trống')
        words = align(a.audio, lines, a)
        timing = build_timing(lines, char_times(words, lines), a.lead)
        bpm = detect_bpm(a.audio) if a.bpm == 'auto' else float(a.bpm or 0)
        json.dump({'audio': os.path.basename(a.audio), 'bpm': bpm, 'meta': meta, 'lines': lines, 'timing': timing},
                  open(os.path.join(a.out, name + '.timing.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    lrc = []
    if meta.get('ti') or a.title: lrc.append('[ti:%s]' % (a.title or meta['ti']))
    if meta.get('ar') or a.artist: lrc.append('[ar:%s]' % (a.artist or meta['ar']))
    for L, t in zip(lines, timing): lrc.append(fmt_lrc(t['s']) + L['row'])
    lyr = '\n'.join(lrc) + '\n'
    open(os.path.join(a.out, name + '.lrc'), 'w', encoding='utf-8').write(lyr)
    print('      %d dòng, BPM %s → %s' % (len(lines), bpm or '-', os.path.join(a.out, name + '.lrc')))
    if a.timing_only: return

    print('[3/3] Tạo script After Effects…', flush=True)
    w, h = (int(x) for x in a.size.lower().replace('×', 'x').split('x'))
    fx = {}
    for k in ('motion', 'glitch', 'chroma', 'decor', 'density', 'texture'):
        if getattr(a, k) is not None: fx[k] = getattr(a, k)
    if a.bgswitch is not None: fx['bgSwitch'] = a.bgswitch
    ext = os.path.splitext(a.audio)[1]
    cfg = {'audio': name + ext, 'lyrics': lyr, 'timing': [t if t and t.get('c') else None for t in timing], 'bpm': bpm,
           'title': a.title, 'artist': a.artist, 'style': a.style, 'mood': a.mood, 'seed': a.seed, 'fx': fx,
           'width': w, 'height': h, 'fps': a.fps, 'key': a.key, 'light': a.light, 'lang': a.lang if a.lang in ('ja', 'en', 'ko', 'zh-Hant', 'zh-Hans') else 'auto',
           'extra': a.extra, 'wa': not a.no_wa, 'typo': a.typo, 'kinetic': a.kinetic, 'horror': a.horror}
    jsx = make_ae_script(ensure_jizura(a.jizura), cfg)
    jp = os.path.join(a.out, name + '_JIZURA.jsx')
    open(jp, 'w', encoding='utf-8').write(jsx)
    dst = os.path.join(a.out, name + ext)
    if os.path.abspath(dst) != os.path.abspath(a.audio): shutil.copyfile(a.audio, dst)
    print('Xong →', jp)
    print('Trong After Effects: File > Scripts > Run Script File… → chọn file trên.')


if __name__ == '__main__':
    main()
