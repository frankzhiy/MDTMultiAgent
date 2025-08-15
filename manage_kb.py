#!/usr/bin/env python3
"""命令行知识库管理脚本

功能:
  rebuild         全量重建 FAISS 索引
  incremental     增量添加(仅新文件)
  stats           显示当前索引统计
  clear           清空索引

可选参数:
  --dir DIR       文档根目录 (默认 knowledge/documents)
  --no-pdf        不处理 PDF
  --no-csv        不处理 CSV
  --patterns "*.txt,*.md"  自定义文本通配符(逗号分隔)
  --debug         设置日志级别为 DEBUG

示例:
  python manage_kb.py rebuild --dir knowledge/documents --patterns "*.txt,*.md" \
         --no-csv
  python manage_kb.py incremental
  python manage_kb.py stats
  python manage_kb.py clear
"""
import os
import sys
import argparse
import logging
from typing import List

# 确保可导入本地包
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from knowledge.vector_store import get_knowledge_store  # noqa: E402
knowledge_store = get_knowledge_store()
from utils.config import config  # noqa: E402


def parse_patterns(pat_str: str) -> List[str]:
    return [p.strip() for p in pat_str.split(',') if p.strip()]

def main():
    parser = argparse.ArgumentParser(description="医学知识库 FAISS 管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--dir', default='knowledge/documents', help='文档根目录')
    common.add_argument('--patterns', default='*.txt,*.md', help='文本文件通配符, 逗号分隔')
    common.add_argument('--no-pdf', action='store_true', help='不处理 PDF')
    common.add_argument('--no-csv', action='store_true', help='不处理 CSV')
    common.add_argument('--debug', action='store_true', help='DEBUG 日志')

    sub.add_parser('rebuild', parents=[common], help='全量重建索引')
    sub.add_parser('incremental', parents=[common], help='增量新增')
    sub.add_parser('stats', help='查看统计')
    sub.add_parser('clear', help='清空索引')

    args = parser.parse_args()

    log_level = 'DEBUG' if getattr(args, 'debug', False) else getattr(config, 'LOG_LEVEL', 'INFO')
    logging.basicConfig(level=log_level,
                        format='[%(asctime)s] %(levelname)s %(message)s',
                        datefmt='%H:%M:%S')

    if args.cmd in ('rebuild', 'incremental'):
        patterns = parse_patterns(args.patterns)
        include_pdf = not args.no_pdf
        include_csv = not args.no_csv
        directory = args.dir

        if args.cmd == 'rebuild':
            logging.info('开始全量重建...')
            summary = knowledge_store.rebuild_from_directory(
                directory_path=directory,
                patterns=patterns,
                include_pdf=include_pdf,
                include_csv=include_csv
            )
            logging.info(f'重建完成: {summary}')
        else:
            logging.info('开始增量更新...')
            summary = knowledge_store.add_new_files_only(
                directory_path=directory,
                patterns=patterns,
                include_pdf=include_pdf,
                include_csv=include_csv
            )
            logging.info(f'增量完成: {summary}')
    elif args.cmd == 'stats':
        stats = knowledge_store.get_collection_stats()
        print('知识库统计:')
        for k,v in stats.items():
            print(f'  {k}: {v}')
    elif args.cmd == 'clear':
        ok = knowledge_store.clear_collection()
        print('已清空' if ok else '清空失败')
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
