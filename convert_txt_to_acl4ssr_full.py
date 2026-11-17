#!/usr/bin/env python3
"""Double-click entry point: convert all TXT node fragments in this folder."""

from __future__ import annotations

import os
import traceback
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_SUFFIX = ".acl4ssr-full.yaml"
INPUT_SUFFIXES = (".txt", ".yaml", ".yml")
ACL4SSR_REMOTE_TEMPLATE = (
    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/"
    "Clash/config/ACL4SSR_Online_Full.ini"
)


def converter():
    try:
        import fragment_to_mihomo_yaml as module
    except SystemExit as exc:
        raise RuntimeError(str(exc)) from exc
    return module


def output_path_for(source: Path) -> Path:
    return source.with_suffix(OUTPUT_SUFFIX)


def is_output_path(path: Path) -> bool:
    return path.name.endswith(OUTPUT_SUFFIX)


def find_sources() -> list[Path]:
    """Every convertible input in this folder: node .txt plus full .yaml profiles."""
    sources: list[Path] = []
    for path in sorted(SCRIPT_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in INPUT_SUFFIXES:
            continue
        if is_output_path(path):
            continue
        sources.append(path)
    return sources


def convert_one(source: Path, template_source: str) -> bool:
    module = converter()
    text = module.read_text(str(source))
    profile = module.load_profile(text)
    source_dns = profile.get("dns")
    names = module.proxy_names(profile)
    if not names:
        raise ValueError("no proxies found")
    if module.has_acl4ssr_rules(profile):
        print(f"SKIP: {source.name} 已套用 ACL4SSR 规则，跳过不重新生成")
        return False
    renames = module.dedupe_proxy_names(profile)
    profile = module.apply_acl4ssr_template(profile, module.read_template(template_source))
    profile = module.apply_defaults(profile)

    problems = module.validate_profile(profile)
    if problems:
        raise ValueError(
            "profile validation failed:\n  - " + "\n  - ".join(problems)
        )
    target = output_path_for(source)
    target.write_text(module.dump_profile(profile), encoding="utf-8", newline="\n")
    print(f"OK: {source.name} -> {target.name} ({len(names)} proxies)")
    if renames:
        print(f"     renamed {len(renames)} duplicate proxy name(s)")
    if isinstance(source_dns, dict):
        final_dns = profile.get("dns") or {}
        policy = final_dns.get("nameserver-policy")
        detail = f", {len(policy)} nameserver-policy entry(s)" if isinstance(policy, dict) else ""
        print(f"     kept dns: {final_dns.get('enhanced-mode', 'n/a')}{detail}")
    return True


def main() -> int:
    print("ACL4SSR full profile converter")
    print(f"Folder: {SCRIPT_DIR}")

    try:
        converter()
    except Exception as exc:
        print(f"\nERROR: {exc}")
        return 1

    template_source = ACL4SSR_REMOTE_TEMPLATE
    print(f"Remote template: {template_source}")
    sources = find_sources()

    if not sources:
        print(f"\nNo {' / '.join(INPUT_SUFFIXES)} files found in this folder.")
        return 0

    collisions: dict[str, Path] = {}
    for source in sources:
        target = str(output_path_for(source))
        if target in collisions:
            print(
                f"\nERROR: {collisions[target].name} and {source.name} "
                f"both map to {Path(target).name}"
            )
            return 1
        collisions[target] = source

    print(f"\nFound {len(sources)} input file(s).")
    failed = 0
    converted = 0
    skipped = 0
    for source in sources:
        try:
            if convert_one(source, template_source):
                converted += 1
            else:
                skipped += 1
        except Exception:
            failed += 1
            print(f"\nFAILED: {source.name}")
            print(traceback.format_exc().rstrip())

    print(f"\nDone. Converted: {converted}, Skipped: {skipped}, Failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    exit_code = main()
    if os.environ.get("ACL4SSR_SKIP_PY_PAUSE") != "1":
        try:
            input("\nPress Enter to exit...")
        except EOFError:
            pass
    raise SystemExit(exit_code)
