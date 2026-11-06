#!/usr/bin/env python3
"""Check ContentBlocker/blockerList.json before it ships.

1. Schema: only keys and values Safari's content-blocker format accepts.
2. Regex subset: nothing WebKit's URL-filter compiler rejects.
3. Behaviour: known ad URLs are blocked, known-good URLs are not, and every
   host rule matches the host and its subdomains but nothing that merely
   contains the name.
"""
import json
import pathlib
import re
import sys
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIST = ROOT / "ContentBlocker" / "blockerList.json"

ACTIONS = {"block", "block-cookies", "css-display-none", "ignore-previous-rules", "make-https"}
TRIGGER_KEYS = {
    "url-filter", "url-filter-is-case-sensitive", "if-domain", "unless-domain",
    "resource-type", "load-type", "if-top-url", "unless-top-url", "load-context",
}
UNSUPPORTED_REGEX = [
    (r"\|", "alternation"),
    (r"\{", "counted quantifier"),
    (r"\(\?", "lookaround or non-capturing group"),
    (r"\\[dDwWsSbB]", "built-in character class"),
    (r"\\[1-9]", "backreference"),
]

failures = []


def fail(msg):
    failures.append(msg)


def registrable(host):
    """Good-enough eTLD+1 for tests: handles co.uk-style second levels."""
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "ac", "gov", "edu"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def domain_matches(host, patterns):
    for p in patterns:
        if p.startswith("*"):
            base = p[1:]
            if host == base or host.endswith("." + base):
                return True
        elif host == p:
            return True
    return False


class Matcher:
    def __init__(self, rules):
        self.rules = []
        for r in rules:
            t = r["trigger"]
            flags = 0 if t.get("url-filter-is-case-sensitive") else re.IGNORECASE
            self.rules.append((re.compile(t["url-filter"], flags), t, r["action"]["type"]))

    def blocked(self, url, top=None, resource="other"):
        host = urlsplit(url).hostname
        top_host = urlsplit(top).hostname if top else host
        party = "third-party" if registrable(host) != registrable(top_host) else "first-party"
        verdict = False
        for rx, t, action in self.rules:
            if action not in ("block", "ignore-previous-rules"):
                continue
            if not rx.search(url):
                continue
            if "load-type" in t and party not in t["load-type"]:
                continue
            if "resource-type" in t and resource not in t["resource-type"]:
                continue
            if "if-domain" in t and not domain_matches(top_host, t["if-domain"]):
                continue
            if "unless-domain" in t and domain_matches(top_host, t["unless-domain"]):
                continue
            verdict = action == "block"
        return verdict


def check_schema(rules):
    seen_cosmetic = False
    for i, r in enumerate(rules):
        if set(r) != {"trigger", "action"}:
            fail(f"rule {i}: keys must be trigger+action, got {sorted(r)}")
            continue
        t, a = r["trigger"], r["action"]
        extra = set(t) - TRIGGER_KEYS
        if extra:
            fail(f"rule {i}: unknown trigger keys {sorted(extra)}")
        if "url-filter" not in t:
            fail(f"rule {i}: missing url-filter")
        if a.get("type") not in ACTIONS:
            fail(f"rule {i}: bad action type {a.get('type')!r}")
        if a.get("type") == "css-display-none":
            seen_cosmetic = True
            sel = a.get("selector", "")
            if not sel or any(c in sel for c in "{};"):
                fail(f"rule {i}: bad selector {sel!r}")
            for open_, close in ("()", "[]"):
                if sel.count(open_) != sel.count(close):
                    fail(f"rule {i}: unbalanced {open_}{close} in selector")
            if sel.count('"') % 2:
                fail(f"rule {i}: unbalanced quotes in selector")
        elif "selector" in a:
            fail(f"rule {i}: selector on non-cosmetic action")
        elif a["type"] == "block" and seen_cosmetic:
            fail(f"rule {i}: block rule after cosmetic rules (keep blocks first)")
        for key in ("if-domain", "unless-domain"):
            for d in t.get(key, []):
                if d != d.lower() or not re.fullmatch(r"\*?[a-z0-9.-]+", d):
                    fail(f"rule {i}: bad {key} entry {d!r}")
        if "if-domain" in t and "unless-domain" in t:
            fail(f"rule {i}: if-domain and unless-domain are mutually exclusive")
        for v in t.get("load-type", []):
            if v not in ("first-party", "third-party"):
                fail(f"rule {i}: bad load-type {v!r}")
        for pattern, why in UNSUPPORTED_REGEX:
            if re.search(pattern, t.get("url-filter", "")):
                fail(f"rule {i}: url-filter uses {why}: {t['url-filter']!r}")
        try:
            re.compile(t.get("url-filter", ""))
        except re.error as e:
            fail(f"rule {i}: url-filter does not compile: {e}")


def check_hosts(m):
    """Every host in rules/domains.txt: host and subdomains blocked, lookalikes not."""
    for raw in (ROOT / "rules" / "domains.txt").read_text().splitlines():
        line = raw.strip()
        if not line or line[0] in "#[":
            continue
        d = line
        top = "https://unrelated-site.example/"
        for url in (f"https://{d}/", f"https://a.b.{d}/x?y=1", f"http://{d}:8080/", f"wss://{d}/socket"):
            if not m.blocked(url, top):
                fail(f"host rule miss: {url}")
        for url in (f"https://not{d}/", f"https://{d}.evil.example/", f"https://x.com/?u={d}/"):
            if m.blocked(url, top):
                fail(f"host rule over-match: {url}")


EXAMPLE = "https://www.example-news.com/story"
BLOCKED = [
    # Google ad stack
    ("https://googleads.g.doubleclick.net/pagead/id", "https://www.youtube.com/", "other"),
    ("https://securepubads.g.doubleclick.net/tag/js/gpt.js", EXAMPLE, "script"),
    ("https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js", EXAMPLE, "script"),
    ("https://adservice.google.com/adsid/integrator.js", EXAMPLE, "script"),
    ("https://adservice.google.co.uk/adsid/integrator.js", EXAMPLE, "script"),
    ("https://www.google.com/pagead/1p-user-list/123/?x", "https://www.google.com/", "image"),
    ("https://www.google.com/ads/ga-audiences?x", "https://www.google.com/", "image"),
    ("https://www.googletagmanager.com/gtag/js?id=G-XXXX", EXAMPLE, "script"),
    # YouTube first-party endpoints
    ("https://www.youtube.com/pagead/interaction/?ai=x", "https://www.youtube.com/", "other"),
    ("https://www.youtube.com/ptracking?html5=1", "https://www.youtube.com/", "image"),
    ("https://www.youtube.com/api/stats/ads?ver=2", "https://www.youtube.com/", "other"),
    ("https://www.youtube.com/youtubei/v1/log_event?alt=json", "https://www.youtube.com/", "other"),
    ("https://music.youtube.com/api/stats/qoe?x", "https://music.youtube.com/", "other"),
    ("https://static.doubleclick.net/instream/ad_status.js", "https://www.youtube.com/", "script"),
    # Music
    ("https://spclient.wg.spotify.com/ad-logic/v1/ads", "https://open.spotify.com/", "other"),
    ("https://spclient.wg.spotify.com/ads/v2/ads", "https://open.spotify.com/", "other"),
    ("https://adeventtracker.spotify.com/event", "https://open.spotify.com/", "other"),
    ("https://api-v2.soundcloud.com/promoted/tracks?x", "https://soundcloud.com/", "other"),
    ("https://cdn.adswizz.com/adswizz/js/SynchroClient2.js", "https://www.iheart.com/", "script"),
    ("https://ads.pandora.com/x", "https://www.pandora.com/", "other"),
    # Streaming video
    ("https://1234.v.fwmrm.net/ad/g/1?x", "https://www.hulu.com/", "other"),
    ("https://ads-v-darwin.hulustream.com/x", "https://www.hulu.com/", "other"),
    ("https://edge.ads.twitch.tv/x", "https://www.twitch.tv/", "other"),
    ("https://spade.twitch.tv/track", "https://www.twitch.tv/", "other"),
    ("https://s.innovid.com/x", "https://www.peacocktv.com/", "script"),
    # Social and forums
    ("https://ads.reddit.com/x", "https://www.reddit.com/", "other"),
    ("https://alb.reddit.com/rp.gif", "https://www.reddit.com/", "image"),
    ("https://www.redditstatic.com/ads/pixel.js", "https://www.reddit.com/", "script"),
    ("https://px.ads.linkedin.com/collect?x", "https://www.linkedin.com/", "image"),
    ("https://www.linkedin.com/li/track", "https://www.linkedin.com/", "other"),
    ("https://snap.licdn.com/li.lms-analytics/insight.min.js", EXAMPLE, "script"),
    ("https://connect.facebook.net/en_US/fbevents.js", EXAMPLE, "script"),
    ("https://www.facebook.com/tr?id=1&ev=PageView", EXAMPLE, "image"),
    ("https://analytics.tiktok.com/i18n/pixel/events.js", EXAMPLE, "script"),
    ("https://bat.bing.com/bat.js", EXAMPLE, "script"),
    ("https://fls-na.amazon.com/1/batch/1/OP/x", "https://www.amazon.com/", "image"),
    ("https://c.amazon-adsystem.com/aax2/apstag.js", EXAMPLE, "script"),
    ("https://static.hotjar.com/c/hotjar-1.js", EXAMPLE, "script"),
    ("https://cdn.taboola.com/libtrc/x/loader.js", EXAMPLE, "script"),
    ("https://widgets.outbrain.com/outbrain.js", EXAMPLE, "script"),
    ("https://sb.scorecardresearch.com/beacon.js", EXAMPLE, "script"),
    ("https://stats.wp.com/e-202545.js", "https://someblog.wordpress.com/", "script"),
    # Generic paths, third-party
    ("https://cdn.somead-cdn.net/pagead/show_ads.js", EXAMPLE, "script"),
    ("https://cdn.somead-cdn.net/adserver/x.js", EXAMPLE, "script"),
    ("https://cdn.somead-cdn.net/openx/x.js", EXAMPLE, "script"),
    ("https://www.example-news.com/js/prebid8.2.0.js", EXAMPLE, "script"),
    ("https://www.example-news.com/js/prebid.js?v=3", EXAMPLE, "script"),
]
ALLOWED = [
    # YouTube playback must keep working
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/", "document"),
    ("https://www.youtube.com/youtubei/v1/player?key=x", "https://www.youtube.com/", "other"),
    ("https://www.youtube.com/youtubei/v1/next?key=x", "https://www.youtube.com/", "other"),
    ("https://www.youtube.com/s/player/abc/player_ias.vflset/en_US/base.js", "https://www.youtube.com/", "script"),
    ("https://rr3---sn-x.googlevideo.com/videoplayback?expire=1&ei=x", "https://www.youtube.com/", "media"),
    ("https://i.ytimg.com/vi/x/hqdefault.jpg", "https://www.youtube.com/", "image"),
    ("https://www.youtube.com/api/timedtext?v=x", "https://www.youtube.com/", "other"),
    ("https://www.youtube.com/api/stats/watchtime?x", "https://www.youtube.com/", "other"),
    ("https://music.youtube.com/", "https://music.youtube.com/", "document"),
    # Google products
    ("https://www.google.com/search?q=safari+content+blocker", "https://www.google.com/", "document"),
    ("https://www.google.com/complete/search?q=x", "https://www.google.com/", "other"),
    ("https://www.google.com/adsense/new/u/0/", "https://www.google.com/", "document"),
    ("https://ads.google.com/home/", "https://ads.google.com/", "document"),
    ("https://www.gstatic.com/og/_/js/k=x.js", "https://www.google.com/", "script"),
    ("https://apis.google.com/js/platform.js", EXAMPLE, "script"),
    ("https://fonts.googleapis.com/css2?family=Inter", EXAMPLE, "style-sheet"),
    ("https://accounts.google.com/o/oauth2/v2/auth", EXAMPLE, "document"),
    ("https://mail.google.com/mail/u/0/", "https://mail.google.com/", "document"),
    ("https://www.googletagmanager.com/gtm.js?id=GTM-X", EXAMPLE, "script"),
    ("https://www.google.com/recaptcha/api.js", EXAMPLE, "script"),
    # Music
    ("https://open.spotify.com/track/x", "https://open.spotify.com/", "document"),
    ("https://spclient.wg.spotify.com/metadata/4/track/x", "https://open.spotify.com/", "other"),
    ("https://api.spotify.com/v1/me/player", "https://open.spotify.com/", "other"),
    ("https://audio-fa.scdn.co/audio/x", "https://open.spotify.com/", "media"),
    ("https://api-v2.soundcloud.com/tracks/1/streams", "https://soundcloud.com/", "other"),
    # Streaming video
    ("https://www.twitch.tv/somechannel", "https://www.twitch.tv/", "document"),
    ("https://gql.twitch.tv/gql", "https://www.twitch.tv/", "other"),
    ("https://usher.ttvnw.net/api/channel/hls/x.m3u8", "https://www.twitch.tv/", "other"),
    ("https://video-weaver.sfo01.hls.ttvnw.net/v1/playlist/x.m3u8", "https://www.twitch.tv/", "other"),
    ("https://static.twitchcdn.net/assets/x.js", "https://www.twitch.tv/", "script"),
    ("https://www.hulu.com/watch/x", "https://www.hulu.com/", "document"),
    ("https://manifest.hulustream.com/x", "https://www.hulu.com/", "other"),
    ("https://www.netflix.com/watch/1", "https://www.netflix.com/", "document"),
    # Social and forums
    ("https://www.reddit.com/r/programming/", "https://www.reddit.com/", "document"),
    ("https://gql.reddit.com/", "https://www.reddit.com/", "other"),
    ("https://www.redditstatic.com/shreddit/en-US/x.js", "https://www.reddit.com/", "script"),
    ("https://oauth.reddit.com/api/v1/me", "https://www.reddit.com/", "other"),
    ("https://i.redd.it/x.png", "https://www.reddit.com/", "image"),
    ("https://www.linkedin.com/feed/", "https://www.linkedin.com/", "document"),
    ("https://static.licdn.com/sc/h/x.js", "https://www.linkedin.com/", "script"),
    ("https://www.linkedin.com/voyager/api/feed", "https://www.linkedin.com/", "other"),
    ("https://www.facebook.com/", "https://www.facebook.com/", "document"),
    ("https://www.facebook.com/translations/x", "https://www.facebook.com/", "document"),
    ("https://connect.facebook.net/en_US/sdk.js", EXAMPLE, "script"),
    ("https://stackoverflow.com/questions/1", "https://stackoverflow.com/", "document"),
    ("https://cdn.sstatic.net/Js/x.js", "https://stackoverflow.com/", "script"),
    ("https://duckduckgo.com/?q=x", "https://duckduckgo.com/", "document"),
    ("https://www.bing.com/search?q=x", "https://www.bing.com/", "document"),
    ("https://www.amazon.com/dp/B000", "https://www.amazon.com/", "document"),
    ("https://images-na.ssl-images-amazon.com/images/I/x.jpg", "https://www.amazon.com/", "image"),
    ("https://completion.amazon.com/api/2017/suggestions", "https://www.amazon.com/", "other"),
    # Lookalikes and ordinary paths
    ("https://notdoubleclick.net/x", EXAMPLE, "script"),
    ("https://doubleclick.net.example.com/x", EXAMPLE, "script"),
    ("https://www.example-news.com/uploads/photo.png", EXAMPLE, "image"),
    ("https://www.example-news.com/wp-content/plugins/advanced-forms/x.js", EXAMPLE, "script"),
    ("https://www.example-news.com/prebid-docs/index.html", EXAMPLE, "document"),
    ("https://www.example-news.com/prebid.json", EXAMPLE, "other"),
    ("https://www.example-news.com/openxchange/", EXAMPLE, "document"),
    ("https://www.example-news.com/pagead/first-party-path", EXAMPLE, "script"),
    ("https://cdn.jsdelivr.net/npm/x", EXAMPLE, "script"),
    ("https://s0.wp.com/wp-content/x.css", "https://someblog.wordpress.com/", "style-sheet"),
    ("https://www.taboola.com/", "https://www.taboola.com/", "document"),
    ("https://www.hotjar.com/pricing/", "https://www.hotjar.com/", "document"),
]


def check_behaviour(m):
    for url, top, resource in BLOCKED:
        if not m.blocked(url, top, resource):
            fail(f"should block: {url} (on {top})")
    for url, top, resource in ALLOWED:
        if m.blocked(url, top, resource):
            fail(f"must NOT block: {url} (on {top})")


def main():
    rules = json.loads(LIST.read_text())
    check_schema(rules)
    if failures:
        for f in failures:
            print("FAIL", f)
        return 1
    m = Matcher(rules)
    check_hosts(m)
    check_behaviour(m)
    if failures:
        for f in failures:
            print("FAIL", f)
        print(f"\n{len(failures)} failure(s)")
        return 1
    print(f"ok: {len(rules)} rules, {len(BLOCKED)} blocked cases, {len(ALLOWED)} allowed cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
