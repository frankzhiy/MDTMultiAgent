import os
from dotenv import load_dotenv
from typing import Optional

# 加载环境变量
load_dotenv()

class Config:
    """系统配置类（支持多 LLM 提供商切换）"""

    # 通用 LLM 抽象层
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()  # openai | deepseek
    LLM_MODEL: str = os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", os.getenv("OPENAI_TEMPERATURE", "0.7")))

    # OpenAI 配置（向后兼容）
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # DeepSeek 配置（遵循 OpenAI 兼容协议）
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    

    # FAISS 持久化目录
    # 向量库存储路径（已迁移到 FAISS，旧 CHROMA_DB_PATH 不再使用）
    FAISS_DB_PATH: str = os.getenv("FAISS_DB_PATH", "./data/faiss_store")
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "medical_knowledge")
    
    # 系统配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "2000"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    RAG_MULTI_QUERY: bool = False  # 是否启用多查询扩展检索
    # Embedding
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
    SHOW_EMBED_PROGRESS: bool = os.getenv("SHOW_EMBED_PROGRESS", "true").lower() in ("1","true","yes")
    # 本地嵌入后备策略: auto | openai | local
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "auto").lower()
    LOCAL_EMBEDDING_MODEL: str = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    
    @classmethod
    def validate(cls) -> bool:
        if not cls.get_llm_api_key():
            raise ValueError("缺少 LLM API Key。请设置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY")
        return True

    @classmethod
    def get_llm_api_key(cls) -> str:
        if cls.LLM_PROVIDER == 'deepseek':
            return cls.DEEPSEEK_API_KEY or cls.OPENAI_API_KEY  # fallback
        return cls.OPENAI_API_KEY

    @classmethod
    def get_llm_base_url(cls) -> str:
        if cls.LLM_PROVIDER == 'deepseek':
            return cls.DEEPSEEK_BASE_URL
        return cls.OPENAI_BASE_URL

    # 兼容旧代码里可能引用的属性（逐步淘汰）
    @property
    def OPENAI_MODEL(self):
        return self.LLM_MODEL

    @property
    def OPENAI_TEMPERATURE(self):
        return self.LLM_TEMPERATURE
# 创建全局配置实例
config = Config()
