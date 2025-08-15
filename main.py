#!/usr/bin/env python3
"""ILD 专门化多轮 MDT 系统 - 命令行入口

提供轻量 CLI 运行：选择专科、执行多轮讨论、输出关键阶段结果。
支持 --auto 模式快速运行（默认全部主要专科）。
"""

from __future__ import annotations
import asyncio
import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mdt_system.orchestrator import MDTOrchestrator
from utils.config import config
from utils.helpers import setup_logging
from knowledge.vector_store import get_knowledge_store
knowledge_store = get_knowledge_store()

ACTIVE_AGENT_KEYS = ["pulmonary", "imaging", "pathology", "rheumatology", "data_analysis"]  # 协调员自动加入
AGENT_LABELS = {
    "pulmonary": "呼吸科",
    "imaging": "影像科",
    "pathology": "病理科",
    "rheumatology": "风湿免疫科",
    "data_analysis": "数据分析",
    "coordinator": "协调员"
}

def load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ 无法加载 {path}: {e}")
        return None

def init_knowledge():
    stats = knowledge_store.get_collection_stats()
    if stats.get("total_documents", 0) == 0:
        docs_dir = os.path.join("knowledge", "documents")
        if os.path.isdir(docs_dir):
            print("📥 构建向量知识库...")
            knowledge_store.add_documents_from_directory(docs_dir, "*.txt")
        else:
            print("⚠️ 未找到知识文档目录，跳过初始化")
    else:
        print(f"📚 知识库可用 (文档片段: {stats['total_documents']})")

def build_case_interactive() -> Dict[str, Any]:
    print("请输入病例信息 (留空则标记为 N/A):")
    def ask(k: str) -> str:
        val = input(f"{k}: ").strip()
        return val or "N/A"
    return {
        "patient_id": ask("患者ID"),
        "symptoms": ask("症状"),
        "medical_history": ask("病史"),
        "imaging_results": ask("影像学"),
        "lab_results": ask("实验室检查"),
        "pathology_results": ask("病理"),
        "additional_info": ask("其他")
    }

def select_agents(interactive: bool, preset: Optional[str]) -> List[str]:
    if preset == "all":
        return ACTIVE_AGENT_KEYS.copy()
    if not interactive:
        return ACTIVE_AGENT_KEYS.copy()
    print("\n可选专科 (输入序号, 逗号分隔, 回车=全部):")
    for i, k in enumerate(ACTIVE_AGENT_KEYS, 1):
        print(f"  {i}. {AGENT_LABELS[k]}")
    raw = input("选择: ").strip()
    if not raw:
        return ACTIVE_AGENT_KEYS.copy()
    chosen: List[str] = []
    for token in raw.split(','):
        token = token.strip()
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(ACTIVE_AGENT_KEYS):
                chosen.append(ACTIVE_AGENT_KEYS[idx])
    return chosen or ACTIVE_AGENT_KEYS.copy()

def summarize_phase_block(title: str):
    print("\n" + title)
    print("-" * 48)

def render_result(phases: Dict[str, Any]):
    # 独立分析
    if "individual_analysis" in phases:
        summarize_phase_block("🔍 独立分析阶段")
        for k, v in phases["individual_analysis"].items():
            agent = v.get("agent", k)
            print(f"【{agent}】")
            print(v.get("response", "(无)"))
            print()
    # 共享讨论
    if "sharing_discussion" in phases:
        summarize_phase_block("🤝 共享讨论阶段")
        for k, v in phases["sharing_discussion"].items():
            agent = v.get("agent", k)
            print(f"【{agent}】 {v.get('response', '(无)')}")
    # 冲突检测
    if "conflict_detection" in phases:
        summarize_phase_block("⚠️ 冲突检测")
        cd = phases["conflict_detection"]
        print(f"存在冲突: {cd.get('conflict_detected')}  共识初值: {cd.get('consensus_score')}")
        print(cd.get("conflict_analysis", "(无分析)"))
    # 多轮讨论
    if "multi_round_discussion" in phases:
        summarize_phase_block("🔄 多轮讨论")
        mrd = phases["multi_round_discussion"]
        rounds = mrd.get("rounds", [])
        for r_idx, r in enumerate(rounds, 1):
            print(f"第 {r_idx} 轮：")
            for a in r.get("responses", []):
                agent = a.get("agent", "?")
                print(f"  - {agent}: {a.get('response', '')[:120]}...")
    # 共识评估
    if "consensus_evaluation" in phases:
        summarize_phase_block("� 共识评估")
        ce = phases["consensus_evaluation"]
        print(f"共识达成: {ce.get('consensus_reached')}  分数: {ce.get('consensus_score')}")
        print(ce.get("evaluation_details") or ce.get("evaluation") or "")
    # 最终协调
    if "final_coordination" in phases:
        summarize_phase_block("🎯 最终协调")
        fc = phases["final_coordination"]
        print(fc.get("coordinator_summary") or fc.get("response") or "(无总结)")
        recs = fc.get("final_recommendations") or []
        if recs:
            print("\n建议列表:")
            for i, r in enumerate(recs, 1):
                print(f"  {i}. {r}")

async def run_cli(case_data: Dict[str, Any], selected: List[str]):
    orchestrator = MDTOrchestrator()
    result = await orchestrator.conduct_mdt_session(case_data, selected)
    phases = result.get("phases", {})
    print(f"\n会话ID: {result.get('session_id')}")
    print(f"参与专家: {', '.join(result.get('participants', []))}")
    render_result(phases)
    print("\n💾 结果已保存到 data/sessions/ (若启用了保存逻辑)")

def parse_args():
    p = argparse.ArgumentParser(description="ILD 专门化多轮 MDT CLI")
    p.add_argument("--auto", action="store_true", help="使用默认病例与全部主要专科")
    p.add_argument("--case", type=str, help="提供病例 JSON 文件路径")
    p.add_argument("--agents", type=str, help="逗号分隔的专科键 (pulmonary,imaging,...) 不含coordinator")
    return p.parse_args()

def load_case_from_args(args) -> Dict[str, Any]:
    if args.case:
        data = load_json(args.case)
        if data:
            return data
        print("⚠️ 指定病例文件加载失败，转交交互模式")
    if args.auto:
        return {
            "patient_id": "ILD_AUTO_001",
            "symptoms": "进行性呼吸困难与干咳12月",
            "medical_history": "长期被动吸烟暴露，疑似禽类过敏环境",
            "imaging_results": "HRCT: 双肺底部网格影+少量蜂窝样",
            "lab_results": "KL-6 升高，ANA 阴性",
            "pathology_results": "外科活检提示 UIP 模式",
            "additional_info": "FVC 70% DLCO 52%"}
    return build_case_interactive()

def resolve_agents(args) -> List[str]:
    if args.agents:
        chosen = []
        for a in args.agents.split(','):
            a = a.strip()
            if a in ACTIVE_AGENT_KEYS:
                chosen.append(a)
        if chosen:
            return chosen
        print("⚠️ --agents 参数无有效项，使用全部")
    if args.auto:
        return ACTIVE_AGENT_KEYS.copy()
    return select_agents(interactive=True, preset=None)

def main():
    print("🏥 ILD 多智能体 MDT 系统 (CLI)")
    if not config.OPENAI_API_KEY:
        print("❌ 未检测到 OPENAI_API_KEY，请在 .env 中配置")
        return
    try:
        config.validate()
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        return
    setup_logging()
    init_knowledge()
    args = parse_args()
    case_data = load_case_from_args(args)
    if not case_data.get("patient_id"):
        print("❌ 病例缺少 patient_id，已终止")
        return
    agents = resolve_agents(args)
    print("选择专科:", ", ".join(AGENT_LABELS[a] for a in agents))
    try:
        asyncio.run(run_cli(case_data, agents))
    except KeyboardInterrupt:
        print("\n⏹ 中断退出")
    except Exception as e:
        logging.exception("运行失败")
        print(f"❌ 运行错误: {e}")

if __name__ == "__main__":
    main()
