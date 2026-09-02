#!/usr/bin/env python3
"""detect.py の回帰テスト。ルール表を編集したら必ず実行する。

    python3 .claude/skills/natural-japanese/scripts/selftest.py

fixtures/unnatural.md は列挙した ID がすべて出ること、
fixtures/natural.md は自然な日本語なので誤検出が出ないことを確認する
（「させていただく」は文脈依存の info なので許容）。
"""

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
DETECT = HERE / "detect.py"

MUST_DETECT = {
    "ra-nuki", "sa-ire", "keigo-double",
    "pronoun-head", "koto-ga-dekiru", "wo-okonau", "toiu", "ni-oite",
    "kanou-desu", "motte-iru", "one-of-the", "plural-tachi",
    "inanimate-subject", "no-chain", "ni-kanshite",
    "ai-ikaga", "ai-hedge", "ai-zehi", "ai-buzzword", "excl-mark",
    "kana-kudasai", "kana-koto",
    "long-sentence", "style-mix",
}

# natural.md で出てもよいもの（文脈判断が要るため機械では消せない）
ALLOWED_ON_NATURAL = {"itadaku"}


def run(path):
    out = subprocess.run(
        [sys.executable, str(DETECT), str(path), "--json"],
        capture_output=True, text=True,
    )
    if out.returncode not in (0, 1):
        sys.exit(f"detect.py が異常終了しました:\n{out.stderr}")
    return json.loads(out.stdout)


def main():
    failed = False

    found = {f["id"] for f in run(HERE / "fixtures" / "unnatural.md")}
    missing = MUST_DETECT - found
    if missing:
        failed = True
        print("検出漏れ: " + ", ".join(sorted(missing)))

    noise = [f for f in run(HERE / "fixtures" / "natural.md")
             if f["id"] not in ALLOWED_ON_NATURAL]
    if noise:
        failed = True
        print("誤検出:")
        for f in noise:
            print(f'  {f["line"]}:{f["col"]} [{f["id"]}] 「{f["text"]}」')

    if failed:
        return 1
    print(f"OK（必須 {len(MUST_DETECT)} ID を検出、誤検出なし）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
