"""Prompt 加载器

职责：
1. 读取 registry.py 中登记的 markdown 文件
2. 支持简单 YAML front-matter 或 HTML 注释头剥离
3. 返回纯文本（保留 {placeholders} 占位符）
4. 结果缓存，避免重复 IO；可通过 reload=True 强制刷新

非工程人员：只需编辑 markdown 文件内容；不要改 id 字段；新增文件后让工程同事在 registry.py 登记。
"""
from __future__ import annotations
import os, re, io
from pathlib import Path
from typing import Dict, Tuple, List, Set, Optional
import yaml
from .registry import PROMPT_FILES

_BASE_DIR = Path(__file__).resolve().parent
_CACHE: Dict[str, str] = {}
_META_CACHE: Dict[str, Dict[str, str]] = {}
_FRONT_MATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_HTML_COMMENT_BLOCK_RE = re.compile(r"^<!--.*?-->\n?", re.DOTALL)

class PromptNotFound(Exception):
    pass

def _strip_meta(text: str) -> str:
    # 去掉 YAML front-matter 或开头单个注释块
    text = _FRONT_MATTER_RE.sub("", text, count=1)
    text = _HTML_COMMENT_BLOCK_RE.sub("", text, count=1)
    return text.strip()

def get_prompt(prompt_id: str, reload: bool=False) -> str:
    if not reload and prompt_id in _CACHE:
        return _CACHE[prompt_id]
    rel_path = PROMPT_FILES.get(prompt_id)
    if not rel_path:
        raise PromptNotFound(f"未登记的提示词ID: {prompt_id}")
    file_path = _BASE_DIR / rel_path
    if not file_path.exists():
        raise PromptNotFound(f"提示词文件不存在: {file_path}")
    text = file_path.read_text(encoding='utf-8')
    content = _strip_meta(text)
    _CACHE[prompt_id] = content
    return content

def list_prompts() -> Dict[str, str]:
    return {k: str((_BASE_DIR / v).resolve()) for k, v in PROMPT_FILES.items()}

def _load_catalog() -> Dict[str, Dict[str, str]]:
    if _META_CACHE:
        return _META_CACHE
    catalog_path = _BASE_DIR / "catalog.yaml"
    if not catalog_path.exists():
        return {}
    try:
        data = yaml.safe_load(catalog_path.read_text(encoding='utf-8')) or {}
        items = data.get('prompts', {})
        for pid, meta in items.items():
            if isinstance(meta, dict):
                _META_CACHE[pid] = {
                    'label': meta.get('label', pid),
                    'category': meta.get('category', ''),
                    'role': meta.get('role', ''),
                    'description': meta.get('description', ''),
                    'group': meta.get('group', ''),  # 新增分组 (按智能体/Agent)
                }
    except Exception:
        return {}
    return _META_CACHE

def get_prompt_meta(prompt_id: str) -> Optional[Dict[str, str]]:
    catalog = _load_catalog()
    return catalog.get(prompt_id)

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

def safe_format(template: str, **kwargs) -> Tuple[str, List[str]]:
    """安全格式化：

    - 提取模板中的占位符 {var}
    - 对缺失的变量不抛异常，原样保留并记录
    - 返回 (格式化后文本, 缺失变量列表)
    - 若某变量值为 None，亦视为缺失（避免生成 'None' 文本）
    """
    placeholders: Set[str] = set(_PLACEHOLDER_RE.findall(template))
    missing: List[str] = []
    # 构造用于 format 的替换字典：缺失的先临时放置特殊标记占位，稍后再替换回原形式
    sentinel_prefix = "__MISSING_PLACEHOLDER__"
    format_map = {}
    for name in placeholders:
        if name in kwargs and kwargs[name] is not None:
            format_map[name] = kwargs[name]
        else:
            missing.append(name)
            format_map[name] = f"{sentinel_prefix}{name}__"
    try:
        formatted = template.format(**format_map)
    except Exception as e:  # 极少数情况（例如花括号转义混乱）
        # 直接回退为原始模板，记录全部占位符为缺失
        return template, sorted(list(placeholders))
    # 恢复缺失变量成原始占位符形式
    for name in missing:
        formatted = formatted.replace(f"{sentinel_prefix}{name}__", f"{{{name}}}")
    return formatted, missing

__all__ = ["get_prompt", "list_prompts", "PromptNotFound", "safe_format", "get_prompt_meta"]

 
