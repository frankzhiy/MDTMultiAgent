"""MDT 讨论阶段定义 (phases.py)

本文件抽离出“阶段 (Phase)”的枚举与元数据，核心目标：
1. 让流程结构显式化：便于科研中针对某个阶段做算法对比或消融。
2. 为每个阶段携带结构化元属性 (parallel / stream / 可扩展字段)，减少硬编码。
3. 支撑“阶段序列实验”：你可以在 orchestrator 中改变阶段顺序或插入新阶段，而不用修改内部逻辑常量字符串。

科研视角解释：
---------------------------------
多智能体协作研究里，一个端到端会话往往被切成功能稳定的模块化阶段，以便：
- 控制变量：只替换冲突检测算法，而不动独立分析；方便做 A/B 对比。
- 记录中间态：每个阶段输出快照可被离线分析（例如计算语义分歧矩阵、共识爬升曲线）。
- 自适应决策：某些阶段可以基于前面指标跳过（例如共识已高 → 跳过 multi_round_discussion）。

阶段语义：
INITIALIZATION          预处理病例 / 建立会话容器。
INDIVIDUAL_ANALYSIS     各专科独立首轮思考（并行 + 流式）。
SHARING_DISCUSSION      查看他人首轮结果后再输出（并行 + 流式）。
CONFLICT_DETECTION      协调员聚合差异、判断是否存在显著分歧。
MULTI_ROUND_DISCUSSION  针对冲突的迭代协同（可提前收敛）。
CONSENSUS_EVALUATION    量化整体一致度（可混合 LLM + 统计指标）。
FINAL_COORDINATION      生成最终综合建议 / 结构化输出。
COMPLETED               标记会话结束（汇总耗时 / 导出归档）。

元数据设计：
_PHASE_META 显式声明哪些阶段允许：
    parallel=True  → 可在多个代理线程/任务同时运行
    stream=True    → UI 可以订阅增量 token (agent_chunk)
未来你可添加字段：
    "skippable": bool            # 是否允许条件跳过
    "requires_conflict": bool     # 仅在存在冲突时执行
    "max_rounds": int             # 针对迭代阶段单独配置

使用方式示例：
---------------------------------
from mdt_system.phases import MDTPhase, get_phase_meta

# 1. 在 orchestrator 中判断是否并行：
if get_phase_meta(MDTPhase.INDIVIDUAL_ANALYSIS).get("parallel"):
        run_parallel_individual()

# 2. 自定义插入新阶段（科研实验）：
class ExtendedPhase(Enum):
        EVIDENCE_REWEIGHT = "evidence_reweight"

# 你可以临时扩展 _PHASE_META（实验脚本中）：
from mdt_system import phases as phase_mod
phase_mod._PHASE_META[ExtendedPhase.EVIDENCE_REWEIGHT] = {"parallel": False, "stream": False}

# 然后在 orchestrator 流程列表中插入该阶段并调用对应处理函数。

# 3. 统计：
for phase in MDTPhase:
        meta = get_phase_meta(phase)
        print(phase.value, meta.get("parallel"), meta.get("stream"))

警告：
- 不建议在生产中随意修改 _PHASE_META；科研脚本可局部 monkey patch，但应记录配置。
- 如果加入新阶段，请确保前端（进度条）和导出逻辑可处理未知 phase（通常用 default 回退）。
"""
from enum import Enum

class MDTPhase(Enum):
    INITIALIZATION = "initialization"
    INDIVIDUAL_ANALYSIS = "individual_analysis"
    SHARING_DISCUSSION = "sharing_discussion"
    CONFLICT_DETECTION = "conflict_detection"
    MULTI_ROUND_DISCUSSION = "multi_round_discussion"
    CONSENSUS_EVALUATION = "consensus_evaluation"
    FINAL_COORDINATION = "final_coordination"
    COMPLETED = "completed"

# 阶段元数据注册表：集中描述控制策略（并行 / 流式）。
# 仅列出与“科研可观察性 + 性能策略”相关的最小字段。
_PHASE_META = {
    MDTPhase.INDIVIDUAL_ANALYSIS: {"parallel": True, "stream": True},
    MDTPhase.SHARING_DISCUSSION: {"parallel": True, "stream": True},
    MDTPhase.CONFLICT_DETECTION: {"parallel": False, "stream": True},
    MDTPhase.MULTI_ROUND_DISCUSSION: {"parallel": False, "stream": True},
    MDTPhase.CONSENSUS_EVALUATION: {"parallel": False, "stream": True},
    MDTPhase.FINAL_COORDINATION: {"parallel": False, "stream": True},
}

def get_phase_meta(phase: MDTPhase):
    """获取阶段的元属性字典

    返回示例：{"parallel": True, "stream": True}
    若未定义该阶段（或未来扩展阶段未登记），返回空 dict，调用方应采取安全默认策略（按串行 / 非流式处理）。
    """
    return _PHASE_META.get(phase, {})

# 便捷：导出所有已知可流式阶段（科研时可直接引用）
STREAMABLE_PHASES = [p for p, meta in _PHASE_META.items() if meta.get("stream")]
PARALLEL_PHASES = [p for p, meta in _PHASE_META.items() if meta.get("parallel")]

__all__ = [
    "MDTPhase",
    "get_phase_meta",
    "STREAMABLE_PHASES",
    "PARALLEL_PHASES",
]
