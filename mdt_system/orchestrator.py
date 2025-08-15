"""
MDT系统编排器模块

该模块实现了多学科团队(MDT)系统的核心编排逻辑，负责协调各专科智能体的工作流程。
主要功能包括：
1. 管理MDT会话的完整生命周期
2. 协调多个智能体的异步执行
3. 实现三阶段MDT流程：独立分析、交叉会诊、协调综合
4. 提供进度回调和状态管理
5. 处理错误和异常情况

创建时间: 2025-07-29
版本: 1.0
"""

from typing import Dict, List, Any, Optional, Callable, Generator
from datetime import datetime
import asyncio
import threading
import queue
import logging
from enum import Enum  # legacy import kept if other parts still reference Enum locally
import time

# 导入各专科智能体 - ILD专门化配置
from agents.coordinator_agent import CoordinatorAgent
from agents.pulmonary_agent import PulmonaryAgent
from agents.imaging_agent import ImagingAgent
from agents.pathology_agent import PathologyAgent
from agents.rheumatology_agent import RheumatologyAgent
from agents.data_analysis_agent import DataAnalysisAgent

# 导入工具函数和配置
from utils.helpers import format_agent_response, save_mdt_session, parse_medical_case
from utils.config import config

# 外部分离的阶段与冲突分析组件
from .phases import MDTPhase
from .conflict_analysis import ConflictAnalyzer

# 配置日志记录器
logger = logging.getLogger(__name__)

## 已迁移：阶段枚举见 phases.MDTPhase；保留此处删除记录供历史 diff 追踪。

class MDTOrchestrator:
    """
    MDT系统编排器 - 协调多智能体协作的核心类
    
    该类负责管理整个MDT会话的执行流程，包括：
    
    主要职责：
    1. 初始化和管理所有专科智能体实例
    2. 协调三阶段MDT工作流程的执行
    3. 管理会话状态和数据存储
    4. 提供异步执行和进度回调机制
    5. 处理错误和异常情况
    
    设计模式：
    - 使用了观察者模式来处理进度回调
    - 采用异步编程模型来提高系统响应性
    - 实现了状态机模式来管理会话状态
    
    属性：
        agents (Dict): 存储所有专科智能体实例的字典
        current_phase (MDTPhase): 当前执行阶段
        session_data (Dict): 会话数据存储
        agent_responses (List): 智能体响应结果列表
        progress_callbacks (List): 进度回调函数列表
    """
    
    def __init__(self):
        """
        初始化MDT编排器
        
        创建所有专科智能体实例并初始化会话状态。
        包含以下智能体（专门化for ILD诊断）：
        - coordinator: MDT协调员智能体
        - pulmonary: 呼吸科医生智能体
        - imaging: 影像科医生智能体（专注影像文字描述）
        - pathology: 病理科医生智能体
        - rheumatology: 风湿免疫科医生智能体
        - data_analysis: 数据分析智能体
        """
        # 初始化所有智能体实例 - ILD专门化配置
        # 每个智能体都有特定的专业领域和分析能力
        self.agents = {
            "coordinator": CoordinatorAgent(),        # MDT协调员智能体
            "pulmonary": PulmonaryAgent(),           # 呼吸科医生智能体
            "imaging": ImagingAgent(),               # 影像科医生智能体（处理影像文字描述）
            "pathology": PathologyAgent(),           # 病理科医生智能体
            "rheumatology": RheumatologyAgent(),     # 风湿免疫科医生智能体
            "data_analysis": DataAnalysisAgent()     # 数据分析智能体
        }
        # MDT会话状态管理
        self.current_phase = MDTPhase.INITIALIZATION   # 当前执行阶段
        self.session_data = {}         # 会话数据存储
        self.agent_responses = []      # 智能体响应结果列表
        self.progress_callbacks = []   # 进度回调函数列表

        # 多轮讨论配置
        self.max_discussion_rounds = 3                 # 最大讨论轮数
        self.consensus_threshold = 0.75                # 共识阈值
        self.current_round = 0                         # 当前讨论轮数

        # 冲突/共识分析组件
        self.conflict_analyzer = ConflictAnalyzer(self.agents["coordinator"])
        
    def add_progress_callback(self, callback: Callable):
        """
        添加进度回调函数
        
        允许外部组件（如UI界面）注册回调函数来接收MDT会话的进度更新。
        采用观察者模式，支持多个回调函数同时注册。
        
        Args:
            callback (Callable): 回调函数，应接受三个参数：
                - phase (str): 当前阶段名称
                - message (str): 进度消息
                - data (Optional[Dict]): 相关数据
        
        示例:
            def progress_handler(phase, message, data):
                print(f"阶段 {phase}: {message}")
            
            orchestrator.add_progress_callback(progress_handler)
        """
        self.progress_callbacks.append(callback)
    
    def _notify_progress(self, phase: MDTPhase, message: str, data: Optional[Dict] = None):
        """
        通知进度更新
        
        向所有注册的回调函数发送进度更新通知。
        采用安全调用机制，即使某个回调函数出错也不会影响其他回调。
        
        Args:
            phase (MDTPhase): 当前执行阶段
            message (str): 进度描述消息
            data (Optional[Dict]): 附加数据，可包含具体的执行结果
        
        注意:
            - 所有回调函数都会被调用，即使前面的回调出现异常
            - 回调异常会被记录到日志中，但不会中断执行流程
        """
        for callback in self.progress_callbacks:
            try:
                # 调用回调函数，传递阶段、消息和数据
                callback(phase.value, message, data)
            except Exception as e:
                # 记录回调异常，但不中断执行
                logger.error(f"Progress callback error: {e}")
    
    async def conduct_mdt_session(self, case_data: Dict[str, Any], 
                                 selected_agents: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        执行完整的多轮讨论MDT会话 - 系统的主要入口点
        
        实现新的7步多轮讨论工作流程：
        1. 初始独立分析
        2. 共享和讨论
        3. 冲突检测
        4. 多轮讨论（最多3轮）
        5. 共识评估
        6. 最终协调
        7. 结果输出
        
        Args:
            case_data (Dict[str, Any]): 病例数据字典
            selected_agents (Optional[List[str]]): 参与讨论的智能体列表
                
        Returns:
            Dict[str, Any]: 完整的多轮MDT会话结果
        """
        try:
            # 专家名称映射：中文名称 -> 英文键名
            expert_name_mapping = {
                "呼吸科专家": "pulmonary",
                "影像科专家": "imaging", 
                "病理科专家": "pathology",
                "风湿免疫科专家": "rheumatology",
                "数据分析专家": "data_analysis",
                "协调员": "coordinator"
            }
            
            # 转换选中的专家名称
            if selected_agents:
                mapped_agents = []
                for agent_name in selected_agents:
                    if agent_name in expert_name_mapping:
                        mapped_agents.append(expert_name_mapping[agent_name])
                    elif agent_name in self.agents:
                        # 如果已经是英文键名，直接使用
                        mapped_agents.append(agent_name)
                    else:
                        logger.warning(f"Unknown agent name: {agent_name}")
                selected_agents = mapped_agents
            
            # === 第一步：初始化会话环境 ===
            session_id = f"mdt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            self.session_data = {
                "session_id": session_id,
                "start_time": datetime.now().isoformat(),
                "case_data": case_data,
                "participants": selected_agents or list(self.agents.keys()),
                "phases": {},
                "discussion_rounds": [],
                "final_result": None,
                "max_rounds": self.max_discussion_rounds,
                "consensus_threshold": self.consensus_threshold
            }
            
            # 重置讨论轮数
            self.current_round = 0
            
            logger.info(f"Starting multi-round MDT session: {session_id}")
            self._notify_progress(MDTPhase.INITIALIZATION, "多轮MDT会议开始", {"session_id": session_id})
            
            # 解析病例数据
            parsed_case = parse_medical_case(case_data)
            self.session_data["parsed_case"] = parsed_case
            
            # === 执行新的7步工作流程 ===
            await self._step_1_individual_analysis(parsed_case, selected_agents)
            await self._step_2_sharing_discussion(parsed_case)
            conflict_detected = await self._step_3_conflict_detection(parsed_case)
            
            if conflict_detected:
                await self._step_4_multi_round_discussion(parsed_case)
            
            consensus_reached = await self._step_5_consensus_evaluation()
            await self._step_6_final_coordination(parsed_case, consensus_reached)
            
            # === 完成会话 ===
            self.current_phase = MDTPhase.COMPLETED
            self.session_data["end_time"] = datetime.now().isoformat()
            self.session_data["duration"] = self._calculate_duration()
            
            session_file = save_mdt_session(self.session_data)
            logger.info(f"Multi-round MDT session completed: {session_file}")
            
            self._notify_progress(MDTPhase.COMPLETED, "多轮MDT会议完成", 
                                {"session_file": session_file})
            
            return self.session_data
            
        except Exception as e:
            logger.error(f"Multi-round MDT session error: {e}")
            self._notify_progress(MDTPhase.COMPLETED, f"多轮MDT会议出错: {str(e)}", 
                                {"error": str(e)})
            raise
    
    def conduct_mdt_session_stream(self, case_data: Dict[str, Any], 
                                  selected_agents: Optional[List[str]] = None) -> Generator[Dict[str, Any], None, None]:
        """
        流式执行完整的多轮讨论MDT会话
        
        实现与conduct_mdt_session相同的7步工作流程，但使用流式输出：
        1. 初始独立分析 (流式)
        2. 共享和讨论 (流式)
        3. 冲突检测
        4. 多轮讨论 (流式)
        5. 共识评估
        6. 最终协调 (流式)
        7. 结果输出
        
        Args:
            case_data (Dict[str, Any]): 病例数据字典
            selected_agents (Optional[List[str]]): 参与讨论的智能体列表
                
        Yields:
            Dict[str, Any]: 流式输出的MDT会话结果片段
        """
        try:
            # 专家名称映射：中文名称 -> 英文键名
            expert_name_mapping = {
                "呼吸科专家": "pulmonary",
                "影像科专家": "imaging", 
                "病理科专家": "pathology",
                "风湿免疫科专家": "rheumatology",
                "数据分析专家": "data_analysis",
                "协调员": "coordinator"
            }
            
            # 转换选中的专家名称
            if selected_agents:
                mapped_agents = []
                for agent_name in selected_agents:
                    if agent_name in expert_name_mapping:
                        mapped_agents.append(expert_name_mapping[agent_name])
                    elif agent_name in self.agents:
                        # 如果已经是英文键名，直接使用
                        mapped_agents.append(agent_name)
                    else:
                        logger.warning(f"Unknown agent name: {agent_name}")
                selected_agents = mapped_agents
            
            # === 第一步：初始化会话环境 ===
            session_id = f"mdt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            self.session_data = {
                "session_id": session_id,
                "start_time": datetime.now().isoformat(),
                "case_data": case_data,
                "participants": selected_agents or list(self.agents.keys()),
                "phases": {},
                "discussion_rounds": [],
                "final_result": None,
                "status": "in_progress"
            }
            
            # 发送初始化完成信号
            yield {
                "type": "phase_start",
                "phase": "initialization",
                "message": "会话初始化完成",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
            
            # === 第二步：独立分析阶段 (流式) ===
            yield {
                "type": "phase_start", 
                "phase": "individual_analysis",
                "message": "开始各专科独立分析阶段",
                "timestamp": datetime.now().isoformat()
            }
            
            # 流式执行独立分析
            for result in self._step_1_individual_analysis_stream(case_data, selected_agents):
                yield result
            
            # === 第三步：共享讨论阶段 (流式) ===
            yield {
                "type": "phase_start",
                "phase": "sharing_discussion", 
                "message": "开始专科间初步讨论阶段",
                "timestamp": datetime.now().isoformat()
            }
            
            # 流式执行共享讨论
            for result in self._step_2_sharing_discussion_stream(case_data, selected_agents):
                yield result
                
            # === 第四步：冲突检测阶段 ===
            yield {
                "type": "phase_start",
                "phase": "conflict_detection",
                "message": "开始意见冲突检测",
                "timestamp": datetime.now().isoformat()
            }
            
            conflict_detected = False
            for result in self._step_3_conflict_detection_stream(case_data):
                if result.get("type") == "phase_complete":
                    conflict_detected = result.get("conflict_detected", False)
                yield result
            
            # === 第五步：多轮讨论阶段 (如果需要，流式) ===
            if conflict_detected:
                yield {
                    "type": "phase_start",
                    "phase": "multi_round_discussion",
                    "message": "检测到意见分歧，开始多轮深入讨论",
                    "timestamp": datetime.now().isoformat()
                }
                
                # 流式执行多轮讨论
                for result in self._step_4_multi_round_discussion_stream(case_data, selected_agents):
                    yield result
            else:
                yield {
                    "type": "phase_skip",
                    "phase": "multi_round_discussion", 
                    "message": "专家意见一致，跳过多轮讨论",
                    "timestamp": datetime.now().isoformat()
                }
            
            # === 第六步：共识评估阶段 ===
            yield {
                "type": "phase_start",
                "phase": "consensus_evaluation",
                "message": "开始共识评估",
                "timestamp": datetime.now().isoformat()
            }
            
            consensus_reached = False
            for result in self._step_5_consensus_evaluation_stream():
                if result.get("type") == "phase_complete":
                    consensus_reached = result.get("consensus_reached", False)
                yield result
            
            # === 第七步：最终协调阶段 (流式) ===
            yield {
                "type": "phase_start",
                "phase": "final_coordination",
                "message": "开始最终协调和建议生成",
                "timestamp": datetime.now().isoformat()
            }
            
            # 流式执行最终协调
            for result in self._step_6_final_coordination_stream(case_data, consensus_reached, selected_agents):
                yield result
            
            # === 第八步：完成会话 ===
            self.session_data["end_time"] = datetime.now().isoformat()
            self.session_data["status"] = "completed"
            
            # 计算会话时长
            start_time = datetime.fromisoformat(self.session_data["start_time"])
            end_time = datetime.fromisoformat(self.session_data["end_time"])
            duration = str(end_time - start_time)
            self.session_data["duration"] = duration
            
            # 保存会话数据
            session_file = save_mdt_session(self.session_data)
            logger.info(f"Stream MDT session completed: {session_file}")
            
            # 发送最终完成信号
            yield {
                "type": "session_complete",
                "phase": "completed",
                "message": "多轮MDT会议完成",
                "session_data": self.session_data,
                "session_file": session_file,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Stream MDT session error: {e}")
            import traceback
            traceback.print_exc()
            yield {
                "type": "session_error",
                "phase": "error",
                "message": f"多轮MDT会议出错: {str(e)}",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            raise
    
    async def _step_1_individual_analysis(self, case_data: Dict[str, Any], 
                                         selected_agents: Optional[List[str]]):
        """
        步骤1：各专科独立分析
        
        各专科医生智能体独立分析同一病例，不受其他意见影响。
        这是多轮讨论流程的起始阶段。
        
        Args:
            case_data (Dict[str, Any]): 解析后的病例数据
            selected_agents (Optional[List[str]]): 选择参与的智能体列表
        """
        self.current_phase = MDTPhase.INDIVIDUAL_ANALYSIS
        self._notify_progress(self.current_phase, "各专科医生独立分析中...")
        
        phase_results = {}
        
        # 确定参与分析的智能体（排除协调员）
        active_agents = selected_agents or ["pulmonary", "imaging", "pathology", "rheumatology", "data_analysis"]
        
        # 创建并行任务
        tasks = []
        for agent_name in active_agents:
            if agent_name in self.agents and agent_name != "coordinator":
                agent = self.agents[agent_name]
                task = asyncio.create_task(
                    self._run_agent_analysis(agent, case_data, [])
                )
                tasks.append((agent_name, task))
        
        # 等待所有分析完成并收集结果
        for agent_name, task in tasks:
            try:
                result = await task
                phase_results[agent_name] = result
                self.agent_responses.append(result)
                
                agent_display_name = result.get('agent') or result.get('agent_name', '未知智能体')
                self._notify_progress(self.current_phase, 
                                    f"{agent_display_name}独立分析完成", result)
                                    
            except Exception as e:
                logger.error(f"Agent {agent_name} analysis failed: {e}")
                error_result = format_agent_response(
                    agent_name, f"分析过程出现错误: {str(e)}", datetime.now()
                )
                phase_results[agent_name] = error_result
        
        self.session_data["phases"]["individual_analysis"] = phase_results
        logger.info(f"Step 1 completed with {len(phase_results)} agent responses")
    
    async def _step_2_sharing_discussion(self, case_data: Dict[str, Any]):
        """
        步骤2：共享和初步讨论
        
        各专科医生查看其他专科的意见，进行初步的交叉讨论。
        这是多轮讨论前的预备阶段。
        """
        self.current_phase = MDTPhase.SHARING_DISCUSSION
        self._notify_progress(self.current_phase, "专科间初步讨论中...")
        
        phase_results = {}
        
        # 为每个智能体进行初步讨论
        for agent_name, agent in self.agents.items():
            if agent_name == "coordinator":
                continue
                
            try:
                # 收集其他专家的意见（排除自己的）
                other_opinions = [resp for resp in self.agent_responses 
                                if resp.get("agent") != agent.name]
                
                if other_opinions:
                    # 执行初步讨论分析
                    result = await self._run_agent_analysis(agent, case_data, other_opinions)
                    phase_results[agent_name] = result
                    
                    # 更新全局响应列表
                    for i, resp in enumerate(self.agent_responses):
                        resp_agent = resp.get("agent") or resp.get("agent_name")
                        if resp_agent == agent.name:
                            self.agent_responses[i] = result
                            break
                    
                    agent_display_name = result.get('agent') or result.get('agent_name', '未知智能体')
                    self._notify_progress(self.current_phase, 
                                        f"{agent_display_name}初步讨论完成", result)
                
            except Exception as e:
                logger.error(f"Sharing discussion failed for {agent_name}: {e}")
        
        self.session_data["phases"]["sharing_discussion"] = phase_results
        logger.info(f"Step 2 completed with {len(phase_results)} updated responses")
    
    async def _step_3_conflict_detection(self, case_data: Dict[str, Any]) -> bool:
        """
        步骤3：冲突检测
        
        使用协调员智能体检测各专科意见之间的冲突和分歧。
        
        Returns:
            bool: 是否检测到显著冲突，决定是否需要进入多轮讨论
        """
        self.current_phase = MDTPhase.CONFLICT_DETECTION
        self._notify_progress(self.current_phase, "检测专家意见冲突中...")
        
        try:
            coordinator = self.agents["coordinator"]
            
            # 准备当前所有专家意见
            current_opinions = []
            for resp in self.agent_responses:
                if isinstance(resp, dict) and resp.get('response'):
                    current_opinions.append({
                        'agent': resp.get('agent', ''),
                        'response': resp.get('response', ''),
                        'timestamp': resp.get('timestamp', ''),
                        'specialty': resp.get('specialty', '')
                    })
            
            # 新：调用外部冲突分析组件
            conflict_result = await self._run_conflict_detection(coordinator, case_data, current_opinions)
            conflicts_detected = self._parse_conflict_result(conflict_result)
            conflict_data = conflict_result
            
            self.session_data["phases"]["conflict_detection"] = conflict_data
            
            if conflicts_detected:
                self._notify_progress(self.current_phase, 
                                    f"检测到显著意见分歧，将进入多轮讨论", conflict_data)
            else:
                self._notify_progress(self.current_phase, 
                                    f"未检测到显著冲突，可直接进入最终协调", conflict_data)
            
            logger.info(f"Step 3 completed, conflicts detected: {conflicts_detected}")
            return conflicts_detected
            
        except Exception as e:
            logger.error(f"Conflict detection failed: {e}")
            # 如果冲突检测失败，默认进行多轮讨论
            return True
    
    async def _step_4_multi_round_discussion(self, case_data: Dict[str, Any]):
        """
        步骤4：多轮讨论（最多3轮）
        
        当检测到冲突时，进行多轮的深入讨论，直到达成共识或达到最大轮数。
        """
        self.current_phase = MDTPhase.MULTI_ROUND_DISCUSSION
        self._notify_progress(self.current_phase, "开始多轮深入讨论...")
        
        discussion_rounds = []
        
        for round_num in range(1, self.max_discussion_rounds + 1):
            self.current_round = round_num
            self._notify_progress(self.current_phase, f"第{round_num}轮讨论开始...")
            
            round_results = {}
            
            # 每一轮讨论中，所有智能体再次分析
            for agent_name, agent in self.agents.items():
                if agent_name == "coordinator":
                    continue
                    
                try:
                    # 包含所有之前轮次的意见和当前轮次已完成的意见
                    all_opinions = []
                    
                    # 添加当前轮次已完成的其他意见
                    for other_agent, other_result in round_results.items():
                        if other_agent != agent_name and isinstance(other_result, dict):
                            all_opinions.append({
                                'agent': other_result.get('agent', ''),
                                'response': other_result.get('response', ''),
                                'round': round_num,
                                'timestamp': other_result.get('timestamp', '')
                            })
                    
                    # 添加之前轮次的意见
                    for prev_round in discussion_rounds:
                        for prev_agent, prev_result in prev_round.items():
                            if isinstance(prev_result, dict):
                                all_opinions.append({
                                    'agent': prev_result.get('agent', ''),
                                    'response': prev_result.get('response', ''),
                                    'round': prev_round.get('round', 0),
                                    'timestamp': prev_result.get('timestamp', '')
                                })
                    
                    # 执行本轮讨论
                    result = await self._run_agent_discussion_round(agent, case_data, all_opinions, round_num)
                    round_results[agent_name] = result
                    
                    agent_display_name = result.get('agent') or result.get('agent_name', '未知智能体')
                    self._notify_progress(self.current_phase, 
                                        f"第{round_num}轮：{agent_display_name}讨论完成", result)
                    
                except Exception as e:
                    logger.error(f"Round {round_num} discussion failed for {agent_name}: {e}")
            
            # 记录本轮结果
            round_data = {
                "round": round_num,
                "results": round_results,
                "timestamp": datetime.now().isoformat()
            }
            discussion_rounds.append(round_data)
            
            # 评估本轮后的共识情况
            round_consensus = await self._evaluate_round_consensus(round_results)
            round_data["consensus_score"] = round_consensus
            
            self._notify_progress(self.current_phase, 
                                f"第{round_num}轮讨论完成，共识度: {round_consensus:.2f}")
            
            # 如果达到了较高的共识，可以提前结束
            if round_consensus >= self.consensus_threshold:
                self._notify_progress(self.current_phase, 
                                    f"第{round_num}轮后达成共识，提前结束讨论")
                break
        
        self.session_data["phases"]["multi_round_discussion"] = {
            "total_rounds": len(discussion_rounds),
            "rounds": discussion_rounds,
            "max_rounds": self.max_discussion_rounds
        }
        
        # 更新agent_responses为最后一轮的结果
        if discussion_rounds:
            last_round = discussion_rounds[-1]["results"]
            self.agent_responses = list(last_round.values())
        
        logger.info(f"Step 4 completed with {len(discussion_rounds)} rounds")
    
    async def _step_5_consensus_evaluation(self) -> bool:
        """
        步骤5：共识评估
        
        评估当前各专科意见的共识程度。
        
        Returns:
            bool: 是否达成了足够的共识
        """
        self.current_phase = MDTPhase.CONSENSUS_EVALUATION
        self._notify_progress(self.current_phase, "评估专家共识程度...")
        
        try:
            coordinator = self.agents["coordinator"]
            
            # 收集当前所有意见
            current_opinions = []
            for resp in self.agent_responses:
                if isinstance(resp, dict) and resp.get('response'):
                    current_opinions.append({
                        'agent': resp.get('agent', ''),
                        'response': resp.get('response', ''),
                        'timestamp': resp.get('timestamp', ''),
                        'specialty': resp.get('specialty', '')
                    })
            
            # 使用协调员评估共识（结构留存，未来可替换外部 analyzer.evaluate_consensus）
            consensus_result = await self._run_consensus_evaluation(coordinator, current_opinions)
            consensus_score = consensus_result.get('consensus_score', 0.0)
            consensus_reached = consensus_score >= self.consensus_threshold
            
            consensus_data = {
                "consensus_score": consensus_score,
                "consensus_reached": consensus_reached,
                "threshold": self.consensus_threshold,
                "evaluation": consensus_result,
                "opinions_count": len(current_opinions)
            }
            
            self.session_data["phases"]["consensus_evaluation"] = consensus_data
            
            if consensus_reached:
                self._notify_progress(self.current_phase, 
                                    f"达成共识，共识度: {consensus_score:.2f}", consensus_data)
            else:
                self._notify_progress(self.current_phase, 
                                    f"共识不足，共识度: {consensus_score:.2f}", consensus_data)
            
            logger.info(f"Step 5 completed, consensus reached: {consensus_reached}, score: {consensus_score:.2f}")
            return consensus_reached
            
        except Exception as e:
            logger.error(f"Consensus evaluation failed: {e}")
            return False
    
    async def _step_6_final_coordination(self, case_data: Dict[str, Any], consensus_reached: bool):
        """
        步骤6：最终协调
        
        由协调员生成最终的综合建议和治疗方案。
        
        Args:
            case_data (Dict[str, Any]): 病例数据
            consensus_reached (bool): 是否达成了共识
        """
        self.current_phase = MDTPhase.FINAL_COORDINATION
        self._notify_progress(self.current_phase, "生成最终MDT建议...")
        
        try:
            coordinator = self.agents["coordinator"]
            
            # 准备传递给协调员的所有阶段数据
            all_phases = {
                "individual_analysis": self.session_data.get("phases", {}).get("individual_analysis", {}),
                "sharing_discussion": self.session_data.get("phases", {}).get("sharing_discussion", {}),
                "conflict_detection": self.session_data.get("phases", {}).get("conflict_detection", {}),
                "multi_round_discussion": self.session_data.get("phases", {}).get("multi_round_discussion", {}),
                "consensus_evaluation": self.session_data.get("phases", {}).get("consensus_evaluation", {})
            }
            
            # 执行最终协调
            coordination_result = await self._run_final_coordination(
                coordinator, case_data, all_phases, consensus_reached
            )
            
            # 保存最终协调结果
            self.session_data["phases"]["final_coordination"] = coordination_result
            self.session_data["final_result"] = coordination_result
            
            self._notify_progress(self.current_phase, "最终MDT建议生成完成", coordination_result)
            logger.info("Step 6 final coordination completed")
            
        except Exception as e:
            logger.error(f"Final coordination failed: {e}")
            error_result = format_agent_response(
                "协调员", f"最终协调过程出现错误: {str(e)}", datetime.now()
            )
            self.session_data["phases"]["final_coordination"] = error_result
            self.session_data["final_result"] = error_result
    
    async def _run_agent_analysis(self, agent, case_data: Dict[str, Any], 
                                other_opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        运行智能体分析（异步包装器）
        
        将同步的智能体分析方法包装为异步操作，使其能够在asyncio事件循环中执行。
        这是一个关键的适配器方法，解决了同步智能体代码与异步编排器之间的接口问题。
        
        技术实现：
        - 使用ThreadPoolExecutor在后台线程中执行同步代码
        - 不会阻塞主事件循环，保持系统响应性
        - 支持并发执行多个智能体分析
        
        Args:
            agent: 智能体实例，必须实现analyze_case方法
            case_data (Dict[str, Any]): 病例数据
            other_opinions (List[Dict[str, Any]]): 其他智能体的意见列表
                - 在独立分析阶段为空列表
                - 在交叉会诊阶段包含其他专科的意见
                
        Returns:
            Dict[str, Any]: 智能体分析结果，包含：
                - agent: 智能体名称
                - specialty: 专科名称  
                - response: 分析结果文本
                - timestamp: 分析时间
                - confidence: 置信度等其他元数据
                
        注意事项：
            - 这个方法确保了线程安全
            - 异常会被正确传播到调用者
        """
        # 获取当前事件循环
        loop = asyncio.get_event_loop()
        
        # 在线程池中运行同步的智能体分析方法
        # 这样不会阻塞主事件循环
        return await loop.run_in_executor(
            None,                           # 使用默认的ThreadPoolExecutor
            agent.analyze_case,             # 要执行的同步方法
            case_data,                      # 传递给方法的参数
            other_opinions
        )
    
    async def _run_coordinator_analysis(self, coordinator, case_data: Dict[str, Any], 
                                      phase_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行协调员分析（异步包装器）
        
        专门为协调员智能体设计的异步包装器。协调员的工作方式与普通智能体不同，
        它需要处理所有阶段的结构化结果而不是简单的意见列表。
        
        与_run_agent_analysis的区别：
        - 调用的是coordinate_mdt_discussion方法而不是analyze_case
        - 第二个参数是phase_results字典而不是other_opinions列表
        - 专门处理MDT协调逻辑
        
        Args:
            coordinator: 协调员智能体实例
            case_data (Dict[str, Any]): 病例数据
            phase_results (Dict[str, Any]): 前两阶段的结构化结果
                - individual_analysis: 独立分析阶段结果
                - cross_consultation: 交叉会诊阶段结果
                
        Returns:
            Dict[str, Any]: 协调员的最终分析结果
            
        这个方法的设计解决了之前的数据格式错误问题。
        """
        # 获取当前事件循环
        loop = asyncio.get_event_loop()
        
        # 在线程池中运行协调员的专门方法
        return await loop.run_in_executor(
            None,                                    # 使用默认线程池
            coordinator.coordinate_mdt_discussion,   # 协调员专用方法
            case_data,                              # 病例数据
            phase_results                           # 结构化的阶段结果
        )
    
    def _calculate_duration(self) -> str:
        """
        计算会话持续时间
        
        根据会话的开始和结束时间计算总持续时间。
        这个信息用于性能监控和用户反馈。
        
        Returns:
            str: 持续时间字符串，格式如 "0:02:35.123456"
                 如果时间信息不完整则返回 "unknown"
                 
        时间格式：
            - 使用ISO 8601格式存储时间戳
            - 计算结果为timedelta对象的字符串表示
        """
        # 检查是否有完整的时间信息
        if "start_time" in self.session_data and "end_time" in self.session_data:
            # 解析ISO格式的时间戳
            start = datetime.fromisoformat(self.session_data["start_time"])
            end = datetime.fromisoformat(self.session_data["end_time"])
            
            # 计算时间差
            duration = end - start
            return str(duration)
        
        # 时间信息不完整
        return "unknown"
    
    def get_session_status(self) -> Dict[str, Any]:
        """
        获取当前会话状态
        
        提供会话的实时状态信息，用于监控和调试。
        这个方法可以在会话执行过程中的任何时候调用。
        
        Returns:
            Dict[str, Any]: 会话状态信息，包含：
                - session_id: 会话唯一标识符
                - current_phase: 当前执行阶段名称
                - participants: 参与的智能体列表
                - completed_phases: 已完成的阶段列表
                - agent_responses_count: 收集到的智能体响应数量
                - start_time: 会话开始时间
                
        用途：
            - UI界面显示进度
            - 调试和日志记录
            - 性能监控
        """
        return {
            "session_id": self.session_data.get("session_id"),
            "current_phase": self.current_phase.value,
            "participants": self.session_data.get("participants", []),
            "completed_phases": list(self.session_data.get("phases", {}).keys()),
            "agent_responses_count": len(self.agent_responses),
            "start_time": self.session_data.get("start_time")
        }
    
    def get_agent_statistics(self) -> Dict[str, Any]:
        """
        获取智能体统计信息
        
        收集所有智能体的性能和使用统计数据。
        这些信息用于系统优化和性能分析。
        
        Returns:
            Dict[str, Any]: 以智能体名称为键的统计信息字典
                每个智能体的统计信息由其get_summary_statistics方法提供
                
        典型用途：
            - 监控各智能体的响应时间
            - 分析token使用量
            - 评估系统性能
            - 成本分析
        """
        stats = {}
        for name, agent in self.agents.items():
            # 调用每个智能体的统计方法
            stats[name] = agent.get_summary_statistics()
        return stats
    
    def reset_session(self):
        """
        重置会话状态
        
        清空所有会话相关的数据，将编排器恢复到初始状态。
        这个方法在开始新会话前调用，确保状态的干净性。
        
        重置内容：
            - 当前阶段回到INITIALIZATION
            - 清空会话数据
            - 清空智能体响应列表
            - 重置讨论轮数
            
        注意：
            - 不会重置智能体实例本身
            - 不会清除进度回调函数
            - 主要用于多次会话之间的状态清理
        """
        self.current_phase = MDTPhase.INITIALIZATION
        self.session_data = {}
        self.agent_responses = []
        self.current_round = 0
        logger.info("MDT session reset")
    
    # === 新增的辅助方法 ===
    
    async def _run_conflict_detection(self, coordinator, case_data: Dict[str, Any], opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """运行冲突检测分析 (委派给 ConflictAnalyzer / 仍保持异步接口)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.conflict_analyzer.detect,
            case_data,
            opinions
        )
    
    def _parse_conflict_result(self, conflict_result: Dict[str, Any]) -> bool:
        """解析冲突检测结果 (可替换为更复杂的解析逻辑)"""
        try:
            if 'conflicts_detected' in conflict_result:
                return conflict_result['conflicts_detected']
            if 'conflict_detected' in conflict_result:
                return conflict_result['conflict_detected']
            text = (conflict_result.get('response') or '').lower()
            for kw in ['冲突', '分歧', '矛盾', '不一致']:
                if kw in text:
                    return True
            score = conflict_result.get('consensus_score')
            if score is not None:
                return score < self.consensus_threshold
            return False
        except Exception:
            return True
    
    async def _run_agent_discussion_round(self, agent, case_data: Dict[str, Any], 
                                        all_opinions: List[Dict[str, Any]], 
                                        round_num: int) -> Dict[str, Any]:
        """运行智能体的讨论轮次"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            agent.discuss_round,
            case_data,
            all_opinions,
            round_num
        )
    
    async def _evaluate_round_consensus(self, round_results: Dict[str, Any]) -> float:
        """评估单轮讨论后的共识度"""
        try:
            if not round_results:
                return 0.0
            
            # 简化的共识度计算
            responses = []
            for result in round_results.values():
                if isinstance(result, dict) and result.get('response'):
                    responses.append(result['response'])
            
            if len(responses) < 2:
                return 1.0
            
            # 计算关键词重叠度
            all_words = set()
            word_counts = {}
            
            for response in responses:
                words = set(response.lower().split())
                all_words.update(words)
                for word in words:
                    word_counts[word] = word_counts.get(word, 0) + 1
            
            # 计算共同词汇比例
            common_words = sum(1 for count in word_counts.values() if count >= len(responses) * 0.5)
            consensus_score = common_words / max(len(all_words), 1)
            
            return min(consensus_score, 1.0)
            
        except Exception as e:
            logger.warning(f"评估轮次共识度失败: {e}")
            return 0.5
    
    async def _run_consensus_evaluation(self, coordinator, 
                                      opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """运行共识评估"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            coordinator.evaluate_consensus,
            opinions
        )
    
    async def _run_final_coordination(self, coordinator, case_data: Dict[str, Any], 
                                    all_phases: Dict[str, Any], 
                                    consensus_reached: bool) -> Dict[str, Any]:
        """运行最终协调"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            coordinator.final_coordination,
            case_data,
            all_phases,
            consensus_reached
        )
    
    # ==================== 流式执行方法 ====================
    
    def _step_1_individual_analysis_stream(self, case_data: Dict[str, Any], 
                                         selected_agents: Optional[List[str]] = None) -> Generator[Dict[str, Any], None, None]:
        """流式执行第一步：各专科独立分析（并行版本）"""
        specialist_agents = [name for name in (selected_agents or self.agents.keys()) if name != "coordinator"]
        analysis_results: Dict[str, Dict[str, Any]] = {}
        results_lock = threading.Lock()
        event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()

        def worker(agent_key: str):
            agent = self.agents[agent_key]
            try:
                event_queue.put({
                    "type": "agent_start",
                    "phase": "individual_analysis",
                    "agent": agent.name,
                    "specialty": agent.specialty,
                    "message": f"{agent.name}开始独立分析",
                    "timestamp": datetime.now().isoformat()
                })
                for chunk in agent.analyze_case(case_data, stream=True):
                    if not isinstance(chunk, dict):
                        logger.error(f"Agent {agent_key} ({agent.name}) returned non-dict chunk: {type(chunk)} - {chunk}")
                        continue
                    if chunk.get("is_complete"):
                        standard_result = {
                            "agent": chunk.get("agent", agent.name),
                            "response": chunk.get("response", chunk.get("full_response", "")),
                            "specialty": agent.specialty,
                            "phase": "individual_analysis",
                            "timestamp": datetime.now().isoformat()
                        }
                        with results_lock:
                            analysis_results[agent_key] = standard_result
                        event_queue.put({
                            "type": "agent_complete",
                            "phase": "individual_analysis",
                            "agent": agent.name,
                            "specialty": agent.specialty,
                            "result": standard_result,
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        event_queue.put({
                            "type": "agent_chunk",
                            "phase": "individual_analysis",
                            "agent": agent.name,
                            "specialty": agent.specialty,
                            "chunk": chunk.get("response_chunk", ""),
                            "full_response": chunk.get("full_response", ""),
                            "timestamp": datetime.now().isoformat()
                        })
            except Exception as e:
                logger.error(f"Parallel individual analysis error for {agent_key}: {e}")
            finally:
                event_queue.put({"type": "internal_done", "agent_key": agent_key})

        threads = [threading.Thread(target=worker, args=(name,), daemon=True) for name in specialist_agents]
        for t in threads:
            t.start()

        finished = 0
        total = len(threads)
        while finished < total:
            event = event_queue.get()
            if event.get("type") == "internal_done":
                finished += 1
                continue
            yield event

        # 所有线程完成
        self.session_data["phases"]["individual_analysis"] = analysis_results
        yield {
            "type": "phase_complete",
            "phase": "individual_analysis",
            "message": "独立分析阶段完成",
            "results": analysis_results,
            "timestamp": datetime.now().isoformat()
        }
    
    def _step_2_sharing_discussion_stream(self, case_data: Dict[str, Any], 
                                         selected_agents: Optional[List[str]] = None) -> Generator[Dict[str, Any], None, None]:
        """流式执行第二步：专科间初步讨论（并行版本）"""
        individual_results = list(self.session_data["phases"].get("individual_analysis", {}).values())
        specialist_agents = [name for name in (selected_agents or self.agents.keys()) if name != "coordinator"]
        sharing_results: Dict[str, Dict[str, Any]] = {}
        results_lock = threading.Lock()
        event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()

        def worker(agent_key: str):
            agent = self.agents[agent_key]
            try:
                event_queue.put({
                    "type": "agent_start",
                    "phase": "sharing_discussion",
                    "agent": agent.name,
                    "specialty": agent.specialty,
                    "message": f"{agent.name}开始参与讨论",
                    "timestamp": datetime.now().isoformat()
                })
                for chunk in agent.analyze_case(case_data, individual_results, stream=True):
                    if chunk.get("is_complete"):
                        standard_result = {
                            "agent": chunk.get("agent", agent.name),
                            "response": chunk.get("response", chunk.get("full_response", "")),
                            "specialty": agent.specialty,
                            "phase": "sharing_discussion",
                            "timestamp": datetime.now().isoformat()
                        }
                        with results_lock:
                            sharing_results[agent_key] = standard_result
                        event_queue.put({
                            "type": "agent_complete",
                            "phase": "sharing_discussion",
                            "agent": agent.name,
                            "specialty": agent.specialty,
                            "result": standard_result,
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        event_queue.put({
                            "type": "agent_chunk",
                            "phase": "sharing_discussion",
                            "agent": agent.name,
                            "specialty": agent.specialty,
                            "chunk": chunk.get("response_chunk", ""),
                            "full_response": chunk.get("full_response", ""),
                            "timestamp": datetime.now().isoformat()
                        })
            except Exception as e:
                logger.error(f"Parallel sharing discussion error for {agent_key}: {e}")
            finally:
                event_queue.put({"type": "internal_done", "agent_key": agent_key})

        threads = [threading.Thread(target=worker, args=(name,), daemon=True) for name in specialist_agents]
        for t in threads:
            t.start()

        finished = 0
        total = len(threads)
        while finished < total:
            event = event_queue.get()
            if event.get("type") == "internal_done":
                finished += 1
                continue
            yield event

        self.session_data["phases"]["sharing_discussion"] = sharing_results
        yield {
            "type": "phase_complete",
            "phase": "sharing_discussion",
            "message": "初步讨论阶段完成",
            "results": sharing_results,
            "timestamp": datetime.now().isoformat()
        }
    
    def _step_3_conflict_detection_stream(self, case_data: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """流式执行第三步：冲突检测"""
        coordinator = self.agents["coordinator"]
        all_opinions = []
        
        # 收集所有意见
        for phase_name in ["individual_analysis", "sharing_discussion"]:
            if phase_name in self.session_data["phases"]:
                phase_results = self.session_data["phases"][phase_name]
                for result in phase_results.values():
                    if isinstance(result, dict) and "agent" in result:
                        all_opinions.append(result)
        
        yield {
            "type": "agent_start",
            "phase": "conflict_detection",
            "agent": coordinator.name,
            "message": "协调员开始冲突检测分析",
            "timestamp": datetime.now().isoformat()
        }
        
        # ===== 真正流式：直接流式调用 LLM =====
        try:
            opinions_text = coordinator._format_other_opinions(all_opinions)
            conflict_prompt = f"""
作为MDT协调员，请分析以下专家意见中是否存在显著的冲突或分歧：

【病例信息】
患者ID: {case_data.get('patient_id', 'N/A')}
主要症状: {case_data.get('symptoms', 'N/A')}

【专家意见】
{opinions_text}

请分析：
1. 诊断方面是否有分歧
2. 治疗方案是否有冲突
3. 风险评估是否不一致
4. 预后判断是否有差异

如果发现显著冲突，请说明具体的分歧点。
如果没有显著冲突，请说明专家意见的一致性。

请以"检测结果："开头，明确回答是否有显著冲突。
"""
            full_response = ""
            # 底层流式生成器（逐小块内容）
            for piece in coordinator._call_llm(conflict_prompt, stream=True):
                if not piece:
                    continue
                full_response += piece
                yield {
                    "type": "agent_chunk",
                    "phase": "conflict_detection",
                    "agent": coordinator.name,
                    "chunk": piece,
                    "full_response": full_response,
                    "timestamp": datetime.now().isoformat()
                }
            # 生成最终结果结构
            conflict_detected = coordinator._analyze_conflict_response(full_response)
            consensus_score = coordinator._calculate_consensus(opinions_text)
            conflict_result = {
                "agent": coordinator.name,
                "conflict_detected": conflict_detected,
                "conflicts_detected": conflict_detected,
                "conflict_analysis": full_response,
                "response": full_response,
                "consensus_score": consensus_score,
                "opinions_analyzed": len(all_opinions),
                "timestamp": datetime.now().isoformat()
            }
            yield {
                "type": "agent_complete",
                "phase": "conflict_detection",
                "agent": coordinator.name,
                "result": conflict_result,
                "timestamp": datetime.now().isoformat()
            }
            self.session_data["phases"]["conflict_detection"] = conflict_result
            yield {
                "type": "phase_complete",
                "phase": "conflict_detection",
                "conflict_detected": conflict_detected,
                "result": conflict_result,
                "message": "检测到意见分歧" if conflict_detected else "专家意见基本一致",
                "timestamp": datetime.now().isoformat()
            }
            # 结束：不直接 return 布尔值，生成器自然结束
            return
        except Exception as e:
            logger.error(f"Streaming conflict detection failed: {e}")
            error_result = {
                "agent": coordinator.name,
                "conflict_detected": True,
                "response": f"冲突检测流式过程出现错误: {e}",
                "timestamp": datetime.now().isoformat()
            }
            yield {
                "type": "agent_complete",
                "phase": "conflict_detection",
                "agent": coordinator.name,
                "result": error_result,
                "timestamp": datetime.now().isoformat()
            }
            self.session_data["phases"]["conflict_detection"] = error_result
            yield {
                "type": "phase_complete",
                "phase": "conflict_detection",
                "conflict_detected": True,
                "result": error_result,
                "message": "冲突检测失败",
                "timestamp": datetime.now().isoformat()
            }
            return
    
    def _step_4_multi_round_discussion_stream(self, case_data: Dict[str, Any], 
                                            selected_agents: Optional[List[str]] = None) -> Generator[Dict[str, Any], None, None]:
        """流式执行第四步：多轮讨论"""
        specialist_agents = [name for name in (selected_agents or self.agents.keys()) 
                           if name != "coordinator"]
        discussion_rounds = []
        
        for round_num in range(1, self.max_discussion_rounds + 1):
            yield {
                "type": "round_start",
                "phase": "multi_round_discussion",
                "round": round_num,
                "message": f"开始第{round_num}轮讨论",
                "timestamp": datetime.now().isoformat()
            }
            
            round_results = {"round": round_num, "results": {}}
            
            # 获取所有之前的标准格式专家意见
            all_previous_opinions = []
            for phase_name, phase_results in self.session_data["phases"].items():
                if phase_name in ["individual_analysis", "sharing_discussion"]:  # 只包含专家分析阶段
                    if isinstance(phase_results, dict):
                        for result in phase_results.values():
                            if isinstance(result, dict) and "agent" in result:
                                all_previous_opinions.append(result)
            
            # 添加之前轮次的讨论结果
            for round_data in discussion_rounds:
                for result in round_data["results"].values():
                    if isinstance(result, dict) and "agent" in result:
                        all_previous_opinions.append(result)
            
            # 每个专家进行本轮讨论
            for agent_name in specialist_agents:
                agent = self.agents[agent_name]
                
                yield {
                    "type": "agent_start",
                    "phase": "multi_round_discussion",
                    "round": round_num,
                    "agent": agent.name,
                    "specialty": agent.specialty,
                    "message": f"{agent.name}开始第{round_num}轮讨论",
                    "timestamp": datetime.now().isoformat()
                }
                
                # 流式获取讨论结果
                for chunk in agent.analyze_case(case_data, all_previous_opinions, stream=True):
                    if chunk.get("is_complete"):
                        # 提取标准格式的讨论结果
                        standard_result = {
                            "agent": chunk.get("agent", agent.name),
                            "response": chunk.get("response", chunk.get("full_response", "")),
                            "specialty": agent.specialty,
                            "phase": "multi_round_discussion",
                            "round": round_num,
                            "timestamp": datetime.now().isoformat()
                        }
                        round_results["results"][agent_name] = standard_result
                        yield {
                            "type": "agent_complete",
                            "phase": "multi_round_discussion",
                            "round": round_num,
                            "agent": agent.name,
                            "specialty": agent.specialty,
                            "result": standard_result,
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        yield {
                            "type": "agent_chunk",
                            "phase": "multi_round_discussion",
                            "round": round_num,
                            "agent": agent.name,
                            "specialty": agent.specialty,
                            "chunk": chunk.get("response_chunk", ""),
                            "full_response": chunk.get("full_response", ""),
                            "timestamp": datetime.now().isoformat()
                        }
            
            # 评估本轮共识度
            responses = [result.get("response", "") for result in round_results["results"].values()]
            consensus_score = self._calculate_simple_consensus(responses)
            round_results["consensus_score"] = consensus_score
            
            discussion_rounds.append(round_results)
            
            yield {
                "type": "round_complete",
                "phase": "multi_round_discussion", 
                "round": round_num,
                "consensus_score": consensus_score,
                "message": f"第{round_num}轮讨论完成，共识度: {consensus_score:.2f}",
                "timestamp": datetime.now().isoformat()
            }
            
            # 如果达到共识阈值，提前结束
            if consensus_score >= self.consensus_threshold:
                yield {
                    "type": "rounds_complete",
                    "phase": "multi_round_discussion",
                    "total_rounds": round_num,
                    "message": f"在第{round_num}轮达成共识，结束讨论",
                    "timestamp": datetime.now().isoformat()
                }
                break
        
        # 保存多轮讨论结果
        self.session_data["phases"]["multi_round_discussion"] = {
            "total_rounds": len(discussion_rounds),
            "rounds": discussion_rounds
        }
        
        yield {
            "type": "phase_complete",
            "phase": "multi_round_discussion",
            "total_rounds": len(discussion_rounds),
            "results": discussion_rounds,
            "timestamp": datetime.now().isoformat()
        }
    
    def _step_5_consensus_evaluation_stream(self) -> Generator[Dict[str, Any], None, None]:
        """流式执行第五步：共识评估"""
        coordinator = self.agents["coordinator"]
        
        # 收集所有阶段的意见
        all_opinions = []
        for phase_results in self.session_data["phases"].values():
            if isinstance(phase_results, dict):
                if "rounds" in phase_results:  # 多轮讨论结果
                    for round_data in phase_results["rounds"]:
                        for result in round_data["results"].values():
                            if isinstance(result, dict) and "agent" in result:
                                all_opinions.append(result)
                else:  # 其他阶段结果
                    for result in phase_results.values():
                        if isinstance(result, dict) and "agent" in result:
                            all_opinions.append(result)
        
        yield {
            "type": "agent_start",
            "phase": "consensus_evaluation",
            "agent": coordinator.name,
            "message": "协调员开始共识评估",
            "timestamp": datetime.now().isoformat()
        }
        
        # ===== 真正流式：直接流式调用 LLM =====
        try:
            opinions_text = coordinator._format_other_opinions(all_opinions)
            consensus_prompt = f"""
作为MDT协调员，请评估以下专家意见的共识程度：

【专家意见】
{opinions_text}

请从以下几个维度评估共识程度：
1. 诊断一致性（0-1分）
2. 治疗方案一致性（0-1分）
3. 风险评估一致性（0-1分）
4. 预后判断一致性（0-1分）

请给出综合共识评分（0-1分，1分表示完全一致），并说明共识与分歧要点。
"""
            full_response = ""
            for piece in coordinator._call_llm(consensus_prompt, stream=True):
                if not piece:
                    continue
                full_response += piece
                yield {
                    "type": "agent_chunk",
                    "phase": "consensus_evaluation",
                    "agent": coordinator.name,
                    "chunk": piece,
                    "full_response": full_response,
                    "timestamp": datetime.now().isoformat()
                }
            llm_score = coordinator._extract_consensus_score(full_response)
            calculated_score = coordinator._calculate_consensus(opinions_text)
            final_score = (llm_score + calculated_score) / 2
            threshold = 0.75
            consensus_reached = final_score >= threshold
            consensus_result = {
                "agent": coordinator.name,
                "consensus_score": final_score,
                "consensus_reached": consensus_reached,
                "threshold": threshold,
                "evaluation": full_response,
                "response": full_response,
                "llm_score": llm_score,
                "calculated_score": calculated_score,
                "opinions_count": len(all_opinions),
                "timestamp": datetime.now().isoformat()
            }
            yield {
                "type": "agent_complete",
                "phase": "consensus_evaluation",
                "agent": coordinator.name,
                "result": consensus_result,
                "timestamp": datetime.now().isoformat()
            }
            self.session_data["phases"]["consensus_evaluation"] = consensus_result
            yield {
                "type": "phase_complete",
                "phase": "consensus_evaluation",
                "consensus_reached": consensus_reached,
                "result": consensus_result,
                "message": "专家已达成共识" if consensus_reached else "需要进一步协调",
                "timestamp": datetime.now().isoformat()
            }
            return
        except Exception as e:
            logger.error(f"Streaming consensus evaluation failed: {e}")
            error_result = {
                "agent": coordinator.name,
                "consensus_score": 0.5,
                "consensus_reached": False,
                "threshold": 0.75,
                "response": f"共识评估流式过程出现错误: {e}",
                "timestamp": datetime.now().isoformat()
            }
            yield {
                "type": "agent_complete",
                "phase": "consensus_evaluation",
                "agent": coordinator.name,
                "result": error_result,
                "timestamp": datetime.now().isoformat()
            }
            self.session_data["phases"]["consensus_evaluation"] = error_result
            yield {
                "type": "phase_complete",
                "phase": "consensus_evaluation",
                "consensus_reached": False,
                "result": error_result,
                "message": "共识评估失败",
                "timestamp": datetime.now().isoformat()
            }
            return
    
    def _step_6_final_coordination_stream(self, case_data: Dict[str, Any], 
                                        consensus_reached: bool,
                                        selected_agents: Optional[List[str]] = None) -> Generator[Dict[str, Any], None, None]:
        """流式执行第六步：最终协调"""
        coordinator = self.agents["coordinator"]
        
        yield {
            "type": "agent_start",
            "phase": "final_coordination",
            "agent": coordinator.name,
            "message": "协调员开始生成最终建议",
            "timestamp": datetime.now().isoformat()
        }
        
        # 收集所有标准格式的专家意见
        all_expert_opinions = []
        for phase_name, phase_data in self.session_data["phases"].items():
            if phase_name in ["individual_analysis", "sharing_discussion", "final_coordination"]:
                if isinstance(phase_data, dict):
                    if "rounds" in phase_data:  # 多轮讨论结果
                        for round_data in phase_data["rounds"]:
                            for result in round_data["results"].values():
                                if isinstance(result, dict) and "agent" in result:
                                    all_expert_opinions.append(result)
                    else:  # 其他阶段结果
                        for result in phase_data.values():
                            if isinstance(result, dict) and "agent" in result:
                                all_expert_opinions.append(result)
        
        # 流式生成最终协调意见
        for chunk in coordinator.analyze_case(case_data, all_expert_opinions, stream=True):
            if chunk.get("is_complete"):
                # 提取标准格式的最终协调结果
                standard_result = {
                    "agent": chunk.get("agent", coordinator.name),
                    "response": chunk.get("response", chunk.get("full_response", "")),
                    "specialty": coordinator.specialty,
                    "phase": "final_coordination",
                    "timestamp": datetime.now().isoformat()
                }
                
                # 保存最终协调结果
                self.session_data["phases"]["final_coordination"] = standard_result
                self.session_data["final_result"] = standard_result
                
                yield {
                    "type": "agent_complete",
                    "phase": "final_coordination",
                    "agent": coordinator.name,
                    "result": standard_result,
                    "timestamp": datetime.now().isoformat()
                }
                
                yield {
                    "type": "phase_complete",
                    "phase": "final_coordination",
                    "message": "最终协调完成",
                    "result": standard_result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                yield {
                    "type": "agent_chunk",
                    "phase": "final_coordination",
                    "agent": coordinator.name,
                    "chunk": chunk.get("response_chunk", ""),
                    "full_response": chunk.get("full_response", ""),
                    "timestamp": datetime.now().isoformat()
                }
    
    def _calculate_simple_consensus(self, responses: List[str]) -> float:
        """简单的共识度计算"""
        if not responses or len(responses) < 2:
            return 1.0
        
        try:
            # 计算关键词重叠度
            all_words = set()
            word_counts = {}
            
            for response in responses:
                words = set(response.lower().split())
                all_words.update(words)
                for word in words:
                    word_counts[word] = word_counts.get(word, 0) + 1
            
            # 计算共同词汇比例
            common_words = sum(1 for count in word_counts.values() if count >= len(responses) * 0.5)
            consensus_score = common_words / max(len(all_words), 1)
            
            return min(consensus_score, 1.0)
            
        except Exception:
            return 0.5
