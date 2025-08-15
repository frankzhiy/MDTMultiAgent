"""BaseAgent 基类

研究定位：
=============
所有临床专科 / 协调员智能体共享的基础能力封装，包括：
- RAG 检索 (向量知识库裁剪上下文)
- 统一 LLM 调用（支持流式与非流式）
- 其他专家意见格式化
- 置信度粗估抽取
- 多轮讨论提示模板构建

与 orchestrator / phases 的关系：
--------------------------------
Orchestrator 在不同 Phase 调用各 agent 的 analyze_case(...) 或 discuss_round(...)。
当 stream=True 时，必须返回一个“增量生成器”。此生成器逐块产出文本片段，直至结束。
为了保持 UI/实验一致性：上层并发与事件分发逻辑会期望最终有一个“完成”信号（当前实现中，具体验证基于 chunk 内部包装由各子类完成）。

为何暂未在基类强制封装 dict 级 chunk：
----------------------------------------
各专科子类可根据需要在流式期间做额外解析（如中途抽取关键信号）。因此基类仅输出纯文本片段；包装格式留在子类或 orchestrator 的 worker 线程内完成，以最大化灵活性。

扩展建议（科研实验）：
----------------------
1. 可为 _call_llm 新增采样控制 / 温度自适应策略比较。
2. 可在 _get_relevant_context 中插入不同的检索策略 (BM25 / Hybrid / Rerank) 做消融。
3. 可在 _extract_confidence 中替换为 LLM 指令式显式评分，或引入专用分类模型。
4. discuss_round 可接入“冲突焦点摘要”作为额外输入段落，研究其对收敛速度的影响。

子类实现最少需求：
------------------
必须实现 analyze_case(self, case_info, other_opinions, stream=False) →
    - 非流式: 返回 dict，包含 keys: agent, response, specialty, timestamp, confidence
    - 流  式: 返回 generator[dict]，逐块产出：
        {"agent": ..., "response_chunk": <当前新增文本>, "full_response": <累计文本>, "is_complete": False/True}
 结束时最后一次 yield 需带 is_complete=True，并可附加压缩版 response。

示例：
------
response_acc = ""
for piece in self._call_llm(prompt, stream=True):
    response_acc += piece
    yield {"agent": self.name, "response_chunk": piece, "full_response": response_acc, "is_complete": False}
yield {"agent": self.name, "response": response_acc, "full_response": response_acc, "is_complete": True}

注意：
------
避免在 analyze_case 内直接执行阻塞式长计算；若需要，可拆分为后台线程或在 orchestrator 侧统一并行。
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Iterator, Generator
from openai import OpenAI
from utils.config import config
from knowledge.vector_store import get_knowledge_store
knowledge_store = get_knowledge_store()
from prompts import SYSTEM_BASE_PROMPT, RAG_QUERY_PROMPT
import logging
from datetime import datetime
import os
import time

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """智能体基类"""
    
    def __init__(self, name: str, specialty: str, system_prompt: str):
        # 基本属性
        self.name = name
        self.specialty = specialty
        self.system_prompt = system_prompt

        # 统一 LLM 客户端 (OpenAI / DeepSeek 兼容)
        self.client = OpenAI(
            api_key=config.get_llm_api_key(),
            base_url=config.get_llm_base_url()
        )

        # 历史记录 & RAG 缓存（延迟创建避免解析器类型注解问题）
        self.conversation_history = []  # list of dict
        # 结构: {raw, source, score, content}
        self.last_retrieved_chunks = []
    
    @abstractmethod
    def analyze_case(self, case_info: Dict[str, Any], other_opinions: Optional[List[Dict[str, Any]]] = None, stream: bool = False) -> Any:
        """分析病例并提供专业意见
        
        Args:
            case_info: 病例信息
            other_opinions: 其他专家意见
            stream: 是否流式输出
            
        Returns:
            如果stream=False，返回Dict[str, Any]；如果stream=True，返回Generator[Dict[str, Any], None, None]
        """
        pass
    
    def _get_relevant_context(self, case_info: Dict[str, Any]) -> str:
        """获取相关医学知识上下文（支持单查询或 multi-query），并缓存片段供前端显示"""
        try:
            # 自动兜底：首次使用若向量库为空，尝试自动增量加载 knowledge/documents
            try:
                from knowledge.vector_store import get_knowledge_store as _getks
                _ks = _getks()
                stats = _ks.get_collection_stats()
                if stats.get('total_documents', 0) == 0:
                    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge', 'documents')
                    if os.path.isdir(docs_dir):
                        _ks.add_new_files_only(docs_dir, patterns=['*.txt','*.md'], include_pdf=True, include_csv=True)
            except Exception as _auto_e:
                logger.warning(f"RAG auto-ingest skipped: {_auto_e}")
            use_multi = getattr(config, 'RAG_MULTI_QUERY', False)
            self.last_retrieved_chunks = []  # 初始化缓存
            if use_multi:
                context = knowledge_store.multi_query_context(case_info, self.specialty.lower(), max_context_length=1500)
                if context:
                    # multi_query_context 已将每个片段格式化为包含来源/分数的多行块，通过分割重建结构
                    for block in context.split('\n\n')[:10]:
                        # 简单解析来源与相关度
                        first_line, *rest = block.split('\n')
                        source = ""
                        score = None
                        if first_line.startswith('['):
                            # e.g. [来源: XXX | 相关度: 0.1234 | 子查询: ...]
                            try:
                                parts = first_line.strip('[]').split('|')
                                for p in parts:
                                    if '来源:' in p:
                                        source = p.split('来源:')[1].strip()
                                    if '相关度:' in p:
                                        val = p.split('相关度:')[1].strip()
                                        try:
                                            score = float(val)
                                        except:
                                            score = None
                            except:
                                pass
                        content_text = '\n'.join(rest).strip() if rest else block
                        self.last_retrieved_chunks.append({
                            'raw': block,
                            'source': source or '未知',
                            'score': score,
                            'content': content_text
                        })
            else:
                # 单查询模式：复用已有 API，再对分割做缓存
                context = knowledge_store.get_context_for_agent(case_info, self.specialty.lower(), max_context_length=1500)
                if context:
                    for block in context.split('\n\n')[:10]:
                        first_line, *rest = block.split('\n')
                        source = ""
                        score = None
                        if first_line.startswith('['):
                            try:
                                parts = first_line.strip('[]').split('|')
                                for p in parts:
                                    if '来源:' in p:
                                        source = p.split('来源:')[1].strip()
                                    if '相关度:' in p:
                                        val = p.split('相关度:')[1].strip()
                                        try:
                                            score = float(val)
                                        except:
                                            score = None
                            except:
                                pass
                        content_text = '\n'.join(rest).strip() if rest else block
                        self.last_retrieved_chunks.append({
                            'raw': block,
                            'source': source or '未知',
                            'score': score,
                            'content': content_text
                        })
            return context if context else "暂无相关医学知识。"
        except Exception as e:
            logger.error(f"Error getting context for {self.name}: {e}")
            return "获取医学知识时出现错误。"
    
    def _format_other_opinions(self, other_opinions: List[Dict[str, Any]]) -> str:
        """格式化其他专家的意见"""
        if not other_opinions:
            return "暂无其他专家意见。"
        
        formatted_opinions = []
        for opinion in other_opinions:
            agent_name = opinion.get("agent") or opinion.get("agent_name", "未知专家")
            response = opinion.get("response", "")
            timestamp = opinion.get("formatted_time", "")
            
            formatted_opinions.append(f"""
【{agent_name}】({timestamp}):
{response}
""")
        
        return "\n".join(formatted_opinions)
    
    def _call_llm(self, prompt: str, temperature: Optional[float] = None, stream: bool = False) -> Any:
        """统一 LLM 调用封装

        参数:
            prompt: 拼接完成的最终提示词（已含病例 + 知识 + 其他专家意见）
            temperature: 覆盖默认温度（可用于实验降/升多样性）
            stream: True → 返回一个逐文本片段生成器 (yield str)

        返回:
            - 非流式: 单个字符串（模型完整回答）
            - 流式: 生成器 -> 逐 delta.content 文本片段

        设计说明:
            1. 不在此层做 chunk -> dict 的格式化，保持最小职责。
            2. 上层子类负责将片段累积和包装，以便插入自定义解析逻辑。
            3. 统一捕获异常并返回友好错误信息，避免打断 orchestrator 流程。
        """
        try:
            if stream:
                # 流式输出
                response = self.client.chat.completions.create(
                    model=config.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature or config.OPENAI_TEMPERATURE,
                    max_tokens=config.MAX_TOKENS,
                    stream=True
                )
                
                def stream_generator():
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                
                return stream_generator()
            else:
                # 非流式输出（原有逻辑）
                response = self.client.chat.completions.create(
                    model=config.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature or config.OPENAI_TEMPERATURE,
                    max_tokens=config.MAX_TOKENS
                )
                
                content = response.choices[0].message.content
                return content.strip() if content else ""
            
        except Exception as e:
            logger.error(f"Error calling LLM for {self.name}: {e}")
            error_msg = f"抱歉，{self.name}在分析过程中遇到了技术问题，请稍后重试。"
            if stream:
                def error_generator():
                    yield error_msg
                return error_generator()
            else:
                return error_msg
    
    def _build_analysis_prompt(
        self,
        case_info: Dict[str, Any],
        other_opinions: List[Dict[str, Any]],
        specialty_specific_info: str = ""
    ) -> str:
        """构建分析提示词

        组成：病例摘要 + 专科附加要求 + RAG 上下文 + 其他专家意见结构化拼接
        可在子类覆盖 specialty_specific_info 以插入专科定制指令 / 维度检查表。
        """
        context = self._get_relevant_context(case_info)
        formatted_opinions = self._format_other_opinions(other_opinions)

        # 格式化病例信息
        case_summary = f"""
患者ID: {case_info.get('patient_id', '未知')}
主要症状: {case_info.get('symptoms', '未提供')}
病史: {case_info.get('medical_history', '未提供')}
影像学结果: {case_info.get('imaging_results', '未提供')}
实验室检查: {case_info.get('lab_results', '未提供')}
病理结果: {case_info.get('pathology_results', '未提供')}
其他信息: {case_info.get('additional_info', '未提供')}
"""

        prompt = f"""
病例信息：
{case_summary}

{specialty_specific_info}

相关医学知识：
{context}

其他专家意见：
{formatted_opinions}

请根据以上信息，从{self.specialty}的角度提供你的专业分析和建议。
"""

        return prompt

    def _append_rag(self, filled_prompt: str, case_info: Dict[str, Any]) -> str:
        """在专科模板已填充的提示词后面追加 RAG 上下文段落。

        设计动机：
            - 各专科此前直接用外部模板 -> 未调用 _build_analysis_prompt → 丢失RAG。
            - 为最小侵入式改造，仅需在子类中调用 self._append_rag(filled_prompt, case_info)。
        """
        try:
            context = self._get_relevant_context(case_info)
            # 防止重复追加（若模板将来内置了标记）
            if "相关医学知识" in filled_prompt and context[:10] in filled_prompt:
                return filled_prompt
            return f"{filled_prompt}\n\n【相关医学知识RAG】\n{context}\n"
        except Exception as e:
            logger.error(f"追加RAG上下文失败: {e}")
            return f"{filled_prompt}\n\n【相关医学知识RAG】获取失败。"
    
    def add_to_history(self, case_info: Dict[str, Any], response: str):
        """添加到对话历史"""
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "case_id": case_info.get("patient_id"),
            "response": response
        })
    
    def _extract_confidence(self, response: str) -> float:
        """从响应中提取置信度分数

        策略层次：
            1. 显式数值抓取（优先）
            2. 关键词映射（粗粒度启发式）
            3. 默认中等值 0.6

        后续科研增强：
            - 可替换为 LLM self-eval 结构化 JSON 输出
            - 或引入专门分类头（另一个模型）预测置信度
        """
        import re
        
        # 尝试从响应中提取置信度信息
        confidence_patterns = [
            r'置信度[：:]\s*(\d+(?:\.\d+)?)',
            r'可信度[：:]\s*(\d+(?:\.\d+)?)',
            r'confidence[：:]\s*(\d+(?:\.\d+)?)',
            r'确定性[：:]\s*(\d+(?:\.\d+)?)',
        ]
        
        for pattern in confidence_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                try:
                    confidence = float(match.group(1))
                    # 如果是百分比形式，转换为0-1范围
                    if confidence > 1:
                        confidence = confidence / 100
                    return min(max(confidence, 0.0), 1.0)
                except ValueError:
                    continue
        
        # 如果没有找到明确的置信度，基于关键词估算
        confidence_keywords = {
            '确定': 0.9, '明确': 0.9, '肯定': 0.85,
            '很可能': 0.8, '高度怀疑': 0.75, '倾向于': 0.7,
            '可能': 0.6, '疑似': 0.5, '不确定': 0.3,
            '难以确定': 0.25, '不明确': 0.2
        }
        
        for keyword, score in confidence_keywords.items():
            if keyword in response:
                return score
        
        # 默认返回中等置信度
        return 0.6
    
    def get_summary_statistics(self) -> Dict[str, Any]:
        """获取智能体统计信息"""
        return {
            "name": self.name,
            "specialty": self.specialty,
            "total_cases_analyzed": len(self.conversation_history),
            "last_activity": self.conversation_history[-1]["timestamp"] if self.conversation_history else None
        }
    
    def discuss_round(self, case_info: Dict[str, Any], all_opinions: List[Dict[str, Any]], 
                     round_num: int) -> Dict[str, Any]:
        """
        参与多轮讨论
        
        Args:
            case_info: 病例信息
            all_opinions: 包含前轮讨论的所有意见
            round_num: 当前讨论轮次
            
        Returns:
            Dict包含本轮讨论结果
        """
        try:
            # 构建多轮讨论专用提示
            prompt = self._build_discussion_prompt(case_info, all_opinions, round_num)
            
            # 调用LLM进行讨论
            response = self._call_llm(prompt)
            
            result = {
                "agent": self.name,
                "specialty": self.specialty,
                "response": response,
                "round": round_num,
                "timestamp": datetime.now().isoformat(),
                "confidence": self._extract_confidence(response),
                "discussion_type": "multi_round"
            }
            
            # 添加到历史记录
            self.add_to_history(case_info, response)
            
            logger.info(f"{self.name} 完成第{round_num}轮讨论")
            return result
            
        except Exception as e:
            logger.error(f"{self.name} 第{round_num}轮讨论失败: {e}")
            return {
                "agent": self.name,
                "specialty": self.specialty,
                "response": f"第{round_num}轮讨论过程中出现错误: {str(e)}",
                "round": round_num,
                "timestamp": datetime.now().isoformat(),
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _build_discussion_prompt(self, case_info: Dict[str, Any], all_opinions: List[Dict[str, Any]], 
                                round_num: int) -> str:
        """构建多轮讨论提示

        说明：强调“差异再评估 + 回应他人”而不是简单重复；便于收敛速度研究。
        可实验插入：
            - 冲突焦点摘要（由协调员提供）
            - 历史轮次聚合摘要（减少 token 开销）
        """
        context = self._get_relevant_context(case_info)
        
        # 格式化病例信息
        case_summary = f"""
患者ID: {case_info.get('patient_id', '未知')}
主要症状: {case_info.get('symptoms', '未提供')}
病史: {case_info.get('medical_history', '未提供')}
影像学结果: {case_info.get('imaging_results', '未提供')}
实验室检查: {case_info.get('lab_results', '未提供')}
病理结果: {case_info.get('pathology_results', '未提供')}
其他信息: {case_info.get('additional_info', '未提供')}
"""
        
        # 格式化多轮讨论历史
        discussion_history = self._format_discussion_history(all_opinions)
        
        prompt = f"""
这是第{round_num}轮MDT讨论。

【病例信息】
{case_summary}

【相关医学知识】
{context}

【之前讨论记录】
{discussion_history}

作为{self.specialty}专家，请基于前面的讨论：
1. 重新审视你的观点
2. 回应其他专家提出的问题或分歧
3. 如果有新的见解，请详细说明
4. 如果坚持之前的观点，请提供更多支持证据
5. 对于其他专家的不同意见，请给出你的看法

请注意：这是多轮讨论，期望有更深入、更具体的分析。
"""
        
        return prompt
    
    def _format_discussion_history(self, all_opinions: List[Dict[str, Any]]) -> str:
        """格式化多轮讨论历史"""
        if not all_opinions:
            return "暂无之前的讨论记录。"
        
        # 按轮次和时间组织意见
        rounds = {}
        for opinion in all_opinions:
            round_num = opinion.get('round', 1)
            if round_num not in rounds:
                rounds[round_num] = []
            rounds[round_num].append(opinion)
        
        formatted_history = []
        for round_num in sorted(rounds.keys()):
            formatted_history.append(f"\n=== 第{round_num}轮讨论 ===")
            for opinion in rounds[round_num]:
                agent_name = opinion.get('agent', '未知专家')
                response = opinion.get('response', '')
                timestamp = opinion.get('timestamp', '')
                
                formatted_history.append(f"""
【{agent_name}】({timestamp}):
{response}
""")
        
        return "\n".join(formatted_history)
