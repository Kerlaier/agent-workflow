#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""summarize.py —— 读一组 markdown，输出「待办 + 最近更改」摘要。

只读、不联网、不写回源文件；结果打到 stdout（Markdown）。

用法：
    python summarize.py --files "protocol/*.md" "docs/*.md" --recent 10
    python summarize.py --files "**/*.md" --recent 5
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):          # Windows 控制台默认不是 UTF-8
    sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------- 规则（可调） ----------------------------

TODO_RE = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s*(.*\S)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

# 认这两种小节名；都按「追加式」处理
CHANGELOG_KEYS = ("更新记录", "变更记录")
DEFAULT_RECENT = 10


def expand_files(patterns):
    """把 glob 模式展开成去重后的 markdown 文件列表（保持给定顺序）。"""
    found = []
    for pattern in patterns:
        hits = sorted(glob.glob(pattern, recursive=True))
        if not hits:
            print(f"[提示] 没有匹配到：{pattern}", file=sys.stderr)
        found.extend(h for h in hits if h.lower().endswith(".md"))

    seen, unique = set(), []
    for path in found:
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def read_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def collect_todos(lines):
    """返回 (未完成列表, 已完成计数)。"""
    pending, done = [], 0
    for line in lines:
        m = TODO_RE.match(line)
        if not m:
            continue
        if m.group(1).lower() == "x":
            done += 1
        else:
            pending.append(m.group(2).strip())
    return pending, done


def collect_changelog(lines, recent):
    """找「更新记录」小节，取**末尾** recent 条。

    为什么取末尾、而不是按时间排序：
      更新记录是追加式的 —— 最后写的就是最新的。
      时间戳可能缺失、也可能不一致（历史上有过），所以**不拿它当排序依据**。
    """
    entries = []
    i = 0
    while i < len(lines):
        heading = HEADING_RE.match(lines[i])
        if heading and any(k in heading.group(2) for k in CHANGELOG_KEYS):
            level = len(heading.group(1))
            i += 1
            while i < len(lines):
                inner = HEADING_RE.match(lines[i])
                if inner and len(inner.group(1)) <= level:
                    break                       # 小节结束
                text = re.sub(r"^[-*]\s*", "", lines[i].strip())
                if text and not text.startswith(">"):   # 跳过说明用的引用行
                    entries.append(text)
                i += 1
            continue
        i += 1
    if recent <= 0:
        return entries
    return entries[-recent:]


def build_report(sections, recent, files):
    out = ["# 摘要", "",
           f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}｜扫描 {len(files)} 个文件", ""]

    total = sum(len(s["pending"]) for s in sections)
    out += ["## 待办", "", f"共 **{total}** 项未完成。", ""]
    if total == 0:
        out += ["（没有未完成项）", ""]
    for s in sections:
        if not s["pending"]:
            continue
        out += [f"### {s['path']}", ""]
        out += [f"- [ ] {item}" for item in s["pending"]]
        out += [""]

    out += ["## 最近更改", "",
            f"> 每个文件取末尾 {recent} 条（更新记录是追加式的，末尾即最新；**时间戳不参与排序**）。", ""]
    changed_any = False
    for s in sections:
        if not s["changes"]:
            continue
        changed_any = True
        out += [f"### {s['path']}", ""]
        out += [f"- {e}" for e in s["changes"]]
        out += [""]
    if not changed_any:
        out += ["（没有找到「更新记录」段落）", ""]

    skipped = [s["path"] for s in sections if not s["changes"]]
    if skipped:
        out += ["## 提示", "", "下面这些文件**没有「更新记录」段落**，已跳过（不是错误）：", ""]
        out += [f"- `{p}`" for p in skipped]
        out += [""]
    return "\n".join(out).rstrip() + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="读 markdown，输出「待办 + 最近更改」摘要（只读，不改任何源文件）")
    ap.add_argument("--files", nargs="+", required=True,
                    help='文件或 glob 模式，例如 "protocol/*.md" "**/*.md"')
    ap.add_argument("--recent", type=int, default=DEFAULT_RECENT,
                    help=f"每个文件最多取多少条更新记录（默认 {DEFAULT_RECENT}；0 = 全部）")
    args = ap.parse_args(argv)

    files = expand_files(args.files)
    if not files:
        print("没有匹配到任何 markdown 文件。", file=sys.stderr)
        return 1

    sections = []
    for path in files:
        lines = read_lines(path)
        pending, done = collect_todos(lines)
        sections.append({
            "path": path,
            "pending": pending,
            "done": done,
            "changes": collect_changelog(lines, args.recent),
        })

    sys.stdout.write(build_report(sections, args.recent, files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
