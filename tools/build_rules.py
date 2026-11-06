#!/usr/bin/env python3
"""Compile rules/*.txt into ContentBlocker/blockerList.json.

Safari compiles the JSON into a bytecode matcher once; nothing in this file
runs on the pages you visit. Keep the output small and the regexes inside
WebKit's supported subset (see rules/urls.txt).
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RULES = ROOT / "rules"
OUT = ROOT / "ContentBlocker" / "blockerList.json"

SCHEME = "^[a-z]+://"
ANY_SUBDOMAIN = r"([^/:]+\.)?"
DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")
RESOURCE_TYPES = {
    "document", "image", "style-sheet", "script", "font", "raw",
    "svg-document", "media", "popup", "ping", "websocket", "other",
}


def host_filter(domain: str) -> str:
    """Regex that matches domain and any subdomain, anchored at the scheme."""
    return SCHEME + ANY_SUBDOMAIN + domain.replace(".", r"\.") + "[/:]"


def strip_comment(line: str, markers=("#", "!")) -> str:
    s = line.strip()
    if not s or s[0] in markers:
        return ""
    return s


def parse_domains(path: pathlib.Path):
    rules = []
    section = None
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        if line.startswith("["):
            section = line.strip("[]")
            if section not in ("block", "block-third-party"):
                sys.exit(f"{path}:{n}: unknown section {section!r}")
            continue
        if section is None:
            sys.exit(f"{path}:{n}: domain before any [section]")
        if not DOMAIN_RE.match(line):
            sys.exit(f"{path}:{n}: not a bare lowercase domain: {line!r}")
        trigger = {"url-filter": host_filter(line)}
        if section == "block-third-party":
            trigger["load-type"] = ["third-party"]
        rules.append({"trigger": trigger, "action": {"type": "block"}})
    return rules


def parse_urls(path: pathlib.Path):
    blocks, exceptions = [], []
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = strip_comment(raw)
        if not line:
            continue
        action = "block"
        if line.startswith("@@"):
            action = "ignore-previous-rules"
            line = line[2:]
        parts = line.split()
        trigger = {"url-filter": parts[0]}
        for opt in parts[1:]:
            if opt == "case-sensitive":
                trigger["url-filter-is-case-sensitive"] = True
                continue
            key, _, value = opt.partition("=")
            values = value.split(",")
            if key == "load-type":
                if not set(values) <= {"first-party", "third-party"}:
                    sys.exit(f"{path}:{n}: bad load-type {value!r}")
            elif key == "resource-type":
                if not set(values) <= RESOURCE_TYPES:
                    sys.exit(f"{path}:{n}: bad resource-type {value!r}")
            elif key in ("if-domain", "unless-domain"):
                values = ["*" + v for v in values]
            else:
                sys.exit(f"{path}:{n}: unknown option {opt!r}")
            trigger[key] = values
        rule = {"trigger": trigger, "action": {"type": action}}
        (exceptions if action != "block" else blocks).append(rule)
    return blocks, exceptions


def parse_cosmetic(path: pathlib.Path, allow_has: bool):
    aliases = {}
    grouped = {}  # tuple(domains) -> [selectors]
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = strip_comment(raw, markers=("!",))
        if not line:
            continue
        if line.startswith("$") and "=" in line and "##" not in line:
            name, _, value = line.partition("=")
            aliases[name.strip()] = value.strip()
            continue
        domains, sep, selector = line.partition("##")
        if not sep or not selector:
            sys.exit(f"{path}:{n}: expected domains##selector")
        if ":has(" in selector and not allow_has:
            continue
        expanded = []
        for d in filter(None, domains.split(",")):
            d = d.strip()
            expanded.extend(aliases[d].split(",") if d.startswith("$") else [d])
        for d in expanded:
            if not DOMAIN_RE.match(d):
                sys.exit(f"{path}:{n}: bad domain {d!r}")
        grouped.setdefault(tuple(sorted(set(expanded))), []).append(selector.strip())

    rules = []
    for domains, selectors in grouped.items():
        trigger = {"url-filter": ".*"}
        if domains:
            trigger["if-domain"] = ["*" + d for d in domains]
        rules.append({
            "trigger": trigger,
            "action": {"type": "css-display-none", "selector": ", ".join(selectors)},
        })
    return rules


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    ap.add_argument("--no-has", action="store_true",
                    help="drop cosmetic rules that use :has() (Safari < 15.4)")
    args = ap.parse_args()

    domain_rules = parse_domains(RULES / "domains.txt")
    url_rules, exceptions = parse_urls(RULES / "urls.txt")
    cosmetic = parse_cosmetic(RULES / "cosmetic.txt", allow_has=not args.no_has)

    # WebKit applies rules in order; exceptions must follow what they exempt.
    rules = domain_rules + url_rules + cosmetic + exceptions

    args.out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rules, separators=(",", ":"), ensure_ascii=True) + "\n"
    args.out.write_text(text)

    selectors = sum(len(r["action"]["selector"].split(", ")) for r in cosmetic)
    print(f"{args.out.relative_to(ROOT)}: {len(rules)} rules, {len(text):,} bytes")
    print(f"  {len(domain_rules)} host blocks, {len(url_rules)} url blocks, "
          f"{len(cosmetic)} cosmetic rules ({selectors} selectors), "
          f"{len(exceptions)} exceptions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
