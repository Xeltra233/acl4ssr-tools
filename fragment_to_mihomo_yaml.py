#!/usr/bin/env python3
"""Convert bare Clash/Mihomo proxy fragments into a valid YAML profile."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import re
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import urlparse

try:
    import yaml
except ImportError as exc:  # pragma: no cover - depends on local env
    raise SystemExit("PyYAML is required. Install it with: pip install PyYAML") from exc

if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z0-9_.-][A-Za-z0-9_. -]*:\s*(?:#.*)?$")
PREFERRED_KEY_ORDER = [
    "mixed-port",
    "port",
    "socks-port",
    "redir-port",
    "tproxy-port",
    "allow-lan",
    "mode",
    "log-level",
    "external-controller",
    "secret",
    "dns",
    "proxies",
    "proxy-groups",
    "rule-providers",
    "rules",
]
BUILTIN_PROXY_NAMES = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE"}
FLAG_RE = re.compile("[\U0001F1E6-\U0001F1FF]{2}")


@dataclass
class CustomGroup:
    name: str
    type: str
    selectors: list[str]
    url: str | None = None
    interval: int | None = None
    tolerance: int | None = None


@dataclass
class Template:
    groups: list[CustomGroup]
    rulesets: list[tuple[str, str]]


class IndentDumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    source = Path(path)
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return source.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return source.read_text(encoding="utf-8-sig")


def write_text(path: str, text: str) -> None:
    if path == "-":
        sys.stdout.write(text)
        return
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def read_text_or_url(source: str) -> str:
    if is_url(source):
        filename = Path(urlparse(source).path).name
        local_candidate = Path(__file__).resolve().parent / filename
        if local_candidate.is_file():
            try:
                return read_text(str(local_candidate))
            except Exception:
                pass

        urls = [source]
        if "raw.githubusercontent.com" in source:
            cdn_url = source.replace("raw.githubusercontent.com", "fastly.jsdelivr.net/gh").replace("/master/", "@master/").replace("/main/", "@main/")
            urls.append(cdn_url)
            urls.append(f"https://ghproxy.net/{source}")

        last_err = None
        for u in urls:
            try:
                request = Request(u, headers={"User-Agent": "acl4ssr-tools/1.0"})
                with urlopen(request, timeout=10) as response:
                    content = response.read().decode("utf-8-sig")
                    try:
                        local_candidate.write_text(content, encoding="utf-8-sig")
                    except Exception:
                        pass
                    return content
            except Exception as e:
                last_err = e
                continue
        if local_candidate.is_file():
            return read_text(str(local_candidate))
        if last_err:
            raise last_err
    return read_text(source)


def read_template(path: str) -> Template:
    groups: list[CustomGroup] = []
    rulesets: list[tuple[str, str]] = []

    for raw_line in read_text_or_url(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if line.startswith("custom_proxy_group="):
            groups.append(parse_custom_group(line.split("=", 1)[1]))
        elif line.startswith("ruleset="):
            policy, rule = line.split("=", 1)[1].split(",", 1)
            rulesets.append((policy.strip(), rule.strip()))

    if not groups:
        raise SystemExit(f"No custom_proxy_group entries found in template: {path}")
    return Template(groups=groups, rulesets=rulesets)


def parse_custom_group(spec: str) -> CustomGroup:
    parts = spec.split("`")
    if len(parts) < 3:
        raise SystemExit(f"Invalid custom_proxy_group entry: {spec}")

    name, group_type = parts[0], parts[1]
    selectors: list[str] = []
    url: str | None = None
    interval: int | None = None
    tolerance: int | None = None

    for token in parts[2:]:
        token = token.strip()
        if not token:
            continue
        if token.startswith("http://") or token.startswith("https://"):
            url = token
            continue
        if re.fullmatch(r"\d+(?:,\d*){0,3}", token):
            values = token.split(",")
            interval = int(values[0])
            numeric_tail = [int(value) for value in values[1:] if value.isdigit()]
            if numeric_tail:
                tolerance = numeric_tail[-1]
            continue
        selectors.append(token)

    return CustomGroup(
        name=name,
        type=group_type,
        selectors=selectors,
        url=url,
        interval=interval,
        tolerance=tolerance,
    )


def has_top_level_key(text: str, key: str) -> bool:
    return re.search(rf"(?m)^{re.escape(key)}\s*:", text) is not None


def first_content_line(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return index
    return None


def is_top_level_section(line: str) -> bool:
    return line == line.lstrip() and TOP_LEVEL_KEY_RE.match(line.strip()) is not None


def wrap_bare_proxy_list(text: str) -> str:
    if has_top_level_key(text, "proxies"):
        return text

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = first_content_line(lines)
    if start is None or not lines[start].lstrip().startswith("- "):
        return text

    prefix = lines[:start]
    proxy_lines: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if is_top_level_section(line):
            break
        if line.strip():
            proxy_lines.append("  " + line)
        else:
            proxy_lines.append("")
        index += 1

    wrapped = [*prefix, "proxies:", *proxy_lines, *lines[index:]]
    return "\n".join(wrapped)


def load_profile(text: str) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(text)
        if isinstance(loaded, dict):
            return loaded
        if isinstance(loaded, list):
            return {"proxies": loaded}
    except Exception:
        pass

    normalized = wrap_bare_proxy_list(text)
    try:
        loaded = yaml.safe_load(normalized) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f"Input is not valid YAML after normalization: {exc}") from exc

    if isinstance(loaded, list):
        return {"proxies": loaded}
    if not isinstance(loaded, dict):
        raise SystemExit("Input must be a YAML mapping or a proxy list.")
    return loaded


def proxy_names(profile: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for proxy in profile.get("proxies") or []:
        if isinstance(proxy, dict) and proxy.get("name") is not None:
            names.append(str(proxy["name"]))
    return names


def dedupe_proxy_names(profile: dict[str, Any]) -> list[tuple[str, str]]:
    """Rename duplicated proxies so every proxy name is unique.

    Renaming keeps the original name as a prefix (``name (2)``) so that the
    ACL4SSR group filters still match the node. Returns the applied
    ``(old_name, new_name)`` pairs.
    """
    proxies = [
        proxy
        for proxy in profile.get("proxies") or []
        if isinstance(proxy, dict) and proxy.get("name") is not None
    ]
    taken = {str(proxy["name"]) for proxy in proxies}
    used: set[str] = set()
    renames: list[tuple[str, str]] = []

    for proxy in proxies:
        original = str(proxy["name"])
        name = original
        index = 2
        while name in used:
            candidate = f"{original} ({index})"
            index += 1
            if candidate in taken or candidate in used:
                continue
            name = candidate
        used.add(name)
        if name != original:
            proxy["name"] = name
            renames.append((original, name))

    for original, name in renames:
        print(
            f"warning: duplicate proxy name renamed: {original} -> {name}",
            file=sys.stderr,
        )
    return renames


def infer_flag(name: str) -> str | None:
    lowered = name.lower()
    checks = [
        ("🇭🇰", ("香港", "hong kong", " hk")),
        ("🇹🇼", ("台湾", "台灣", "臺灣", "taiwan", " tw")),
        ("🇲🇴", ("澳门", "澳門", "macao", "macau", " mo")),
        ("🇨🇳", ("中国", "中國", "china", " cn")),
        ("🇸🇬", ("新加坡", "狮城", "獅城", "singapore", " sg")),
        ("🇯🇵", ("日本", "东京", "東京", "大阪", "japan", " jp")),
        (
            "🇺🇸",
            (
                "美国",
                "美國",
                "洛杉矶",
                "洛杉磯",
                "西雅图",
                "西雅圖",
                "纽约",
                "紐約",
                "united states",
                " usa",
                " us",
            ),
        ),
    ]
    for flag, keywords in checks:
        if any(keyword in lowered for keyword in keywords):
            return flag
    return None


def regex_match_name(name: str) -> str:
    flag = infer_flag(name)
    if flag:
        return f"{flag} {FLAG_RE.sub('', name).strip()}"
    return name


def selector_matches(selector: str, name: str) -> bool:
    if selector == "^":
        return True
    try:
        return re.search(selector, regex_match_name(name)) is not None
    except re.error as exc:
        print(f"warning: invalid group regex skipped: {selector} ({exc})", file=sys.stderr)
        return False


def expand_group_selectors(group: CustomGroup, names: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()

    def append(value: str) -> None:
        if value and value not in seen:
            expanded.append(value)
            seen.add(value)

    for selector in group.selectors:
        if selector.startswith("[]"):
            append(selector[2:])
        else:
            for name in names:
                if selector_matches(selector, name):
                    append(name)
    return expanded


def filter_group_proxies(
    proxies: list[str], proxy_name_set: set[str], kept_group_names: set[str]
) -> list[str]:
    return [
        proxy
        for proxy in proxies
        if proxy in proxy_name_set or proxy in BUILTIN_PROXY_NAMES or proxy in kept_group_names
    ]


def build_acl4ssr_proxy_groups(groups: list[CustomGroup], names: list[str]) -> list[dict[str, Any]]:
    proxy_name_set = set(names)
    drafted: list[dict[str, Any]] = []
    for group in groups:
        item: dict[str, Any] = {
            "name": group.name,
            "type": group.type,
            "proxies": expand_group_selectors(group, names),
        }
        if group.url:
            item["url"] = group.url
        if group.interval is not None:
            item["interval"] = group.interval
        if group.tolerance is not None:
            item["tolerance"] = group.tolerance
        drafted.append(item)

    kept = {str(group["name"]) for group in drafted}
    while True:
        next_kept = {
            str(group["name"])
            for group in drafted
            if filter_group_proxies(group["proxies"], proxy_name_set, kept)
        }
        if next_kept == kept:
            break
        kept = next_kept

    result: list[dict[str, Any]] = []
    for group in drafted:
        if group["name"] not in kept:
            continue
        item = dict(group)
        item["proxies"] = filter_group_proxies(item["proxies"], proxy_name_set, kept)
        if item["proxies"]:
            result.append(item)
    return result


def provider_name_for(url: str, used: set[str]) -> str:
    parsed = urlparse(url)
    basename = Path(parsed.path).name or "ruleset"
    stem = Path(basename).stem or "ruleset"
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "ruleset"
    candidate = name
    index = 2
    while candidate in used:
        candidate = f"{name}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def build_acl4ssr_rules(
    rulesets: list[tuple[str, str]]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    providers: dict[str, dict[str, Any]] = {}
    rules: list[str] = []
    used_provider_names: set[str] = set()

    for policy, target in rulesets:
        if target.startswith("[]"):
            rule_parts = [part.strip() for part in target[2:].split(",") if part.strip()]
            if not rule_parts:
                continue
            rule_type = rule_parts[0].upper()
            if rule_type in {"FINAL", "MATCH"}:
                rules.append(f"MATCH,{policy}")
            else:
                suffix = rule_parts[1:]
                rules.append(",".join([rule_type, *suffix, policy]))
            continue

        provider_name = provider_name_for(target, used_provider_names)
        suffix = Path(urlparse(target).path).suffix.lower()
        providers[provider_name] = {
            "type": "http",
            "behavior": "classical",
            "format": "yaml" if suffix in {".yaml", ".yml"} else "text",
            "url": target,
            "path": f"./ruleset/{provider_name}{suffix or '.list'}",
            "interval": 86400,
        }
        rules.append(f"RULE-SET,{provider_name},{policy}")

    return providers, rules


def apply_acl4ssr_template(profile: dict[str, Any], template: Template) -> dict[str, Any]:
    names = proxy_names(profile)
    if not names:
        raise SystemExit("No proxies found in input.")

    profile = dict(profile)
    profile["proxy-groups"] = build_acl4ssr_proxy_groups(template.groups, names)
    providers, rules = build_acl4ssr_rules(template.rulesets)
    if providers:
        profile["rule-providers"] = providers
    elif "rule-providers" in profile:
        del profile["rule-providers"]
    profile["rules"] = rules or [f"MATCH,{choose_match_target(profile)}"]
    return profile


def choose_match_target(profile: dict[str, Any]) -> str:
    groups = profile.get("proxy-groups") or []
    group_names = [
        str(group["name"])
        for group in groups
        if isinstance(group, dict) and group.get("name") is not None
    ]
    for preferred in ("Final", "MATCH", "Proxy", "MESL"):
        for group_name in group_names:
            if group_name.lower() == preferred.lower():
                return group_name
    if group_names:
        return group_names[0]
    names = proxy_names(profile)
    return names[0] if names else "DIRECT"


def apply_defaults(profile: dict[str, Any]) -> dict[str, Any]:
    profile = dict(profile)
    profile.setdefault("mixed-port", 7890)
    profile.setdefault("allow-lan", True)
    profile.setdefault("mode", "rule")
    profile.setdefault("log-level", "info")

    names = proxy_names(profile)
    if names and not profile.get("proxy-groups"):
        profile["proxy-groups"] = [
            {
                "name": "Proxy",
                "type": "select",
                "proxies": ["Auto", *names, "DIRECT"],
            },
            {
                "name": "Auto",
                "type": "url-test",
                "proxies": names,
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
            },
        ]

    if not profile.get("rules"):
        profile["rules"] = [f"MATCH,{choose_match_target(profile)}"]

    return profile

def validate_profile(profile: dict[str, Any]) -> list[str]:
    """Return structural problems that would make Mihomo reject the profile."""
    problems: list[str] = []
    names = proxy_names(profile)
    duplicated = sorted(
        name for name, count in Counter(names).items() if count > 1
    )
    for name in duplicated:
        problems.append(f"duplicate proxy name: {name}")

    groups = [
        group
        for group in profile.get("proxy-groups") or []
        if isinstance(group, dict) and group.get("name") is not None
    ]
    group_names = [str(group["name"]) for group in groups]
    group_name_set = set(group_names)

    for name in sorted(set(names) & group_name_set):
        problems.append(f"proxy name collides with proxy group name: {name}")

    proxy_name_set = set(names)
    known_targets = proxy_name_set | group_name_set | BUILTIN_PROXY_NAMES
    for group in groups:
        members = [str(member) for member in group.get("proxies") or []]
        label = group["name"]
        if not members:
            problems.append(f"proxy group has no members: {label}")
        for member, count in Counter(members).items():
            if count > 1:
                problems.append(f"duplicate member in group {label}: {member}")
            if member == label:
                problems.append(f"proxy group references itself: {label}")
            elif member not in known_targets:
                problems.append(f"unknown target in group {label}: {member}")

    providers = profile.get("rule-providers") or {}
    for rule in profile.get("rules") or []:
        parts = [part.strip() for part in str(rule).split(",")]
        if not parts or not parts[0]:
            continue
        if parts[0].upper() == "RULE-SET":
            if len(parts) < 3:
                problems.append(f"malformed RULE-SET rule: {rule}")
                continue
            if parts[1] not in providers:
                problems.append(f"rule references missing rule-provider: {rule}")
            if parts[2] not in known_targets:
                problems.append(f"rule references missing proxy group: {rule}")
        elif parts[-1] not in known_targets:
            problems.append(f"rule references missing proxy group: {rule}")

    return problems

def order_keys(profile: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in PREFERRED_KEY_ORDER:
        if key in profile:
            ordered[key] = profile[key]
    for key, value in profile.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def dump_profile(profile: dict[str, Any]) -> str:
    return yaml.dump(
        order_keys(profile),
        Dumper=IndentDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=4096,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a bare proxy fragment into a Clash/Mihomo YAML profile."
    )
    parser.add_argument("input", help="Input file path, or '-' for stdin.")
    parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output YAML path, or '-' for stdout. Defaults to stdout.",
    )
    parser.add_argument(
        "--no-defaults",
        action="store_true",
        help="Only normalize YAML; do not add mixed-port, proxy-groups, or rules.",
    )
    parser.add_argument(
        "--acl4ssr-template",
        help=(
            "Path to an ACL4SSR subconverter ini, for example "
            "ACL4SSR/ACL4SSR_Online_Full_Mannix.ini. Replaces proxy-groups, "
            "rule-providers, and rules with template-derived Mihomo YAML."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = load_profile(read_text(args.input))
    dedupe_proxy_names(profile)
    if args.acl4ssr_template:
        profile = apply_acl4ssr_template(profile, read_template(args.acl4ssr_template))
    if not args.no_defaults:
        profile = apply_defaults(profile)
    problems = validate_profile(profile)
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if problems:
        return 1
    write_text(args.output, dump_profile(profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
