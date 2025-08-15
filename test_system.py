#!/usr/bin/env python3
"""
多智能体MDT系统 - 快速测试脚本
"""

import os
import sys

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试所有模块是否可以正常导入"""
    print("🧪 测试模块导入...")

    try:
        # 测试基础依赖
        import openai  # noqa: F401
        from langchain_openai import OpenAIEmbeddings  # 基础向量依赖
        _ = OpenAIEmbeddings
        print("✅ 基础依赖导入成功 (不再使用 Chroma)")

        # 测试项目模块
        from utils.config import config  # noqa: F401
        print("✅ 配置模块导入成功")
        from knowledge.vector_store import get_knowledge_store  # noqa: F401
        print("✅ 知识库模块导入成功")

        # 更新后的专科智能体导入
        from agents.pulmonary_agent import PulmonaryAgent  # noqa: F401
        from agents.imaging_agent import ImagingAgent  # noqa: F401
        from agents.pathology_agent import PathologyAgent  # noqa: F401
        from agents.rheumatology_agent import RheumatologyAgent  # noqa: F401
        from agents.data_analysis_agent import DataAnalysisAgent  # noqa: F401
        from agents.coordinator_agent import CoordinatorAgent  # noqa: F401
        print("✅ 智能体模块导入成功")

        from mdt_system.orchestrator import MDTOrchestrator  # noqa: F401
        print("✅ 编排器模块导入成功")

        return True

    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        return False

def test_configuration():
    """测试配置是否正确"""
    print("\n⚙️ 测试系统配置...")
    try:
        from utils.config import config
        # 检查API密钥
        if not config.OPENAI_API_KEY and config.EMBEDDING_PROVIDER == 'openai':
            print("⚠️ 警告：OPENAI_API_KEY 未设置且嵌入提供者为 openai，建议改为 EMBEDDING_PROVIDER=local")
        else:
            if config.OPENAI_API_KEY:
                print("✅ OpenAI API 密钥已配置")
        # 输出核心配置
        print(f"✅ 模型: {config.OPENAI_MODEL}")
        print(f"✅ 温度: {config.OPENAI_TEMPERATURE}")
        print(f"✅ 向量库存储路径: {config.FAISS_DB_PATH}")
        print(f"✅ 嵌入提供者: {config.EMBEDDING_PROVIDER} (LOCAL 模型: {config.LOCAL_EMBEDDING_MODEL})")
        return True
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

def test_knowledge_store():
    """测试知识库连接"""
    print("\n📚 测试知识库连接...")
    
    try:
        from knowledge.vector_store import get_knowledge_store
        # 获取知识库状态
        ks = get_knowledge_store()
        stats = ks.get_collection_stats()
        print(f"✅ 知识库状态: {stats['status']}")
        print(f"✅ 文档数量: {stats['total_documents']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 知识库测试失败: {e}")
        return False

def test_agents():
    """测试智能体创建"""
    print("\n👨‍⚕️ 测试智能体创建...")
    
    try:
        from agents.pulmonary_agent import PulmonaryAgent
        from agents.imaging_agent import ImagingAgent
        from agents.pathology_agent import PathologyAgent
        from agents.rheumatology_agent import RheumatologyAgent
        from agents.data_analysis_agent import DataAnalysisAgent
        from agents.coordinator_agent import CoordinatorAgent
        
        pulmonary = PulmonaryAgent()
        print(f"✅ 创建 {pulmonary.name} 成功")
        
        imaging = ImagingAgent()
        print(f"✅ 创建 {imaging.name} 成功")
        
        pathology = PathologyAgent()
        print(f"✅ 创建 {pathology.name} 成功")
        
        rheumatology = RheumatologyAgent()
        print(f"✅ 创建 {rheumatology.name} 成功")
        
        data_analysis = DataAnalysisAgent()
        print(f"✅ 创建 {data_analysis.name} 成功")
        
        coordinator = CoordinatorAgent()
        print(f"✅ 创建 {coordinator.name} 成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 智能体测试失败: {e}")
        return False

def test_orchestrator():
    """测试MDT编排器"""
    print("\n🎭 测试MDT编排器...")
    
    try:
        from mdt_system.orchestrator import MDTOrchestrator
        
        # 创建编排器
        orchestrator = MDTOrchestrator()
        print("✅ MDT编排器创建成功")
        
        # 检查智能体
        agent_count = len(orchestrator.agents)
        print(f"✅ 已加载 {agent_count} 个智能体")
        
        return True
        
    except Exception as e:
        print(f"❌ 编排器测试失败: {e}")
        return False

def run_all_tests():
    """运行所有测试"""
    print("🏥 多智能体MDT系统 - 系统测试")
    print("=" * 50)
    
    tests = [
        ("模块导入", test_imports),
        ("系统配置", test_configuration),
        ("知识库连接", test_knowledge_store),
        ("智能体创建", test_agents),
        ("MDT编排器", test_orchestrator)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统可以正常使用")
        print("\n🚀 运行方式:")
        print("   1. 命令行版本: python main.py")
        print("   2. Web界面版本: streamlit run app/streamlit_app_stream.py")
    else:
        print("⚠️ 部分测试失败，请检查配置和依赖")
        
        if not os.path.exists('.env'):
            print("\n💡 提示:")
            print("   1. 创建 .env 文件 (可复制 .env.example)")
            print("   2. 在 .env 文件中添加: OPENAI_API_KEY=your_api_key_here")

if __name__ == "__main__":
    run_all_tests()
