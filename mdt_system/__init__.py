"""MDT System package

精简后仅保留新版多轮讨论编排器 `MDTOrchestrator` 与阶段枚举 `MDTPhase`。
已移除旧的通用 workflow/模拟 streaming Orchestrator/StreamingManager 以减少重复与概念混淆。
"""

from .phases import MDTPhase  # noqa: F401
from .orchestrator import MDTOrchestrator  # noqa: F401

__all__ = ["MDTOrchestrator", "MDTPhase"]
