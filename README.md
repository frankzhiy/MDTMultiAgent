# 间质性肺病(ILD) 专门化多智能体 MDT 系统

> 文档已精简整合：原 PROJECT_SUMMARY.md / USAGE_GUIDE.md / MULTI_ROUND_UPGRADE.md / ILD_MDT_CONVERSION_SUMMARY.md 全部内容合并于此 README。

## 目录
- [简介](#简介)
- [核心特性](#核心特性)
- [系统架构与目录结构](#系统架构与目录结构)
- [智能体列表 (ILD 专门化)](#智能体列表-ild-专门化)
- [如何编辑 Prompt (Markdown)](#如何编辑-prompt-markdown)
- [多轮 MDT 工作流程](#多轮-mdt-工作流程)
- [快速开始](#快速开始)
- [运行方式](#运行方式)
- [环境变量与配置](#环境变量与配置)
- [使用流程](#使用流程)
- [示例代码](#示例代码)
- [导出与界面特性](#导出与界面特性)
- [故障排除](#故障排除)
- [后续路线 / Roadmap](#后续路线-roadmap)
- [免责声明](#免责声明)

## 简介
本项目是一个针对间质性肺病 (Interstitial Lung Disease, ILD) 诊断讨论场景定制的多智能体 MDT（多学科团队）系统。系统整合呼吸、影像、病理、风湿免疫与数据分析等专科视角，并通过协调员形成统一共识，支持多轮冲突识别、共识评估与实时可视化。

底层依赖：LangChain + FAISS + OpenAI/本地嵌入 + Streamlit。支持流式输出、并行阶段处理、结构化导出与交互图可视化。

- RAG 检索：FAISS 向量库按专科检索相关背景
- 多专科协同：呼吸 / 影像（文字描述）/ 病理 / 风湿免疫 / 数据分析 / 协调员
- ILD 专门化提示词与分析关注维度
├── knowledge/                 # 知识库 (FAISS)
- 多轮讨论机制：冲突检测 → 迭代讨论 → 共识量化 → 最终协调
│   └── faiss_store/
FAISS_DB_PATH=./data/faiss_store
- 实时 UI 组件：阶段进度条、专家卡片网格、交互关系图(SVG)、滚动卡片、专业 Markdown 渲染
| FAISS 错误 | 向量库损坏 | 删除 data/faiss_store 重新生成 |
- 结果导出：TXT 结构化报告 + JSON 全量会话数据 + （可扩展）图谱快照
- RAG 检索：FAISS 向量库按专科检索相关背景
- 可扩展架构：新增专科只需实现 BaseAgent 子类并注册

## 系统架构与目录结构
FAISS_DB_PATH=./data/faiss_store
multiAgent/
├── agents/                    # 智能体实现
│   ├── base_agent.py          # 基类
│   ├── pulmonary_agent.py     # 呼吸科（ILD 核心临床）
# 嵌入提供者: openai | local | auto (auto: 先探针OpenAI失败再回退本地)
EMBEDDING_PROVIDER=auto
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
│   ├── imaging_agent.py       # 影像文字描述 / HRCT 模式
│   ├── pathology_agent.py     # 病理组织学 / 纤维化特征
│   ├── rheumatology_agent.py  # CTD-ILD / 自身抗体关联
│   ├── data_analysis_agent.py # 数据/指标整合分析
│   └── coordinator_agent.py   # 协调员 / 冲突与共识
│
├── knowledge/                 # 知识库 (FAISS)
│   ├── vector_store.py
│   └── documents/
│
├── prompts/                   # 提示词模板（已裁剪为现行专科）
├── mdt_system/                # 核心流程 & 状态机（已精简）
│   └── orchestrator.py        # 单一来源：多轮工作流 + 并行/流式事件
├── app/                       # Streamlit 前端
│   └── streamlit_app_stream.py
├── data/                      # 样例 / 会话 / 向量库
│   ├── sample_cases/
│   ├── sessions/
│   └── faiss_store/
├── utils/                     # 配置 & 工具
├── test_system.py             # 运行前健康自检
├── setup.sh / setup.bat       # 一键环境脚本
├── requirements.txt
└── README.md                  # (唯一文档)
```

## 智能体列表 (ILD 专门化)
| 标识 | 文件 | 角色定位 | 关键关注点 |
|------|------|----------|------------|
| pulmonary | pulmonary_agent.py | 呼吸科 | ILD 分类 / 症状进展 / 肺功能 / 治疗策略 |
| imaging | imaging_agent.py | 影像科 | HRCT 模式 (UIP/NSIP/OP 等) / 进展对比 |
| pathology | pathology_agent.py | 病理科 | 组织学模式 / 纤维化程度 / 差异诊断 |
| rheumatology | rheumatology_agent.py | 风湿免疫 | CTD-ILD 关联 / 自身抗体解释 |
| data_analysis | data_analysis_agent.py | 数据分析 | 指标趋势 / 风险评分 / 结构化整合 |
| coordinator | coordinator_agent.py | 协调员 | 冲突检测 / 共识评估 / 综合建议 |

## 如何编辑 Prompt (Markdown)
提示词已经全部改为 Markdown 文件（prompts/ 目录）。非工程人员可直接改文本；代码自动加载。若要新增或修改：

目录结构示例：
```
prompts/
	system/              # 各智能体 system prompt（角色/身份）
	tasks/               # 任务型 prompt（总结、RAG 等）
	checklists_md/       # 分专科结构化分析清单
	registry.py          # id → 路径登记表
	loader.py            # get_prompt + 缓存 + safe_format
	preview_tool.py      # 预览/占位符检测 CLI 工具
	__init__.py          # 导出常量（保持旧接口不变）
```

新增步骤：
1. 在对应子目录创建 .md 文件，首行可选写 YAML front‑matter：
	 ```
	 ---
	 id: NEW_SPECIAL_PROMPT
	 desc: 影像模式差异对比专用
	 ---
	 这里是正文，可使用 Markdown、列表、表格、示例段落。
	 需要动态插值的变量，用 {variable_name} 形式占位。
	 ```
2. 在 `prompts/registry.py` 中添加：`"NEW_SPECIAL_PROMPT": "system/new_special.md",`
3. （可选）如需模块级常量，编辑 `prompts/__init__.py`：仿照现有常量添加一行 `NEW_SPECIAL_PROMPT = get_prompt("NEW_SPECIAL_PROMPT")`
4. 运行 Web 界面“Prompt 管理”面板点击“♻️ 热加载全部”即可生效，或重启进程。

安全占位符：
- 支持 `{patient_id}` 这类 Python format 语法。
- 使用 `safe_format(template, **data)`：缺失变量不会报错，原样 `{var}` 留存，并返回缺失变量列表。

预览与检查：
```bash
python -m prompts.preview_tool --list                 # 列出全部
python -m prompts.preview_tool --id COORDINATOR_PROMPT --show
python -m prompts.preview_tool --id COORDINATOR_PROMPT --check case_info="..." all_opinions="..."
```

热加载：
- Web 界面侧边栏或顶部“Prompt 管理”区点击“♻️ 热加载全部”
- 或在 Python 代码中调用：
	```python
	from prompts import reload_all_prompts
	reload_all_prompts()
	```

最佳实践：
- 用列表强调步骤，表格展示结构化清单。
- 避免在 system prompt 中直接写具体病例示例（保持泛化）。
- 把随实验变化的超参数（轮次、阈值）放到配置层，不嵌入固定文本。

占位符审计：在 RAG / 任务型 prompt 中新增变量后，务必在调用处补充 `safe_format` 参数，防止 KeyError。


## 多轮 MDT 工作流程
阶段状态机 (MDTPhase)：
1. initialization - 初始化/解析病例
2. individual_analysis - 各专科独立流式分析（并行）
3. sharing_discussion - 初步共享讨论（并行）
4. conflict_detection - 语义冲突检测 & 分歧摘要
5. multi_round_discussion - 针对冲突的最多 N(≤3) 轮迭代
6. consensus_evaluation - 共识评分 / 阈值触发提前终止
7. final_coordination - 协调员综合报告
8. completed - 会话结束 (导出 / 归档)

设计要点：
- 前两阶段并行 + 流式事件：agent_chunk / agent_complete
- 冲突矩阵/共识度量：由协调员基于自然语言相似性与差异段落提炼
- 迭代终止条件：达到共识阈值 (默认 0.75) 或轮次上限

## 快速开始
```bash
git clone <your_repo>
cd multiAgent
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY
python test_system.py      # 健康检查
streamlit run app/streamlit_app_stream.py
```

## 运行方式
CLI（支持参数）：
```bash
# 交互模式（逐步输入病例 + 选择专科）
python main.py

# 全自动快速演示（默认全部主要专科 + 内置示例病例）
python main.py --auto

# 指定病例 JSON 文件 + 仅选择呼吸与影像 + 数据分析
python main.py --case data/sample_cases/ild_case_uip.json --agents pulmonary,imaging,data_analysis

# 仅自定义专科（病例信息交互输入）
python main.py --agents pulmonary,pathology,rheumatology
```
可用专科键（--agents 逗号分隔，不包含协调员/自动添加）：
pulmonary | imaging | pathology | rheumatology | data_analysis

参数说明：
- `--auto` ：使用内置 ILD_AUTO_001 示例病例 + 全部专科
- `--case <path>` ：加载指定 JSON（需包含 patient_id 字段）；失败则回退交互输入
- `--agents <list>` ：限制参与专科；无效项忽略；全部无效则回退为全体

Web：
```bash
streamlit run app/streamlit_app_stream.py
```

## 环境变量与配置 (.env)
```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4
OPENAI_TEMPERATURE=0.7
FAISS_DB_PATH=./data/faiss_store
LOG_LEVEL=INFO
MAX_TOKENS=2000
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

## 使用流程
1. 准备病例：在 Web 界面粘贴或通过示例载入
2. 选择参与专科（未选专科不会出现在后续任何阶段）
3. 启动会话：实时查看独立分析 / 共享讨论流式输出
4. 观察冲突检测结果与迭代多轮讨论 (如触发)
5. 查看共识评分与最终协调建议
6. 导出报告 (TXT/JSON)

## 示例代码
```python
import asyncio
from mdt_system.orchestrator import MDTOrchestrator

case_data = {
	"patient_id": "ILD001",
	"symptoms": "进行性呼吸困难，干咳18个月",
	"medical_history": "40包年吸烟，可能接触鸟类饲养环境",
	"imaging_results": "HRCT: 基底部网状影+蜂窝样改变，轻度牵拉支气管扩张",
	"pathology_results": "外科肺活检：UIP 模式特征",
	"lab_results": "ANA(-) RF(-) KL-6 升高",
	"additional_info": "6MWD 420m, FVC 68% 预计值"
}

async def run():
	orchestrator = MDTOrchestrator()
	result = await orchestrator.conduct_mdt_session(
		case_data,
		selected_agents=["pulmonary","imaging","pathology","rheumatology","data_analysis"]
	)
	print(result["phases"].keys())

asyncio.run(run())
```

## 导出与界面特性
- 专家卡片网格布局（前期 3 列，自适应）
- 滚动内容区域（长响应不撑爆页面）
- 后期阶段全宽卡片：冲突 / 多轮 / 共识 / 最终
- Markdown 增强：标题锚点、表格、强调块
- 实时阶段流：pending / active / done 样式指示
- 交互图：节点 = 专家；有向边 = 发言顺序影响，权重按引用频次
- 导出：
  - TXT：结构化章节（病例摘要 / 各专科要点 / 冲突与共识 / 最终建议）
  - JSON：原始数据 + 分阶段响应 + 时间戳

## 故障排除
| 问题 | 可能原因 | 处理 |
|------|----------|------|
| 无响应或很慢 | API Key 未配置 / 网络代理 | 检查 .env / 网络 / 更换模型 |
| FAISS 错误 | 向量库损坏 | 删除 data/faiss_store 重新生成 |
| 显示残缺 | 浏览器缓存 / Streamlit 版本 | 刷新或升级 streamlit |
| 成本过高 | tokens 超限 | 降低 MAX_TOKENS / 缩短病例文本 |

日志查看：
```bash
tail -f mdt_system.log
```

## 后续路线 Roadmap
- [ ] 交互图导出为 SVG/PNG
- [ ] 共识评分可视化（趋势火花线）
- [ ] “示例假数据模式” 无 API 演示
- [ ] Agent 权重可调 / 自适应投票
- [ ] 更多结构化指标抽取与数据面板

## 免责声明
本系统仅供科研与教学用途，不能替代临床医疗决策。请确保所有输入已脱敏并遵守数据合规要求。输出内容须由合格医疗专业人员审核。

## License
仅限研究使用（Research Only）。

---
文档合并时间：2025-08-11

如需历史版本说明，可在提交历史中查看已删除的文档记录。


（文档末尾的旧版重复说明已移除，避免混淆。）
