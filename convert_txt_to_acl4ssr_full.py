#!/usr/bin/env python3
"""Double-click entry point: convert all TXT node fragments in this folder."""

from __future__ import annotations

import os
import traceback
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_SUFFIX = ".acl4ssr-full.yaml"
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


def convert_one(source: Path, template_source: str) -> None:
    module = converter()
    text = module.read_text(str(source))
    profile = module.load_profile(text)
    names = module.proxy_names(profile)
    if not names:
        raise ValueError("no proxies found")

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
    txt_files = sorted(
        path
        for path in SCRIPT_DIR.glob("*.txt")
        if path.is_file() and output_path_for(path).name != path.name
    )

    if not txt_files:
        print("\nNo .txt files found in this folder.")
        return 0

    print(f"\nFound {len(txt_files)} txt file(s).")
    failed = 0
    for source in txt_files:
        try:
            convert_one(source, template_source)
        except Exception:
            failed += 1
            print(f"\nFAILED: {source.name}")
            print(traceback.format_exc().rstrip())

    print(f"\nDone. Success: {len(txt_files) - failed}, Failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    exit_code = main()
    if os.environ.get("ACL4SSR_SKIP_PY_PAUSE") != "1":
        try:
            input("\nPress Enter to exit...")
        except EOFError:
            pass
    raise SystemExit(exit_code)
