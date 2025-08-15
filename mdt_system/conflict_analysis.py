"""冲突分析与共识评估组件

独立出：
- 冲突检测 detect_conflicts
- 共识评估 evaluate_consensus
- 共识与冲突文本解析方法

便于针对性替换 / 实验不同冲突度量算法。
"""
from __future__ import annotations
from typing import List, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ConflictAnalyzer:
    def __init__(self, coordinator_agent):
        self.coordinator = coordinator_agent

    def detect(self, case_data: Dict[str, Any], opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行冲突检测，返回结构化结果"""
        try:
            result = self.coordinator.detect_conflicts(case_data, opinions)
            # 规范化字段
            normalized = {
                "agent": self.coordinator.name,
                "conflict_detected": result.get("conflicts_detected") or result.get("conflict_detected"),
                "conflicts_detected": result.get("conflicts_detected") or result.get("conflict_detected"),
                "response": result.get("response") or result,
                "raw": result,
                "timestamp": datetime.now().isoformat(),
            }
            return normalized
        except Exception as e:
            logger.error(f"Conflict detection error: {e}")
            return {
                "agent": self.coordinator.name,
                "conflict_detected": True,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def evaluate_consensus(self, opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            result = self.coordinator.evaluate_consensus(opinions)
            normalized = {
                "agent": self.coordinator.name,
                "consensus_score": result.get("consensus_score", 0.0),
                "consensus_reached": result.get("consensus_score", 0.0) >= 0.75,
                "raw": result,
                "timestamp": datetime.now().isoformat(),
            }
            return normalized
        except Exception as e:
            logger.error(f"Consensus evaluation error: {e}")
            return {
                "agent": self.coordinator.name,
                "consensus_score": 0.0,
                "consensus_reached": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def final_coordination(self, case_data: Dict[str, Any], all_phases: Dict[str, Any], consensus_reached: bool) -> Dict[str, Any]:
        try:
            result = self.coordinator.final_coordination(case_data, all_phases, consensus_reached)
            result.setdefault("timestamp", datetime.now().isoformat())
            return result
        except Exception as e:
            logger.error(f"Final coordination error: {e}")
            return {
                "agent": self.coordinator.name,
                "response": f"最终协调失败: {e}",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
