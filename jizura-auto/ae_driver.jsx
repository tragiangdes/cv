// ---------------------------------------------------------------- JIZURA Auto driver (ExtendScript / ES3)
// Inserted by jizura_auto.py inside the JIZURA engine closure: imports the song, plans the cuts from the aligned
// timing and builds the finished comp — no panel, no green screen round trip.
var JA_CFG = __JA_CFG__;

// cut boundaries from the per-character vocal times (o.timing[line].c) instead of character-count proportions
function jzAutoBounds(units, TM, s0, visEnd, fb) {
    var b = [s0], idx = 0, n = TM.c.length, k, t, minGap = 0.15;
    for (k = 1; k < units.length; k++) {
        if (units[k].recap) t = TM.e;                      // the full-line recap comes in when the singing ends
        else { idx += jzCount(units[k - 1].text); t = TM.c[Math.min(idx, n - 1)]; }
        t = Math.max(t, b[b.length - 1] + minGap);
        if (t > visEnd - minGap * (units.length - k)) return fb;
        b.push(t);
    }
    b.push(visEnd);
    return b;
}

function jaAudioFile() {
    var here = null;
    try { here = File($.fileName).parent; } catch (e) {}
    if (here) { var f = new File(here.fsName + '/' + JA_CFG.audio); if (f.exists) return f; }
    return File.openDialog('JIZURA Auto: chọn file nhạc (' + JA_CFG.audio + ')');
}

function jaRun() {
    var f = jaAudioFile();
    if (!f) return;
    if (!app.project) app.newProject();
    var item, plan, t0 = new Date().getTime();
    app.beginUndoGroup('JIZURA Auto');
    try {
        item = app.project.importFile(new ImportOptions(f));
        var sw = { extra: JA_CFG.extra, wa: JA_CFG.wa, typo: JA_CFG.typo, kinetic: JA_CFG.kinetic, horror: JA_CFG.horror, lang: JA_CFG.lang };
        var style = JA_CFG.style, mood = JA_CFG.mood || null, seed = JA_CFG.seed || 1, hud = 0, palette = null, onTwos = true, flash = true;
        var fx = { motion: 0.7, glitch: 0.55, chroma: 0.7, decor: 0.5, density: 0.55, texture: 0.6, bgSwitch: 0.35 }, k;
        if (!style || style === 'auto' || !JZ_DATA.styles[style]) {         // おまかせ, reproducible from the seed
            var rr = new JzRng(jzHash(seed, 'auto'));
            var r = jzOmakase(null, null, function () { return rr.next(); }, sw);   // (its first arg is the mood to avoid)
            style = r.style; mood = mood || r.mood; onTwos = r.onTwos; flash = r.flash; hud = r.hud; palette = r.palette;
            for (k in r.fx) if (r.fx.hasOwnProperty(k)) fx[k] = r.fx[k];
        }
        for (k in JA_CFG.fx) if (JA_CFG.fx.hasOwnProperty(k)) fx[k] = JA_CFG.fx[k];
        fx.onTwos = onTwos; fx.flash = flash;
        fx.hud = hud === 1 ? true : hud === 2 ? false : !!JZ_DATA.styles[style].hud;
        var o = {
            lyrics: JA_CFG.lyrics, title: JA_CFG.title, artist: JA_CFG.artist, style: style, seed: seed, fx: fx,
            width: JA_CFG.width, height: JA_CFG.height, fps: JA_CFG.fps, bpm: JA_CFG.bpm || 0, starts: null,
            enabled: jzMoodEnabled(mood, seed, sw), offset: 0.4, lineScale: 1, duration: item.duration,
            extra: sw.extra, wa: sw.wa, typo: sw.typo, kinetic: sw.kinetic, horror: sw.horror, lang: sw.lang,
            centerFree: false, centerDir: 'tb', timing: JA_CFG.timing
        };
        plan = jzMakePlan(o);
        plan.hud = fx.hud;
        if (palette) plan.style = jzStyleWithPalette(plan.style, palette);
        if (JA_CFG.key) { plan.keyBg = JA_CFG.key; plan.style = jzKeyStyle(plan.style); }
    } catch (e) {
        app.endUndoGroup();
        alert('JIZURA Auto: lỗi khi lập kế hoạch: ' + e.toString() + (e.line ? ' (line ' + e.line + ')' : ''));
        return;
    }
    app.endUndoGroup();

    // build in slices with a progress window so AE stays responsive on long songs
    var w = null, bar = null, txt = null;
    try {
        w = new Window('palette', 'JIZURA Auto');
        txt = w.add('statictext', undefined, JZ_DATA.styles[plan.styleKey].name + (mood && JZ_DATA.moods[mood] ? ' × ' + JZ_DATA.moods[mood].name : '') + ' — ' + plan.cuts.length + ' cuts');
        txt.preferredSize.width = 320;
        bar = w.add('progressbar', undefined, 0, plan.cuts.length || 1); bar.preferredSize.width = 320;
        w.show();
    } catch (ew) { w = null; }
    var job;
    app.beginUndoGroup('JIZURA Auto build');
    try {
        job = jzBuildStart(plan, { roles: JZ_ROLE_DEFAULT, audioItem: item, audioStart: 0, light: !!JA_CFG.light });
        while (!job.finished) {
            job.step(700);
            if (bar) { bar.value = job.done || 0; try { w.update(); } catch (eu) {} }
        }
    } catch (e2) {
        alert('JIZURA Auto: lỗi khi dựng comp: ' + e2.toString() + (e2.line ? ' (line ' + e2.line + ')' : ''));
    } finally { app.endUndoGroup(); if (w) w.close(); }
    if (!job || !job.comp) return;
    $.global.JA_LAST = { plan: plan, comp: job.comp };
    try { job.comp.openInViewer(); } catch (eo) {}
    var msg = 'JIZURA Auto: xong "' + job.comp.name + '" — ' + plan.cuts.length + ' cuts, ' + ((new Date().getTime() - t0) / 1000).toFixed(1) + 's\n' +
        'Style: ' + plan.styleKey + (mood ? ' / mood: ' + mood : '') + ' / seed: ' + seed;
    var mf = jzMissingFonts();
    if (mf.length) msg += '\n\nThiếu font (đã thay font gần giống): ' + mf.join(', ') + '\nCài từ fonts.google.com rồi chạy lại để giống bản web.';
    if (JZLOG.length) msg += '\n\nLưu ý:\n' + JZLOG.slice(0, 10).join('\n');
    alert(msg);
}
jaRun();
