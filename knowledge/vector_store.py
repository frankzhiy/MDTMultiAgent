import os
from typing import List, Dict, Any, Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.embeddings.base import Embeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from utils.config import config
import logging
from prompts import RAG_QUERY_PROMPT  # 保留扩展多查询模板需要
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
import glob
import pandas as pd  # CSV 解析
import pickle
import uuid
import time

logger = logging.getLogger(__name__)

class MedicalKnowledgeStore:
    """医学知识库管理类 (FAISS 后端版本)"""

    def __init__(self):
        api_key_raw = getattr(config, 'OPENAI_API_KEY', None) or os.getenv('OPENAI_API_KEY') or ''
        # 通过环境变量设置避免 proxies 参数冲突
        if api_key_raw:
            os.environ['OPENAI_API_KEY'] = api_key_raw
        # 延迟初始化 embeddings / index，避免导入时阻塞 UI
        self.embeddings: Optional[Embeddings] = None
        self.embedding_model_name: str = getattr(config, 'EMBEDDING_PROVIDER', 'auto')
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""]
        )
        self.index: Optional[FAISS] = None
        self.meta_records: Dict[str, Dict[str, Any]] = {}
        # 持久化目录（统一使用 FAISS_DB_PATH）
        self.persist_path = getattr(config, 'FAISS_DB_PATH', './data/faiss_store')
        os.makedirs(self.persist_path, exist_ok=True)
        # 仅加载 meta 记录，向量索引延迟加载
        self._load_meta_if_exists()

    # ---- 延迟初始化辅助 ----
    def ensure_embeddings(self):
        if self.embeddings is None:
            self.embeddings = self._init_embeddings()

    def ensure_index_loaded(self):
        if self.index is not None:
            return
        # 若磁盘存在索引文件，则延迟加载
        idx_file, meta_file = self._faiss_files()
        if os.path.exists(idx_file):
            try:
                self.ensure_embeddings()
                try:
                    self.index = FAISS.load_local(self.persist_path, self.embeddings, allow_dangerous_deserialization=True)  # type: ignore[arg-type]
                except TypeError:
                    self.index = FAISS.load_local(self.persist_path, self.embeddings)  # type: ignore[arg-type]
                logger.info(f"FAISS 索引延迟加载完成: {self.persist_path}")
            except Exception as e:
                logger.warning(f"延迟加载 FAISS 失败: {e}")

    # ---------------- FAISS 持久化 ----------------
    def _faiss_files(self):
        # FAISS save_local 实际保存为 index.faiss 和 index.pkl，我们只需要 meta.pkl
        return os.path.join(self.persist_path, 'index.faiss'), os.path.join(self.persist_path, 'meta.pkl')

    def _init_embeddings(self) -> Embeddings:
        provider = getattr(config, 'EMBEDDING_PROVIDER', 'auto')
        want_local = provider == 'local'
        # 明确 openai 模式（不做回退）
        if provider == 'openai':
            emb_model = getattr(config, 'EMBEDDING_MODEL', 'text-embedding-3-small')
            self.embedding_model_name = f"openai:{emb_model}"
            return OpenAIEmbeddings(model=emb_model)

        # auto / local 模式：优先尝试 OpenAI（仅 auto 且存在 key），做一次探针调用验证；失败则回退本地
        if provider in ('auto', 'local'):
            if provider == 'auto' and config.get_llm_api_key():
                try:
                    emb_model = getattr(config, 'EMBEDDING_MODEL', 'text-embedding-3-small')
                    test = OpenAIEmbeddings(model=emb_model)
                    # 探针：实际请求一次极小的嵌入，提前触发 401 / 网络错误
                    try:
                        test.embed_query("ping")  # 触发一次网络调用
                        logger.info("Using OpenAI embeddings (auto, probe ok)")
                        self.embedding_model_name = f"openai:{emb_model}"
                        return test
                    except Exception as e_probe:
                        logger.warning(f"OpenAI embeddings probe failed -> fallback local: {e_probe}")
                except Exception as e_init:
                    logger.warning(f"OpenAI embeddings init failed (auto) -> fallback local: {e_init}")
            # 本地回退 / 指定 local
            try:
                from sentence_transformers import SentenceTransformer
                model_name = getattr(config, 'LOCAL_EMBEDDING_MODEL', 'BAAI/bge-small-zh-v1.5')
                logger.info(f"Using local embeddings model: {model_name}")
                model = SentenceTransformer(model_name)

                class _STEmb(Embeddings):  # 适配 LangChain Embeddings 接口
                    def __init__(self, m, name):
                        self.m = m
                        self.name = name
                    def embed_documents(self, texts):
                        return [list(v) for v in self.m.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)]
                    def embed_query(self, text):
                        return list(self.m.encode(text, show_progress_bar=False, normalize_embeddings=True))
                self.embedding_model_name = f"local:{model_name}"
                return _STEmb(model, self.embedding_model_name)
            except Exception as e_local:
                if want_local:
                    raise RuntimeError(f"本地嵌入模型加载失败: {e_local}")
                logger.warning(f"Local embedding load failed (auto mode), re-attempting OpenAI as last resort: {e_local}")

        # 兜底：再尝试 OpenAI（可能依旧失败，但保持行为可见）
        emb_model = getattr(config, 'EMBEDDING_MODEL', 'text-embedding-3-small')
        self.embedding_model_name = f"openai:{emb_model}(fallback)"
        return OpenAIEmbeddings(model=emb_model)

    def _load_meta_if_exists(self):
        idx_file, meta_file = self._faiss_files()
        if os.path.exists(meta_file):
            try:
                with open(meta_file, 'rb') as f:
                    self.meta_records = pickle.load(f)
                logger.info(f"Loaded existing FAISS meta from {self.persist_path}, records={len(self.meta_records)}")
            except Exception as e:
                logger.warning(f"Failed loading existing FAISS meta: {e}")

    def _persist(self):
        if self.index is None:
            return
        idx_file, meta_file = self._faiss_files()
        try:
            self.index.save_local(self.persist_path)
            with open(meta_file, 'wb') as f:
                pickle.dump(self.meta_records, f)
        except Exception as e:
            logger.error(f"Persist FAISS failed: {e}")
    
    def add_documents_from_directory(self, directory_path: str, file_pattern: str = "*.txt") -> int:
        if not os.path.exists(directory_path):
            return 0
        try:
            loader = DirectoryLoader(directory_path, glob=file_pattern, loader_cls=TextLoader, loader_kwargs={'encoding':'utf-8'})
            docs = loader.load()
            if not docs:
                return 0
            split_docs = self.text_splitter.split_documents(docs)
            return self._add_docs(split_docs)
        except Exception as e:
            logger.error(f"add_documents_from_directory error: {e}")
            return 0
    
    def add_document_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        try:
            from langchain.schema import Document
            chunks = self.text_splitter.split_text(text)
            docs = [Document(page_content=c, metadata=metadata or {}) for c in chunks]
            added = self._add_docs(docs)
            return added > 0
        except Exception as e:
            logger.error(f"add_document_text error: {e}")
            return False

    def _add_docs(self, docs) -> int:
        start_total = time.time()
        docs = [d for d in docs if (d.page_content or '').strip()]
        if not docs:
            return 0
        try:
            # 确保已就绪 embeddings；index 如为空将于首批创建
            self.ensure_embeddings()
            t_prep = time.time()
            texts = [d.page_content for d in docs]
            metas = []
            for d in docs:
                md = dict(d.metadata)
                md.setdefault('source', md.get('source','unknown'))
                md['doc_id'] = md.get('doc_id') or str(uuid.uuid4())
                metas.append(md)
                self.meta_records[md['doc_id']] = md
            t_embed_start = time.time()
            # 分批嵌入，减少单次请求体积，提高可观测性；首批若 index 为空 用 from_texts 创建
            batch_size = getattr(config, 'EMBEDDING_BATCH_SIZE', 64)
            total_batches = (len(texts) + batch_size - 1) // batch_size
            start_idx = 0
            if self.index is None:
                first_batch_texts = texts[:batch_size]
                first_batch_metas = metas[:batch_size]
                b_start = time.time()
                self.index = FAISS.from_texts(first_batch_texts, self.embeddings, metadatas=first_batch_metas)
                b_end = time.time()
                if getattr(config, 'SHOW_EMBED_PROGRESS', True):
                    logger.info(f"[Embed进度] batch 1/{total_batches} (首批初始化) size={len(first_batch_texts)} 用时={(b_end-b_start):.2f}s")
                start_idx = batch_size
            batch_counter = 1 if start_idx else 0
            for i in range(start_idx, len(texts), batch_size):
                b_texts = texts[i:i+batch_size]
                b_metas = metas[i:i+batch_size]
                b_start = time.time()
                if b_texts:
                    self.index.add_texts(b_texts, metadatas=b_metas)  # type: ignore
                b_end = time.time()
                batch_counter += 1
                if getattr(config, 'SHOW_EMBED_PROGRESS', True) and b_texts:
                    pct = (batch_counter/total_batches)*100
                    logger.info(f"[Embed进度] batch {batch_counter}/{total_batches} ({pct:.1f}%) size={len(b_texts)} 用时={(b_end-b_start):.2f}s")
            t_after = time.time()
            self._persist()
            logger.info(
                f"Embedding新增: chunks={len(texts)} | 准备耗时={(t_embed_start - t_prep):.2f}s | 向量写入耗时={(t_after - t_embed_start):.2f}s | 总耗时={(t_after - start_total):.2f}s"
            )
            return len(texts)
        except Exception as e:
            logger.error(f"_add_docs error: {e}")
            return 0
    
    def search_relevant_knowledge(self, query: str, specialty: str = "", k: int = 5) -> List[Dict[str, Any]]:
        try:
            q = f"{specialty} {query}" if specialty else query
            # 确保索引可用（若磁盘存在则延迟加载）
            self.ensure_index_loaded()
            if self.index is None:
                return []
            docs_scores = self.index.similarity_search_with_score(q, k=k)  # type: ignore
            out = []
            for doc, score in docs_scores:
                out.append({
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'relevance_score': score,
                    'source': doc.metadata.get('source','unknown')
                })
            return out
        except Exception as e:
            logger.error(f"search_relevant_knowledge error: {e}")
            return []
    
    def get_context_for_agent(self, case_info: Dict[str, Any], agent_type: str, max_context_length: int = 2000) -> str:
        """为特定智能体获取相关上下文"""
        # 根据智能体类型构建查询
        queries = self._build_agent_queries(case_info, agent_type)
        collected: List[Dict[str, Any]] = []
        for query in queries:
            results = self.search_relevant_knowledge(query, agent_type, k=3)
            for result in results:
                collected.append(result)
        # 组装带来源和分数
        formatted = []
        for i, r in enumerate(collected, 1):
            src = r.get('source','未知来源')
            score = r.get('relevance_score')
            score_str = f"{score:.4f}" if isinstance(score,(int,float)) else "?"
            formatted.append(f"[片段#{i} | 来源: {src} | 相关度: {score_str}]\n{r.get('content','')}")
        context = "\n\n".join(formatted)
        if len(context) > max_context_length:
            context = context[:max_context_length] + "..."
        
        return context
    
    def _build_agent_queries(self, case_info: Dict[str, Any], agent_type: str) -> List[str]:
        """为不同类型的智能体构建查询"""
        base_query = f"{case_info.get('symptoms', '')} {case_info.get('medical_history', '')}"
        
        queries = [base_query]
        
        if agent_type == "radiology":
            if case_info.get("imaging_results"):
                queries.append(f"影像学 {case_info['imaging_results']}")
        elif agent_type == "pathology":
            if case_info.get("pathology_results"):
                queries.append(f"病理学 {case_info['pathology_results']}")
        elif agent_type == "oncology":
            queries.append(f"肿瘤治疗 {base_query}")
        elif agent_type == "clinical":
            queries.append(f"临床诊断 {base_query}")
        
        return queries
    
    def generate_multi_queries(self, case_info: Dict[str, Any], agent_type: str, n: int = 4) -> List[str]:
        """利用 LLM 将病例关键信息扩展为多个检索子查询。

        说明：
        - 轻量实现：直接拼装一个指令而非再用单独 RAG_QUERY_PROMPT（保留字段以便未来切换）。
        - 可扩展点：改为调用一个专用 PROMPT（多查询模板），或返回 JSON 后解析。
        """
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.get_llm_api_key(), base_url=config.get_llm_base_url())
            summary_parts = []
            for k in ["symptoms","medical_history","imaging_results","lab_results","pathology_results","additional_info"]:
                v = case_info.get(k)
                if v and v not in ("N/A","未提供"):
                    summary_parts.append(f"{k}:{v}")
            summary = " | ".join(summary_parts) or "空"
            instruction = (
                "请基于间质性肺病病例信息，为" + agent_type + " 专科生成"+str(n)+"条检索子查询。"
                "要求：\n- 每条尽量聚焦一个方面（症状模式/影像特征/实验室指标/风险因素/并发症/治疗反应）"
                "\n- 直接输出纯行文本，每行一个查询，不要编号，不要解释。\n病例概要: " + summary
            )
            resp = client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[{"role":"system","content":"你是医学信息检索助手"},{"role":"user","content":instruction}],
                temperature=0.2,
                max_tokens=400
            )
            content = resp.choices[0].message.content if resp.choices and resp.choices[0].message and resp.choices[0].message.content else ""
            if not content:
                return []
            queries = [q.strip() for q in content.splitlines() if q.strip()][:n]
            # 兜底：若 LLM 返回不足，补一个基线查询
            if not queries:
                base_q = f"{case_info.get('symptoms','')} {case_info.get('medical_history','')}".strip()
                if base_q:
                    queries=[base_q]
            return queries
        except Exception:
            base_q = f"{case_info.get('symptoms','')} {case_info.get('medical_history','')}".strip()
            return [base_q] if base_q else []

    def multi_query_context(self, case_info: Dict[str, Any], agent_type: str, max_context_length: int = 2000, n_queries: int = 4, per_query_k: int = 3) -> str:
        """执行 multi-query 检索并合并上下文。

        步骤：
        1. 生成子查询列表
        2. 对每个子查询 top-k 相似度检索
        3. 去重（基于内容 hash）与合并
        4. 按原加入顺序截断总长度
        """
        queries = self.generate_multi_queries(case_info, agent_type, n=n_queries)
        seen = set()
        merged_chunks: List[str] = []
        detailed_chunks: List[str] = []
        for q in queries:
            results = self.search_relevant_knowledge(q, agent_type, k=per_query_k)
            for r in results:
                content = r.get("content","")
                if not content:
                    continue
                h = hash(content)
                if h in seen:
                    continue
                seen.add(h)
                src = r.get('source','未知来源')
                score = r.get('relevance_score')
                score_str = f"{score:.4f}" if isinstance(score,(int,float)) else "?"
                chunk_text = f"[来源: {src} | 相关度: {score_str} | 子查询: {q}]\n{content}"
                merged_chunks.append(content)
                detailed_chunks.append(chunk_text)
                if sum(len(c) for c in merged_chunks) > max_context_length:
                    break
            if sum(len(c) for c in merged_chunks) > max_context_length:
                break
        context = "\n\n".join(detailed_chunks)
        if len(context) > max_context_length:
            context = context[:max_context_length] + "..."
        return context or ""
    
    def get_collection_stats(self) -> Dict[str, Any]:
        try:
            total = len(self.meta_records)
            return {
                'total_documents': total,
                'backend': 'FAISS',
                'path': self.persist_path,
                'embedding_model': getattr(self, 'embedding_model_name', 'lazy'),
                'status': 'healthy'
            }
        except Exception as e:
            return {'total_documents':0,'backend':'FAISS','status':'error','error':str(e)}
    
    def clear_collection(self) -> bool:
        try:
            import shutil
            if os.path.isdir(self.persist_path):
                shutil.rmtree(self.persist_path)
            os.makedirs(self.persist_path, exist_ok=True)
            self.index = None
            self.meta_records = {}
            logger.info("FAISS collection cleared")
            return True
        except Exception as e:
            logger.error(f"clear_collection error: {e}")
            return False

    def get_processed_files(self) -> set:
        """获取已处理文件列表（基于meta_records中的source）"""
        processed = set()
        for meta in self.meta_records.values():
            source = meta.get('source', '')
            if source and not source.startswith('chunk_'):
                # 提取文件路径（去掉可能的chunk后缀）
                if '|chunk_' in source:
                    source = source.split('|chunk_')[0]
                processed.add(source)
        return processed

    def add_new_files_only(self,
                          directory_path: str = "knowledge/documents",
                          patterns: Optional[List[str]] = None,
                          include_pdf: bool = True,
                          include_csv: bool = True) -> Dict[str, Any]:
        """增量更新：仅处理新文件，并输出耗时统计"""
        patterns = patterns or ["*.txt", "*.md"]
        summary = {"chunks_added":0, "files_processed":0, "txt_files":0, "pdf_files":0, "csv_files":0, "errors": [], "skipped_files": 0}
        start_all = time.time()
        if not os.path.isdir(directory_path):
            summary["errors"].append(f"Directory not found: {directory_path}")
            return summary
        processed_files = self.get_processed_files()
        logger.info(f"Already processed files: {len(processed_files)}")
        # 预统计总文件数用于百分比
        total_files = 0
        for pattern in patterns:
            total_files += len(glob.glob(os.path.join(directory_path, pattern)))
        if include_pdf:
            total_files += len(glob.glob(os.path.join(directory_path, "*.pdf")))
        if include_csv:
            total_files += len(glob.glob(os.path.join(directory_path, "*.csv")))
        processed_file_counter = 0
        # --- TXT / MD ---
        for pattern in patterns:
            file_paths = glob.glob(os.path.join(directory_path, pattern))
            for file_path in file_paths:
                try:
                    abs_path = os.path.abspath(file_path)
                    if abs_path in processed_files:
                        summary["skipped_files"] += 1
                        processed_file_counter += 1
                        continue
                    docs = TextLoader(file_path, encoding='utf-8').load()
                    for d in docs:
                        d.metadata['source'] = abs_path
                    added = self._add_documents_batched(docs)
                    summary['chunks_added'] += added
                    summary['txt_files'] += 1
                    summary['files_processed'] += 1
                    processed_file_counter += 1
                    if getattr(config, 'SHOW_EMBED_PROGRESS', True) and total_files:
                        logger.info(f"[文件进度] {processed_file_counter}/{total_files} ({processed_file_counter/total_files*100:.1f}%) 处理: {os.path.basename(file_path)}")
                except Exception as e:
                    summary['errors'].append(f"txt({file_path}): {e}")
        # --- PDF ---
        if include_pdf:
            pdf_paths = glob.glob(os.path.join(directory_path, "*.pdf"))
            for pdf_path in pdf_paths:
                try:
                    abs_path = os.path.abspath(pdf_path)
                    if abs_path in processed_files:
                        summary['skipped_files'] += 1
                        processed_file_counter += 1
                        continue
                    pages = PyPDFLoader(pdf_path).load()
                    for p in pages:
                        p.metadata['source'] = abs_path
                    added = self._add_documents_batched(pages)
                    summary['chunks_added'] += added
                    summary['pdf_files'] += 1
                    summary['files_processed'] += 1
                    processed_file_counter += 1
                    if getattr(config, 'SHOW_EMBED_PROGRESS', True) and total_files:
                        logger.info(f"[文件进度] {processed_file_counter}/{total_files} ({processed_file_counter/total_files*100:.1f}%) 处理: {os.path.basename(pdf_path)}")
                except Exception as e:
                    summary['errors'].append(f"pdf({pdf_path}): {e}")
        # --- CSV ---
        if include_csv:
            csv_paths = glob.glob(os.path.join(directory_path, "*.csv"))
            for csv_path in csv_paths:
                try:
                    abs_path = os.path.abspath(csv_path)
                    if abs_path in processed_files:
                        summary['skipped_files'] += 1
                        processed_file_counter += 1
                        continue
                    df = pd.read_csv(csv_path)
                    flattened = df.apply(lambda row: ' | '.join(row.astype(str)), axis=1).tolist()
                    docs = [Document(page_content=t, metadata={'source': abs_path}) for t in flattened]
                    added = self._add_documents_batched(docs)
                    summary['chunks_added'] += added
                    summary['csv_files'] += 1
                    summary['files_processed'] += 1
                    processed_file_counter += 1
                    if getattr(config, 'SHOW_EMBED_PROGRESS', True) and total_files:
                        logger.info(f"[文件进度] {processed_file_counter}/{total_files} ({processed_file_counter/total_files*100:.1f}%) 处理: {os.path.basename(csv_path)}")
                except Exception as e:
                    summary['errors'].append(f"csv({csv_path}): {e}")
        self._persist()
        elapsed = time.time() - start_all
        avg = (elapsed / summary['chunks_added']) if summary['chunks_added'] else 0
        logger.info(f"Incremental update summary: {summary} | 总耗时={elapsed:.2f}s | 平均每chunk={avg:.3f}s")
        return summary

    # ---------------- New ingestion / rebuild helpers -----------------
    def _add_documents_batched(self, docs, batch_size: int = 50, retries: int = 2):
        # 对 FAISS 简化：直接一次性走 _add_docs（FAISS add_texts 已内部分批）
        return self._add_docs(docs)

    def rebuild_from_directory(self,
                                directory_path: str = "knowledge/documents",
                                patterns: Optional[List[str]] = None,
                                include_pdf: bool = True,
                                include_csv: bool = True,
                                max_csv_rows: int = 5000,
                                batch_size: int = 40) -> Dict[str, Any]:
        """清空并重建索引，支持多格式 (txt, pdf, csv)。

        Returns summary 统计。
        """
        patterns = patterns or ["*.txt", "*.md"]
        summary = {"chunks_added":0, "files_processed":0, "txt_files":0, "pdf_files":0, "csv_files":0, "errors": []}
        try:
            rebuild_start = time.time()
            self.clear_collection()
            if not os.path.isdir(directory_path):
                logger.warning(f"Rebuild directory not found: {directory_path}")
                return summary
            # TXT/MD
            for pat in patterns:
                try:
                    files = glob.glob(os.path.join(directory_path, pat))
                    if not files:
                        continue
                    loader = DirectoryLoader(directory_path, glob=pat, loader_cls=TextLoader, loader_kwargs={'encoding':'utf-8'})
                    docs = loader.load()
                    if not docs:
                        continue
                    split_docs = self.text_splitter.split_documents(docs)
                    # 填充 source
                    for d in split_docs:
                        d.metadata.setdefault('source', d.metadata.get('source', 'unknown'))
                    if split_docs:
                        added = self._add_documents_batched(split_docs, batch_size=batch_size)
                        summary['chunks_added'] += added
                    summary['txt_files'] += len(files)
                    summary['files_processed'] += len(files)
                except Exception as e:
                    logger.error(f"TXT ingest error pattern {pat}: {e}")
                    summary['errors'].append(f"txt({pat}): {e}")
            # PDF
            if include_pdf:
                pdf_paths = glob.glob(os.path.join(directory_path, "*.pdf"))
                for pdf in pdf_paths:
                    try:
                        loader = PyPDFLoader(pdf)
                        pages = loader.load()
                        # 过滤空内容页
                        pages = [p for p in pages if (p.page_content or '').strip()]
                        for p in pages:
                            p.metadata['source'] = pdf
                        if not pages:
                            logger.warning(f"PDF 空或无法提取文本: {pdf}")
                            continue
                        split_pages = self.text_splitter.split_documents(pages)
                        split_pages = [sp for sp in split_pages if (sp.page_content or '').strip()]
                        if split_pages:
                            added = self._add_documents_batched(split_pages, batch_size=batch_size)
                            summary['chunks_added'] += added
                        summary['pdf_files'] += 1
                        summary['files_processed'] += 1
                    except Exception as e:
                        logger.error(f"PDF ingest error {pdf}: {e}")
                        summary['errors'].append(f"pdf({pdf}): {e}")
            # CSV
            if include_csv:
                csv_paths = glob.glob(os.path.join(directory_path, "*.csv"))
                for csv_file in csv_paths:
                    try:
                        df = pd.read_csv(csv_file, nrows=max_csv_rows)
                        # 简单：每行合并为一段；可改进为列选择/字段截断
                        rows_text = []
                        for _, row in df.iterrows():
                            line = ' | '.join(f"{c}:{row[c]}" for c in df.columns if str(row[c]).strip() != '')
                            if line:
                                rows_text.append(line)
                        full_text = '\n'.join(rows_text)
                        if not full_text.strip():
                            continue
                        from langchain.schema import Document
                        docs = [Document(page_content=full_text, metadata={'source': csv_file, 'type':'csv'})]
                        split_docs = self.text_splitter.split_documents(docs)
                        for d in split_docs:
                            d.metadata.setdefault('source', csv_file)
                        if split_docs:
                            added = self._add_documents_batched(split_docs, batch_size=batch_size)
                            summary['chunks_added'] += added
                        summary['csv_files'] += 1
                        summary['files_processed'] += 1
                    except Exception as e:
                        logger.error(f"CSV ingest error {csv_file}: {e}")
                        summary['errors'].append(f"csv({csv_file}): {e}")
            logger.info(f"Rebuild finished: {summary} | 总耗时={time.time()-rebuild_start:.2f}s")
            return summary
        except Exception as e:
            logger.error(f"Rebuild failed: {e}")
            summary['errors'].append(str(e))
            return summary

# 单例与惰性 getter，避免导入即初始化重资源
_singleton: Optional[MedicalKnowledgeStore] = None

def get_knowledge_store() -> MedicalKnowledgeStore:
    global _singleton
    if _singleton is None:
        _singleton = MedicalKnowledgeStore()
    return _singleton
