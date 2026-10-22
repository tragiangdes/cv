// Run a generated *_JIZURA.jsx on JIZURA's emulated After Effects object model (JIZURA/dev/aeom.js) in an ES3 realm,
// then check the comp was built and that every cut starts on the aligned vocal time.
//   node tests/ae_mock_test.js out/song_JIZURA.jsx out/song.timing.json [path/to/JIZURA]
const fs = require('fs'), vm = require('vm'), path = require('path');
const [jsxPath, timingPath, jzDir = path.join(__dirname, '..', 'JIZURA')] = process.argv.slice(2);
const AEOM = require(path.resolve(jzDir, 'dev/aeom.js'));
const SRC = fs.readFileSync(jsxPath, 'utf8').replace(/^#target.*\n/, '');
const T = JSON.parse(fs.readFileSync(timingPath, 'utf8'));
try { require(path.resolve(jzDir, 'dev/node_modules/acorn')).parse(SRC, { ecmaVersion: 3 }); }
catch (e) { console.log('ES3 SYNTAX ERROR', e.message); process.exit(1); }

const env = AEOM.makeEnv({ fonts: () => true });
const ctx = env.ctx;
for (const k of ['JSON', 'Math', 'Date', 'String', 'Number', 'Array', 'Object', 'RegExp', 'Error', 'parseInt', 'parseFloat', 'isFinite', 'isNaN', 'encodeURIComponent', 'decodeURIComponent']) delete ctx[k];
const dur = Math.max(...T.timing.filter(Boolean).map(t => (t.e || t.s) + 3));
ctx.File = function F(p) { if (!(this instanceof F)) return new F(p); this.fsName = p; this.exists = true; this.parent = { fsName: '/song' }; };
ctx.File.openDialog = () => null;
ctx.ImportOptions = function (f) { this.file = f; };
env.app.project.importFile = io => env.app.project._addFootage({ name: T.audio, path: io.file.fsName, duration: dur });
ctx.Window = function () { this.add = () => ({ preferredSize: {}, value: 0 }); this.show = this.close = this.update = () => {}; };
ctx.$.fileName = '/song/x.jsx'; ctx.$.global = ctx;
vm.createContext(ctx);
vm.runInContext(`(function(){ var d=function(o,l){for(var i=0;i<l.length;i++)delete o[l[i]];};
  d(Array.prototype,['forEach','map','filter','some','every','reduce','indexOf','find','includes']); d(Object,['keys','assign','entries']);
  d(String.prototype,['trim','includes','startsWith','endsWith','repeat','padStart']); d(Function.prototype,['bind']); this.JSON=undefined; }).call(this);`, ctx);
vm.runInContext(SRC, ctx, { filename: path.basename(jsxPath) });

const last = ctx.JA_LAST, fail = [];
if (!last) { console.log('NO COMP BUILT', ctx.__alerts); process.exit(1); }
const plan = last.plan, s = env.stats;
console.log(`style=${plan.styleKey} cuts=${plan.cuts.length} comps=${s.comps} layers=${s.layers} exprs=${s.exprs} duration=${plan.duration.toFixed(2)}`);
if (s.problems.length) fail.push(...s.problems.slice(0, 10));
if (s.exprErrors.length) fail.push(...s.exprErrors.slice(0, 10));
// every lyric cut of a timed line must start on the vocal time of its first character
const bad = [];
for (const c of plan.cuts) {
  const tm = T.timing[c.line];
  if (!tm || !tm.c || !tm.c.length || c.layout === 'interlude' || c.layout === 'title') continue;
  if (c.recap) { if (c.start < tm.e - 0.2) bad.push(`recap line ${c.line} starts ${c.start} before vocal end ${tm.e}`); continue; }
  const lineChars = c.lineText.replace(/[\s　]/g, ''), unit = c.text.replace(/[\s　]/g, '');
  const idx = lineChars.indexOf(unit), want = tm.c[idx];
  if (idx < 0) continue;
  if (Math.abs(c.start - want) > 0.16) bad.push(`line ${c.line} "${c.text}" starts ${c.start.toFixed(2)} want ${want}`);
}
console.log('cut alignment checks:', bad.length ? bad.length + ' off' : 'all on time');
bad.slice(0, 8).forEach(b => console.log('  ', b));
fail.forEach(f => console.log('PROBLEM', f));
console.log(ctx.__alerts.join('\n---\n'));
process.exit(fail.length || bad.length ? 1 : 0);
