"""Prompt 预览与占位符检测工具

用法（示例）：
python -m prompts.preview_tool --list
python -m prompts.preview_tool --id COORDINATOR_PROMPT --show
python -m prompts.preview_tool --id CASE_SUMMARY_PROMPT --check --supply case_info='xxx' discussion_process='...' final_decision='...'

非工程人员：
1. --list 查看可用 ID
2. --id 选择要预览的 prompt
3. 如果需要检测占位符是否都能成功格式化，提供 --check 与 --supply k=v 对。
"""
from __future__ import annotations
import argparse, re, sys
from typing import Dict
from . import get_prompt, PROMPT_FILES

PLACEHOLDER_RE = re.compile(r"{([a-zA-Z0-9_]+)}")

def extract_placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER_RE.findall(text))

def format_with_supply(text: str, supply: Dict[str,str]) -> str:
    try:
        return text.format(**supply)
    except KeyError as e:
        missing = e.args[0]
        raise KeyError(f"缺少占位符参数: {missing}") from e

def main(argv=None):
    p = argparse.ArgumentParser(description="Prompt 预览工具")
    p.add_argument('--list', action='store_true', help='列出所有 Prompt ID')
    p.add_argument('--id', help='指定要预览的 Prompt ID')
    p.add_argument('--show', action='store_true', help='打印原始内容')
    p.add_argument('--check', action='store_true', help='检测占位符并尝试格式化')
    p.add_argument('--supply', nargs='*', help='提供占位符值，形式 k=v')
    args = p.parse_args(argv)

    if args.list:
        print('可用 Prompt ID:')
        for pid in PROMPT_FILES.keys():
            print(' -', pid)
        return

    if not args.id:
        print('未提供 --id，使用 --list 查看可用 ID', file=sys.stderr)
        return

    try:
        content = get_prompt(args.id, reload=False)
    except Exception as e:
        print(f"加载失败: {e}", file=sys.stderr)
        return

    placeholders = extract_placeholders(content)
    print(f"Prompt: {args.id}")
    print(f"文件: {PROMPT_FILES.get(args.id)}")
    print(f"占位符: {sorted(placeholders) if placeholders else '（无）'}")

    if args.show:
        print('-' * 40)
        print(content)
        print('-' * 40)

    if args.check:
        supply_map: Dict[str,str] = {}
        if args.supply:
            for pair in args.supply:
                if '=' not in pair:
                    print(f"忽略非法 supply: {pair}")
                    continue
                k, v = pair.split('=', 1)
                supply_map[k] = v
        missing = [ph for ph in placeholders if ph not in supply_map]
        if missing:
            print(f"缺少参数: {missing}")
        else:
            try:
                rendered = format_with_supply(content, supply_map)
                print('格式化成功预览:')
                print('-' * 40)
                print(rendered)
                print('-' * 40)
            except KeyError as e:
                print(f"格式化失败: {e}")

if __name__ == '__main__':
    main()
