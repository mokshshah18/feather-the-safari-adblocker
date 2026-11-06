// Feather YouTube Skipper
//
// Server-stitched video ads cannot be blocked by URL, so this script makes
// them end instantly instead. It watches the player's class list (YouTube adds
// `ad-showing` during an ad), mutes, seeks to the end, and presses Skip.
// When no ad is showing it does nothing except one cheap check per second
// to see whether the player element has been replaced.
(() => {
  'use strict';

  const PLAYER = '.html5-video-player';
  const AD_CLASSES = ['ad-showing', 'ad-interrupting'];
  const SKIP_BUTTONS = [
    '.ytp-skip-ad-button',
    '.ytp-ad-skip-button',
    '.ytp-ad-skip-button-modern',
    '.ytp-ad-skip-button-slot button',
    '.ytp-ad-overlay-close-button',
  ].join(', ');
  const AD_RATE = 16; // used only when the ad's duration is not yet known
  const RETRY_MS = 250; // how often to retry while an ad is on screen

  let player = null;
  let observer = null;
  let inAd = false;
  let saved = null; // { muted, rate } to restore after the ad
  let timer = 0;

  const isAd = () => AD_CLASSES.some((c) => player.classList.contains(c));

  function skip() {
    const video = player.querySelector('video');
    if (video) {
      if (saved === null) saved = { muted: video.muted, rate: video.playbackRate };
      video.muted = true;
      if (Number.isFinite(video.duration) && video.duration > 0) {
        video.currentTime = video.duration;
      } else {
        video.playbackRate = AD_RATE;
      }
    }
    for (const button of player.querySelectorAll(SKIP_BUTTONS)) button.click();
  }

  function restore() {
    const video = player.querySelector('video');
    if (video && saved) {
      video.muted = saved.muted;
      video.playbackRate = saved.rate;
    }
    saved = null;
  }

  function onClassChange() {
    const ad = isAd();
    if (ad && !inAd) {
      inAd = true;
      skip();
      timer = setInterval(skip, RETRY_MS);
    } else if (!ad && inAd) {
      inAd = false;
      clearInterval(timer);
      timer = 0;
      restore();
    }
  }

  function attach(element) {
    if (observer) observer.disconnect();
    player = element;
    observer = new MutationObserver(onClassChange);
    observer.observe(player, { attributes: true, attributeFilter: ['class'] });
    onClassChange();
  }

  // YouTube is a single-page app; the player usually survives navigation.
  // Re-find it only if it is missing or was detached from the document.
  function find() {
    if (player && player.isConnected) return;
    const element = document.querySelector(PLAYER);
    if (element) attach(element);
  }

  find();
  setInterval(find, 1000);
})();
