// Render .bpmn files to PNG (and SVG) with the bpmn.io viewer.
// usage: node render.js out_dir file1.bpmn [file2.bpmn ...]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const VIEWER = path.join(__dirname, 'node_modules/bpmn-js/dist/bpmn-viewer.production.min.js');
const CSS = ['diagram-js.css', 'bpmn-js.css', 'bpmn-font/css/bpmn.css']
  .map((f) => fs.readFileSync(path.join(__dirname, 'node_modules/bpmn-js/dist/assets', f), 'utf8'))
  .join('\n');

(async () => {
  const [outDir, ...files] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1600, height: 1000 } });
  await page.setContent(`<html><head><style>${CSS}
    body{margin:0;background:#fff;font-family:Arial,sans-serif}
    #c{width:20000px;height:20000px}
    .djs-label, .djs-element text{font-family:Arial,sans-serif !important}
  </style></head><body><div id="c"></div></body></html>`);
  await page.addScriptTag({ path: VIEWER });
  for (const file of files) {
    const xml = fs.readFileSync(file, 'utf8');
    const res = await page.evaluate(async (xml) => {
      document.getElementById('c').innerHTML = '';
      const viewer = new BpmnJS({ container: '#c' });
      try {
        const { warnings } = await viewer.importXML(xml);
        const { svg } = await viewer.saveSVG();
        return { svg, warnings: warnings.map((w) => w.message) };
      } catch (e) {
        return { error: String(e) };
      }
    }, xml);
    const base = path.join(outDir, path.basename(file, '.bpmn'));
    if (res.error) { console.error(file, 'ERROR', res.error); continue; }
    if (res.warnings.length) console.warn(file, 'warnings:', res.warnings.slice(0, 5));
    fs.writeFileSync(base + '.svg', res.svg);
    // Rasterise the exported SVG on a white page at 2x.
    const m = res.svg.match(/width="([\d.]+)" height="([\d.]+)"/);
    const w = Math.ceil(parseFloat(m[1])), h = Math.ceil(parseFloat(m[2]));
    const p2 = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: w, height: h } });
    await p2.setContent(`<html><body style="margin:0;background:#fff">${res.svg}</body></html>`);
    await p2.screenshot({ path: base + '.png', clip: { x: 0, y: 0, width: w, height: h } });
    await p2.close();
    console.log('rendered', base + '.png', w + 'x' + h);
  }
  await browser.close();
})();
