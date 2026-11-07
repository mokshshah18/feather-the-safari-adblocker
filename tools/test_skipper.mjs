// Smoke test for Skipper/Resources/youtube.js using a fake YouTube player.
// Runs headless Chromium through Playwright; the script is injected the way a
// content script would be (before any page script).
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// Resolve Playwright the way `require` would, so a global install works too.
const { chromium } = createRequire(import.meta.url)('playwright');
const here = dirname(fileURLToPath(import.meta.url));
const script = readFileSync(join(here, '..', 'Skipper', 'Resources', 'youtube.js'), 'utf8');

const page_html = `<!doctype html><html><body>
  <div id="movie_player" class="html5-video-player">
    <video id="v"></video>
    <button class="ytp-skip-ad-button" id="skip">Skip</button>
  </div>
  <script>
    window.skipClicks = 0;
    document.getElementById('skip').addEventListener('click', () => {
      window.skipClicks++;
      // YouTube removes the class once the ad is over.
      document.getElementById('movie_player').classList.remove('ad-showing');
    });
  </script>
</body></html>`;

const errors = [];
const browser = await chromium.launch();
const page = await browser.newPage();
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
await page.addInitScript(script); // init scripts run on navigation, like a content script
await page.route('https://www.youtube.com/**', (route) =>
  route.fulfill({ contentType: 'text/html', body: page_html }));
await page.goto('https://www.youtube.com/watch?v=test');

const state = () => page.evaluate(() => {
  const v = document.getElementById('v');
  return { muted: v.muted, rate: v.playbackRate, clicks: window.skipClicks,
           ad: document.getElementById('movie_player').classList.contains('ad-showing') };
});

const before = await state();
if (before.muted || before.rate !== 1 || before.clicks !== 0) {
  throw new Error(`script touched the player with no ad showing: ${JSON.stringify(before)}`);
}

// Simulate an ad starting. The video has no source, so duration is NaN and the
// script should fall back to muting plus fast playback, then press Skip.
await page.evaluate(() => document.getElementById('movie_player').classList.add('ad-showing'));
await page.waitForFunction(() => window.skipClicks > 0, null, { timeout: 2000 });
const after = await state();
if (after.ad) throw new Error('skip button was clicked but ad class still present');
if (after.clicks < 1) throw new Error('skip button was not clicked');

// The class is gone, so the script must have restored the player.
await page.waitForFunction(() => !document.getElementById('v').muted, null, { timeout: 2000 });
const restored = await state();
if (restored.muted || restored.rate !== 1) {
  throw new Error(`player not restored after ad: ${JSON.stringify(restored)}`);
}

// A second ad later must be handled again (state machine resets).
await page.evaluate(() => { window.skipClicks = 0; document.getElementById('movie_player').classList.add('ad-showing'); });
await page.waitForFunction(() => window.skipClicks > 0, null, { timeout: 2000 });
await page.waitForFunction(() => !document.getElementById('v').muted, null, { timeout: 2000 });

// Replacing the player element (YouTube does this on some navigations) must be picked up.
await page.evaluate(() => {
  const old = document.getElementById('movie_player');
  const fresh = old.cloneNode(true);
  fresh.querySelector('#skip').addEventListener('click', () => {
    window.skipClicks++;
    fresh.classList.remove('ad-showing');
  });
  old.replaceWith(fresh);
  window.skipClicks = 0;
});
await page.waitForTimeout(1300); // the script re-finds the player once a second
await page.evaluate(() => document.getElementById('movie_player').classList.add('ad-showing'));
await page.waitForFunction(() => window.skipClicks > 0, null, { timeout: 2000 });

await browser.close();
if (errors.length) throw new Error(`console errors:\n${errors.join('\n')}`);
console.log('ok: skipper mutes, skips, restores, survives player replacement');
