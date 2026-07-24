from __future__ import annotations
import json
import math
import re
import os
from pathlib import Path
from typing import Any, Optional

from app.agents.llm import get_embedding, use_mock
from app.orchestrator.crawler import generate_codebase_outline

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(x*y for x, y in zip(v1, v2))
    n1 = sum(x*x for x in v1) ** 0.5
    n2 = sum(x*x for x in v2) ** 0.5
    return dot / (n1 * n2) if (n1 > 0 and n2 > 0) else 0.0

def chunk_text(text: str, chunk_size: int = 600, overlap: int = 150) -> list[str]:
    lines = text.splitlines()
    chunks = []
    current_lines = []
    current_len = 0
    
    for line in lines:
        current_lines.append(line)
        current_len += len(line)
        if current_len >= chunk_size:
            chunks.append("\n".join(current_lines))
            overlap_lines = current_lines[-max(1, len(current_lines) // 4):]
            current_lines = list(overlap_lines)
            current_len = sum(len(x) for x in current_lines)
            
    if current_lines and current_len > 0:
        chunks.append("\n".join(current_lines))
        
    return chunks or [text]

class SimpleBM25:
    def __init__(self, corpus: list[dict], k1: float = 1.5, b: float = 0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.doc_len = []
        self.doc_freqs = []
        self.ndocs = len(corpus)
        self.avg_doc_len = 0
        self.idf = {}
        self._initialize()

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def _initialize(self):
        total_len = 0
        df = {}
        for doc in self.corpus:
            tokens = self._tokenize(doc["text"])
            self.doc_len.append(len(tokens))
            total_len += len(tokens)
            
            freqs = {}
            for t in tokens:
                freqs[t] = freqs.get(t, 0) + 1
            self.doc_freqs.append(freqs)
            
            for t in freqs:
                df[t] = df.get(t, 0) + 1
                
        self.avg_doc_len = total_len / self.ndocs if self.ndocs > 0 else 0
        
        for t, f in df.items():
            self.idf[t] = math.log((self.ndocs - f + 0.5) / (f + 0.5) + 1.0)

    def get_scores(self, query: str) -> list[float]:
        query_tokens = self._tokenize(query)
        scores = []
        for i in range(self.ndocs):
            score = 0.0
            freqs = self.doc_freqs[i]
            d_len = self.doc_len[i]
            for t in query_tokens:
                if t in freqs:
                    f = freqs[t]
                    idf_val = self.idf.get(t, 0.0)
                    num = f * (self.k1 + 1)
                    den = f + self.k1 * (1 - self.b + self.b * (d_len / self.avg_doc_len))
                    score += idf_val * (num / den)
            scores.append(score)
        return scores

def build_or_update_index(repo_dir: Path, index_file: Path) -> dict:
    repo_dir = repo_dir.resolve()
    index_data = {"files": {}}
    
    if index_file.exists():
        try:
            index_data = json.loads(index_file.read_text(encoding="utf-8"))
        except Exception:
            pass
            
    outline = generate_codebase_outline(repo_dir)
    updated = False
    
    for f in outline["files"]:
        path_str = f["path"]
        abs_path = repo_dir / path_str
        if not abs_path.exists():
            continue
            
        mtime = abs_path.stat().st_mtime
        
        existing = index_data.get("files", {}).get(path_str)
        if existing and existing.get("mtime") == mtime:
            continue
            
        try:
            content = abs_path.read_text(encoding="utf-8", errors="ignore")
            chunks = chunk_text(content)
            chunk_records = []
            
            for chunk in chunks:
                emb = get_embedding(chunk)
                chunk_records.append({
                    "text": chunk,
                    "embedding": emb
                })
                
            index_data.setdefault("files", {})[path_str] = {
                "mtime": mtime,
                "chunks": chunk_records
            }
            updated = True
        except Exception:
            pass
            
    active_paths = {f["path"] for f in outline["files"]}
    for path_str in list(index_data.get("files", {}).keys()):
        if path_str not in active_paths:
            index_data["files"].pop(path_str, None)
            updated = True
            
    if updated:
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.write_text(json.dumps(index_data, indent=2), encoding="utf-8")
        
    return index_data

def hybrid_search(repo_dir: Path, index_file: Path, query: str, top_k: int = 5) -> list[dict]:
    index_data = build_or_update_index(repo_dir, index_file)
    
    corpus_chunks = []
    for path_str, f_data in index_data.get("files", {}).items():
        for i, chunk in enumerate(f_data.get("chunks", [])):
            corpus_chunks.append({
                "id": f"{path_str}#chunk{i}",
                "path": path_str,
                "text": chunk["text"],
                "embedding": chunk["embedding"]
            })
            
    if not corpus_chunks:
        return []
        
    bm25 = SimpleBM25(corpus_chunks)
    bm25_scores = bm25.get_scores(query)
    
    q_emb = get_embedding(query)
    semantic_scores = [cosine_similarity(q_emb, chunk["embedding"]) for chunk in corpus_chunks]
    
    max_bm25 = max(bm25_scores) if bm25_scores else 0
    norm_bm25 = [s / max_bm25 if max_bm25 > 0 else 0.0 for s in bm25_scores]
    
    ranked_results = []
    for i, chunk in enumerate(corpus_chunks):
        bm25_val = norm_bm25[i]
        sem_val = semantic_scores[i]
        combined_score = 0.3 * bm25_val + 0.7 * sem_val
        
        ranked_results.append({
            "path": chunk["path"],
            "text": chunk["text"],
            "score": combined_score,
            "bm25": bm25_val,
            "semantic": sem_val
        })
        
    ranked_results.sort(key=lambda x: x["score"], reverse=True)
    return ranked_results[:top_k]
