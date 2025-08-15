from typing import Dict, Any, List, Optional, Generator
from agents.base_agent import BaseAgent
from prompts import (
    COORDINATOR_SYSTEM_PROMPT,
    COORDINATION_ANALYSIS_PROMPT,
    CONFLICT_DETECTION_PROMPT,
    CONSENSUS_EVALUATION_PROMPT,
    FINAL_COORDINATION_PROMPT,
)
from prompts.loader import safe_format
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CoordinatorAgent(BaseAgent):
    """MDT协调员智能体 - 负责整合各专科意见并生成最终建议"""
    
    def __init__(self):
        super().__init__(
            name="MDT协调员",
            specialty="多学科协调",
            system_prompt=COORDINATOR_SYSTEM_PROMPT
        )
        self.consensus_threshold = 0.7
        
    def analyze_case(self, case_info: Dict[str, Any], other_opinions: Optional[List[Dict[str, Any]]] = None, stream: bool = False) -> Any:
        """分析病例并协调各专科意见"""
        if other_opinions is None:
            other_opinions = []
            
        try:
            # 构建协调提示
            prompt = self._build_coordination_prompt(case_info, other_opinions)
            
            # 计算共识度
            specialists_summary = self._format_other_opinions(other_opinions)
            consensus_score = self._calculate_consensus(specialists_summary)
            
            if stream:
                # 流式输出
                def stream_generator():
                    full_response = ""
                    for chunk in self._call_llm(prompt, stream=True):
                        full_response += chunk
                        yield {
                            "agent": self.name,
                            "specialty": self.specialty,
                            "response_chunk": chunk,
                            "full_response": full_response,
                            "consensus_score": consensus_score,
                            "timestamp": self._get_timestamp(),
                            "is_complete": False
                        }
                    
                    # 最终完成的响应
                    yield {
                        "agent": self.name,
                        "specialty": self.specialty,
                        "response": full_response,
                        "consensus_score": consensus_score,
                        "timestamp": self._get_timestamp(),
                        "confidence": self._extract_confidence(full_response),
                        "is_complete": True
                    }
                
                return stream_generator()
            else:
                # 非流式输出（原有逻辑）
                response = self._call_llm(prompt)
                
                result = {
                    "agent": self.name,
                    "specialty": self.specialty,
                    "response": response,
                    "consensus_score": consensus_score,
                    "timestamp": self._get_timestamp(),
                    "confidence": self._extract_confidence(response)
                }
                
                logger.info(f"MDT协调完成，共识度: {consensus_score:.2f}")
                return result
            
        except Exception as e:
            logger.error(f"MDT协调过程出错: {str(e)}")
            error_result = {
                "agent": self.name,
                "specialty": self.specialty,
                "response": f"协调过程出现错误: {str(e)}",
                "consensus_score": 0.0,
                "timestamp": self._get_timestamp(),
                "confidence": 0.0,
                "error": str(e)
            }
            
            if stream:
                def error_generator():
                    error_result["is_complete"] = True
                    yield error_result
                return error_generator()
            else:
                return error_result
    
    def _build_coordination_prompt(self, case_info: Dict[str, Any], other_opinions: List[Dict[str, Any]]) -> str:
        """构建协调提示"""
        specialists_opinions = self._format_other_opinions(other_opinions)
        
        filled, missing = safe_format(
            COORDINATION_ANALYSIS_PROMPT,
            patient_id=case_info.get('patient_id','N/A'),
            symptoms=case_info.get('symptoms','N/A'),
            medical_history=case_info.get('medical_history','N/A'),
            imaging_results=case_info.get('imaging_results','N/A'),
            lab_results=case_info.get('lab_results','N/A'),
            pathology_results=case_info.get('pathology_results','N/A'),
            additional_info=case_info.get('additional_info','N/A'),
            specialists_opinions=specialists_opinions,
        )
        if missing:
            logger.warning(f"COORDINATION_ANALYSIS_PROMPT 缺失占位符: {missing}")
        # 追加RAG上下文（协调员也可参考全局知识）
        return self._append_rag(filled, case_info)
    
    def _format_other_opinions(self, other_opinions: List[Dict[str, Any]]) -> str:
        """格式化其他专科医生的意见"""
        if not other_opinions:
            return "暂无其他专科医生意见"
        
        formatted_opinions = []
        for opinion in other_opinions:
            if isinstance(opinion, dict):
                agent_name = opinion.get('agent', '未知专科')
                response = opinion.get('response', '无响应')
                # 只有当response不为空时才添加
                if response and response.strip():
                    formatted_opinions.append(f"【{agent_name}】\n{response}\n")
            else:
                # 如果不是字典，尝试转换为字符串
                logger.warning(f"收到非字典格式的意见: {type(opinion)}")
                formatted_opinions.append(f"【未知专科】\n{str(opinion)}\n")
        
        return "\n".join(formatted_opinions) if formatted_opinions else "暂无有效意见"
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _calculate_consensus(self, specialists_opinions: str) -> float:
        """计算专家共识度"""
        try:
            # 简化的共识度计算方法
            # 实际应用中可以使用更复杂的NLP分析
            
            if not specialists_opinions:
                return 0.0
            
            # 检查关键词一致性
            consensus_indicators = [
                "建议", "推荐", "治疗", "诊断", "手术", 
                "化疗", "放疗", "观察", "随访", "检查"
            ]
            
            opinions = specialists_opinions.lower()
            indicator_count = sum(1 for indicator in consensus_indicators if indicator in opinions)
            
            # 基础共识度
            base_score = min(indicator_count / len(consensus_indicators), 1.0)
            
            # 检查是否有明显分歧
            conflict_indicators = ["不同意", "分歧", "争议", "不确定", "需要讨论"]
            conflict_count = sum(1 for indicator in conflict_indicators if indicator in opinions)
            
            # 调整共识度
            consensus_score = base_score - (conflict_count * 0.1)
            return max(0.0, min(1.0, consensus_score))
            
        except Exception as e:
            logger.warning(f"共识度计算出错: {str(e)}")
            return 0.5  # 默认中等共识度
    
    def _extract_confidence(self, response: str) -> float:
        """从响应中提取置信度"""
        try:
            # 简化的置信度评估
            confidence_indicators = {
                "强烈建议": 0.9,
                "明确建议": 0.8,
                "建议": 0.7,
                "可以考虑": 0.6,
                "可能": 0.5,
                "不确定": 0.3,
                "需要进一步": 0.4
            }
            
            response_lower = response.lower()
            max_confidence = 0.5  # 默认置信度
            
            for indicator, confidence in confidence_indicators.items():
                if indicator in response_lower:
                    max_confidence = max(max_confidence, confidence)
            
            return max_confidence
            
        except Exception:
            return 0.5  # 默认置信度
    
    def coordinate_discussion(self, individual_analyses: Dict[str, Dict]) -> Dict[str, Any]:
        """协调多个专科的讨论结果"""
        try:
            # 整合各专科意见
            specialists_summary = self._summarize_specialists_opinions(individual_analyses)
            
            # 识别关键议题
            key_issues = self._identify_key_issues(individual_analyses)
            
            # 生成协调建议
            coordination_prompt = f"""
作为MDT协调员，基于以下各专科医生的独立分析，请提供综合协调意见：

{specialists_summary}

关键议题：
{key_issues}

请提供：
1. 综合诊断结论
2. 统一治疗方案
3. 各专科配合要点
4. 时间安排和优先级
5. 患者沟通要点
"""
            
            response = self._call_llm(coordination_prompt)
            consensus_score = self._calculate_consensus(specialists_summary)
            
            return {
                "agent": self.name,
                "response": response,
                "consensus_score": consensus_score,
                "specialists_count": len(individual_analyses),
                "key_issues": key_issues,
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"协调讨论出错: {str(e)}")
            return {
                "agent": self.name,
                "response": f"协调过程出现错误: {str(e)}",
                "consensus_score": 0.0,
                "error": str(e),
                "timestamp": self._get_timestamp()
            }
    
    def _summarize_specialists_opinions(self, analyses: Dict[str, Dict]) -> str:
        """总结各专科意见"""
        summary_parts = []
        
        for agent_name, analysis in analyses.items():
            if isinstance(analysis, dict) and 'response' in analysis:
                summary_parts.append(f"【{analysis.get('agent', agent_name)}】\n{analysis['response']}\n")
        
        return "\n".join(summary_parts)
    
    def _identify_key_issues(self, analyses: Dict[str, Dict]) -> str:
        """识别关键议题"""
        # 简化的关键议题识别
        key_topics = ["诊断", "治疗", "手术", "化疗", "放疗", "预后", "风险"]
        
        issues = []
        for topic in key_topics:
            mentions = 0
            for analysis in analyses.values():
                if isinstance(analysis, dict) and 'response' in analysis:
                    if topic in analysis['response']:
                        mentions += 1
            
            if mentions >= 2:  # 至少两个专科提到
                issues.append(f"- {topic}方案需要多学科协调")
        
        return "\n".join(issues) if issues else "- 各专科意见较为一致"
    
    def coordinate_mdt_discussion(self, case_info: Dict[str, Any], phase_results: Dict[str, Dict]) -> Dict[str, Any]:
        """协调MDT讨论 - 整合所有阶段的结果"""
        try:
            logger.info(f"开始MDT协调，收到phase_results: {list(phase_results.keys())}")
            
            # 提取个体分析结果
            individual_analyses = phase_results.get('individual_analysis', {})
            cross_consultation = phase_results.get('cross_consultation', {})
            
            logger.info(f"个体分析结果数量: {len(individual_analyses)}")
            logger.info(f"交叉会诊结果数量: {len(cross_consultation)}")
            
            # 构建综合分析
            all_opinions = []
            
            # 添加个体分析意见
            for agent_name, analysis in individual_analyses.items():
                logger.info(f"处理智能体 {agent_name} 的分析结果，类型: {type(analysis)}")
                if isinstance(analysis, dict) and analysis.get('response'):
                    # 确保添加的是字典格式
                    opinion_dict = {
                        'agent': analysis.get('agent', agent_name),
                        'response': analysis.get('response', ''),
                        'timestamp': analysis.get('timestamp', ''),
                        'specialty': analysis.get('specialty', '')
                    }
                    all_opinions.append(opinion_dict)
                    logger.info(f"成功添加意见，智能体: {opinion_dict['agent']}")
                else:
                    logger.warning(f"跳过无效分析结果: {agent_name}, 类型: {type(analysis)}")
            
            # 添加交叉会诊意见
            for agent_name, analysis in cross_consultation.items():
                logger.info(f"处理交叉会诊 {agent_name} 的结果，类型: {type(analysis)}")
                if isinstance(analysis, dict) and analysis.get('response'):
                    # 确保添加的是字典格式，并避免重复
                    opinion_dict = {
                        'agent': analysis.get('agent', agent_name),
                        'response': analysis.get('response', ''),
                        'timestamp': analysis.get('timestamp', ''),
                        'specialty': analysis.get('specialty', '')
                    }
                    
                    # 检查是否已存在相同的意见（基于agent名称和response内容）
                    is_duplicate = False
                    for existing_opinion in all_opinions:
                        if (existing_opinion.get('agent') == opinion_dict.get('agent') and 
                            existing_opinion.get('response') == opinion_dict.get('response')):
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        all_opinions.append(opinion_dict)
                        logger.info(f"成功添加交叉会诊意见，智能体: {opinion_dict['agent']}")
                    else:
                        logger.info(f"跳过重复意见: {agent_name}")
                else:
                    logger.warning(f"跳过无效交叉会诊结果: {agent_name}, 类型: {type(analysis)}")
            
            logger.info(f"总共收集到 {len(all_opinions)} 个有效意见")
            
            # 验证all_opinions的格式
            for i, opinion in enumerate(all_opinions):
                if not isinstance(opinion, dict):
                    logger.error(f"意见 {i} 不是字典格式: {type(opinion)}")
                    raise ValueError(f"意见格式错误: 第{i}个意见不是字典类型")
            
            # 使用现有的analyze_case方法进行协调
            result = self.analyze_case(case_info, all_opinions)
            
            # 添加MDT特定的信息
            result.update({
                "coordination_type": "mdt_final",
                "phase_count": len(phase_results),
                "total_opinions": len(all_opinions)
            })
            
            logger.info(f"MDT最终协调完成，处理了{len(all_opinions)}个专家意见")
            return result
            
        except Exception as e:
            logger.error(f"MDT讨论协调出错: {str(e)}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return {
                "agent": self.name,
                "response": f"MDT讨论协调过程出现错误: {str(e)}",
                "consensus_score": 0.0,
                "error": str(e),
                "timestamp": self._get_timestamp()
            }
    
    def detect_conflicts(self, case_info: Dict[str, Any], opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        检测专家意见之间的冲突和分歧
        
        Args:
            case_info: 病例信息
            opinions: 专家意见列表
            
        Returns:
            Dict包含冲突检测结果
        """
        try:
            logger.info(f"开始冲突检测，收到 {len(opinions)} 个专家意见")
            
            if len(opinions) < 2:
                return {
                    "agent": self.name,
                    "conflicts_detected": False,
                    "response": "专家意见数量不足，无法检测冲突",
                    "consensus_score": 1.0,
                    "timestamp": self._get_timestamp()
                }
            
            # 构建冲突检测提示
            opinions_text = self._format_other_opinions(opinions)
            
            conflict_prompt, missing = safe_format(
                CONFLICT_DETECTION_PROMPT,
                patient_id=case_info.get('patient_id','N/A'),
                symptoms=case_info.get('symptoms','N/A'),
                opinions_text=opinions_text,
            )
            if missing:
                logger.warning(f"CONFLICT_DETECTION_PROMPT 缺失占位符: {missing}")
            response = self._call_llm(conflict_prompt)
            
            # 分析响应判断是否有冲突
            conflicts_detected = self._analyze_conflict_response(response)
            consensus_score = self._calculate_consensus(opinions_text)
            
            result = {
                "agent": self.name,
                "conflict_detected": conflicts_detected,  # 修改字段名以匹配UI期望
                "conflicts_detected": conflicts_detected,  # 保留兼容性
                "conflict_analysis": response,  # 添加UI期望的字段
                "response": response,
                "consensus_score": consensus_score,
                "opinions_analyzed": len(opinions),
                "timestamp": self._get_timestamp()
            }
            
            logger.info(f"冲突检测完成，发现冲突: {conflicts_detected}, 共识度: {consensus_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"冲突检测过程出错: {str(e)}")
            return {
                "agent": self.name,
                "conflicts_detected": True,  # 出错时默认有冲突
                "response": f"冲突检测过程出现错误: {str(e)}",
                "consensus_score": 0.0,
                "error": str(e),
                "timestamp": self._get_timestamp()
            }
    
    def _analyze_conflict_response(self, response: str) -> bool:
        """分析冲突检测响应判断是否有冲突"""
        response_lower = response.lower()
        
        # 明确的一致性指示词 - 优先检查，避免子字符串匹配问题
        consensus_indicators = [
            "没有显著冲突", "意见一致", "观点统一", "基本一致", "无明显分歧",
            "达成共识", "意见相符", "看法相近", "高度的一致性", "没有冲突"
        ]
        
        # 明确的冲突指示词
        conflict_indicators = [
            "有显著冲突", "存在分歧", "意见不一致", "有争议", "有矛盾",
            "需要进一步讨论", "意见分化", "看法不同", "观点相左", "发现冲突"
        ]
        
        # 优先检查一致性指示词，避免子字符串匹配问题
        for indicator in consensus_indicators:
            if indicator in response_lower:
                return False
        
        # 然后检查冲突指示词
        for indicator in conflict_indicators:
            if indicator in response_lower:
                return True
        
        # 最后根据关键词频率判断
        conflict_words = ["冲突", "分歧", "不同", "争议", "矛盾"]
        conflict_count = sum(1 for word in conflict_words if word in response_lower)
        
        return conflict_count >= 2
    
    def evaluate_consensus(self, opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        评估专家意见的共识程度
        
        Args:
            opinions: 专家意见列表
            
        Returns:
            Dict包含共识评估结果
        """
        try:
            logger.info(f"开始共识评估，收到 {len(opinions)} 个专家意见")
            
            if len(opinions) < 2:
                return {
                    "agent": self.name,
                    "consensus_score": 1.0,
                    "response": "专家意见数量不足，默认完全共识",
                    "timestamp": self._get_timestamp()
                }
            
            opinions_text = self._format_other_opinions(opinions)
            
            consensus_prompt, missing = safe_format(
                CONSENSUS_EVALUATION_PROMPT,
                opinions_text=opinions_text,
            )
            if missing:
                logger.warning(f"CONSENSUS_EVALUATION_PROMPT 缺失占位符: {missing}")
            response = self._call_llm(consensus_prompt)
            consensus_score = self._extract_consensus_score(response)
            
            # 使用原有方法验证
            calculated_score = self._calculate_consensus(opinions_text)
            
            # 取两种方法的平均值作为最终分数
            final_score = (consensus_score + calculated_score) / 2
            
            # 判断是否达成共识 (阈值0.75)
            consensus_threshold = 0.75
            consensus_reached = final_score >= consensus_threshold
            
            result = {
                "agent": self.name,
                "consensus_score": final_score,
                "consensus_reached": consensus_reached,  # 添加UI期望的字段
                "threshold": consensus_threshold,  # 添加阈值信息
                "evaluation": response,  # 添加UI期望的字段
                "response": response,
                "llm_score": consensus_score,
                "calculated_score": calculated_score,
                "opinions_count": len(opinions),
                "timestamp": self._get_timestamp()
            }
            
            logger.info(f"共识评估完成，最终得分: {final_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"共识评估过程出错: {str(e)}")
            return {
                "agent": self.name,
                "consensus_score": 0.5,  # 默认中等共识
                "response": f"共识评估过程出现错误: {str(e)}",
                "error": str(e),
                "timestamp": self._get_timestamp()
            }
    
    def _extract_consensus_score(self, response: str) -> float:
        """从LLM响应中提取共识分数"""
        try:
            import re
            
            # 寻找明确的分数表述
            score_patterns = [
                r'共识评分[：:]\s*([0-9]*\.?[0-9]+)',
                r'综合评分[：:]\s*([0-9]*\.?[0-9]+)', 
                r'共识程度[：:]\s*([0-9]*\.?[0-9]+)',
                r'([0-9]*\.?[0-9]+)\s*分',
                r'([0-9]*\.?[0-9]+)/1',
                r'分数[：:]\s*([0-9]*\.?[0-9]+)'
            ]
            
            for pattern in score_patterns:
                matches = re.findall(pattern, response)
                if matches:
                    try:
                        score = float(matches[-1])  # 取最后一个匹配的分数
                        if 0 <= score <= 1:
                            return score
                        elif 0 <= score <= 10:  # 可能是10分制
                            return score / 10
                    except ValueError:
                        continue
            
            # 如果没找到明确分数，根据描述词判断
            response_lower = response.lower()
            
            if any(word in response_lower for word in ["高度共识", "完全一致", "高度一致"]):
                return 0.9
            elif any(word in response_lower for word in ["良好共识", "基本一致", "较为一致"]):
                return 0.8
            elif any(word in response_lower for word in ["部分共识", "部分一致", "有一定共识"]):
                return 0.6
            elif any(word in response_lower for word in ["轻微共识", "略有共识", "轻度一致"]):
                return 0.4
            elif any(word in response_lower for word in ["显著分歧", "明显分歧", "严重分歧"]):
                return 0.2
            
            return 0.5  # 默认中等共识
            
        except Exception as e:
            logger.warning(f"提取共识分数失败: {e}")
            return 0.5
    
    def final_coordination(self, case_info: Dict[str, Any], all_phases: Dict[str, Any], 
                          consensus_reached: bool) -> Dict[str, Any]:
        """
        执行最终协调，生成综合MDT建议
        
        Args:
            case_info: 病例信息
            all_phases: 所有阶段的结果
            consensus_reached: 是否达成共识
            
        Returns:
            Dict包含最终协调结果
        """
        try:
            logger.info(f"开始最终协调，共识状态: {consensus_reached}")
            
            # 提取关键信息
            individual_analysis = all_phases.get("individual_analysis", {})
            sharing_discussion = all_phases.get("sharing_discussion", {})
            multi_round_discussion = all_phases.get("multi_round_discussion", {})
            consensus_evaluation = all_phases.get("consensus_evaluation", {})
            
            # 构建最终协调提示
            coordination_prompt, missing = safe_format(
                FINAL_COORDINATION_PROMPT,
                patient_id=case_info.get('patient_id','N/A'),
                symptoms=case_info.get('symptoms','N/A'),
                medical_history=case_info.get('medical_history','N/A'),
                imaging_results=case_info.get('imaging_results','N/A'),
                individual_count=len(individual_analysis),
                sharing_count=len(sharing_discussion),
                multi_round_status=("进行了详细讨论" if multi_round_discussion else "无需深入讨论"),
                consensus_status=("已达成共识" if consensus_reached else "存在分歧"),
                consensus_summary=self._format_consensus_summary(consensus_evaluation),
                final_opinions=self._format_final_opinions(all_phases),
            )
            if missing:
                logger.warning(f"FINAL_COORDINATION_PROMPT 缺失占位符: {missing}")
            response = self._call_llm(coordination_prompt)
            
            # 计算最终共识度
            final_consensus = self._calculate_final_consensus(all_phases)
            
            result = {
                "agent": self.name,
                "specialty": self.specialty,
                "response": response,
                "consensus_score": final_consensus,
                "consensus_reached": consensus_reached,
                "discussion_rounds": self._count_discussion_rounds(all_phases),
                "coordination_type": "multi_round_final",
                "timestamp": self._get_timestamp(),
                "confidence": self._extract_confidence(response)
            }
            
            logger.info(f"最终协调完成，最终共识度: {final_consensus:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"最终协调过程出错: {str(e)}")
            return {
                "agent": self.name,
                "response": f"最终协调过程出现错误: {str(e)}",
                "consensus_score": 0.0,
                "error": str(e),
                "timestamp": self._get_timestamp()
            }
    
    def _format_consensus_summary(self, consensus_evaluation: Dict[str, Any]) -> str:
        """格式化共识评估摘要"""
        if not consensus_evaluation:
            return "无共识评估数据"
        
        score = consensus_evaluation.get('consensus_score', 0.0)
        return f"共识度评分: {score:.2f}/1.0"
    
    def _format_final_opinions(self, all_phases: Dict[str, Any]) -> str:
        """格式化各阶段的最终意见"""
        opinions = []
        
        # 优先使用多轮讨论的结果
        multi_round = all_phases.get("multi_round_discussion", {})
        if multi_round and "rounds" in multi_round:
            rounds = multi_round["rounds"]
            if rounds:
                last_round = rounds[-1]["results"]
                for agent_name, result in last_round.items():
                    if isinstance(result, dict) and result.get('response'):
                        opinions.append(f"【{result.get('agent', agent_name)}】\n{result['response']}\n")
        
        # 如果没有多轮讨论结果，使用初步讨论结果
        if not opinions:
            sharing = all_phases.get("sharing_discussion", {})
            for agent_name, result in sharing.items():
                if isinstance(result, dict) and result.get('response'):
                    opinions.append(f"【{result.get('agent', agent_name)}】\n{result['response']}\n")
        
        # 最后使用独立分析结果
        if not opinions:
            individual = all_phases.get("individual_analysis", {})
            for agent_name, result in individual.items():
                if isinstance(result, dict) and result.get('response'):
                    opinions.append(f"【{result.get('agent', agent_name)}】\n{result['response']}\n")
        
        return "\n".join(opinions) if opinions else "无有效专家意见"
    
    def _calculate_final_consensus(self, all_phases: Dict[str, Any]) -> float:
        """计算最终共识度"""
        try:
            # 优先使用共识评估的结果
            consensus_eval = all_phases.get("consensus_evaluation", {})
            if consensus_eval and "consensus_score" in consensus_eval:
                return consensus_eval["consensus_score"]
            
            # 使用多轮讨论最后一轮的共识度
            multi_round = all_phases.get("multi_round_discussion", {})
            if multi_round and "rounds" in multi_round:
                rounds = multi_round["rounds"]
                if rounds and "consensus_score" in rounds[-1]:
                    return rounds[-1]["consensus_score"]
            
            # 使用基础计算方法
            final_opinions = self._format_final_opinions(all_phases)
            return self._calculate_consensus(final_opinions)
            
        except Exception as e:
            logger.warning(f"计算最终共识度失败: {e}")
            return 0.5
    
    def _count_discussion_rounds(self, all_phases: Dict[str, Any]) -> int:
        """统计讨论轮数"""
        multi_round = all_phases.get("multi_round_discussion", {})
        if multi_round and "total_rounds" in multi_round:
            return multi_round["total_rounds"]
        return 0
