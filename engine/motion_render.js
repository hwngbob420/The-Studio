// Renders motion-graphic callouts (HTML5 + GSAP) to transparent PNG sequences. 0 API tokens.
// usage: node motion_render.js <callouts.json> <out_dir> [fps=60]
// callouts.json: [{"id":"c01","type":"card","text":"...","t":1.2,"dur":3, ...}]  -> out_dir/<id>/f_00001.png
const path = require('path');
const fs = require('fs');
const NODE = path.join(__dirname, '..', 'tools', 'node', 'node_modules');
const { chromium } = require(path.join(NODE, 'playwright-core'));

function findChrome() {
  const c = [process.env.CHROME_EXE,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'];
  return c.find(p => p && fs.existsSync(p));
}

(async () => {
  const [spec, outDir, fpsArg] = process.argv.slice(2);
  const fps = parseInt(fpsArg || '60', 10);
  const callouts = JSON.parse(fs.readFileSync(spec, 'utf8'));
  const tpl = path.join(__dirname, '..', 'vault_config', 'motion_templates');
  // gsap lives in tools/node; copy next to the template so file:// loads work
  fs.copyFileSync(path.join(NODE, 'gsap', 'dist', 'gsap.min.js'), path.join(tpl, 'gsap.min.js'));
  const browser = await chromium.launch({ executablePath: findChrome(), headless: true });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto('file:///' + path.join(tpl, 'overlay.html').replace(/\\/g, '/'));
  for (const c of callouts) {
    const dir = path.join(outDir, c.id);
    fs.mkdirSync(dir, { recursive: true });
    const dur = await page.evaluate((cc) => window.build(cc), c);
    const n = Math.round(dur * fps);
    for (let i = 0; i < n; i++) {
      await page.evaluate((t) => window.seek(t), i / fps);
      await page.screenshot({ path: path.join(dir, `f_${String(i + 1).padStart(5, '0')}.png`), omitBackground: true });
    }
    console.log(`[motion_render] ${c.id} ${c.type} ${n} frames`);
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
