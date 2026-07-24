from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Try initializing FastEmbed text embedding, fallback to simple hashing embedding if offline
try:
    from fastembed import TextEmbedding
    _fastembed_model: Optional[TextEmbedding] = None

    def get_embedding_model() -> TextEmbedding:
        global _fastembed_model
        if _fastembed_model is None:
            _fastembed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return _fastembed_model

    def embed_texts(texts: List[str]) -> List[List[float]]:
        model = get_embedding_model()
        return [list(vec) for vec in model.embed(texts)]
    EMBEDDING_DIM = 384
except Exception:
    import hashlib

    def embed_texts(texts: List[str]) -> List[List[float]]:
        results = []
        for t in texts:
            # Deterministic lightweight 128-dim embedding fallback
            h = hashlib.sha256(t.encode("utf-8")).digest()
            vec = [float(b) / 255.0 for b in h] * 4  # 32 * 4 = 128
            results.append(vec[:384])
        return results
    EMBEDDING_DIM = 384


import concurrent.futures


def _process_single_file(args: tuple[Path, Path, int, int]) -> Dict[str, Any] | None:
    """Parallel worker to read, split into chunks, and embed a single codebase file."""
    fpath, base_dir, chunk_size, chunk_overlap = args
    try:
        content = fpath.read_text(encoding="utf-8", errors="replace")
        rel_path = str(fpath.relative_to(base_dir))

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )
        chunks = splitter.split_text(content)
        if not chunks:
            return None

        embeddings = embed_texts(chunks)
        lines = content.splitlines()

        chunk_items = []
        for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
            payload = {
                "path": rel_path,
                "chunk_index": idx,
                "content": chunk_text,
                "line_count": len(lines),
            }
            chunk_items.append((emb, payload))

        return {
            "rel_path": rel_path,
            "chunks_count": len(chunks),
            "bytes": len(content),
            "chunk_items": chunk_items,
        }
    except Exception as err:
        print(f"[RAG Worker] Error processing {fpath}: {err}")
        return None


COLLECTION_NAME = "flowforge_codebase"
QDRANT_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "qdrant_db"


class QdrantRAGManager:
    """Manages Qdrant vector database storage, file chunking, and similarity search."""

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = QDRANT_STORAGE_DIR
        storage_path.mkdir(parents=True, exist_ok=True)

        try:
            self.client = QdrantClient(path=str(storage_path))
        except Exception:
            self.client = QdrantClient(location=":memory:")
        self._ensure_collection()


    def _ensure_collection(self) -> None:
        collections = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )

    def index_directory(
        self,
        repo_path: str,
        target_files: Optional[List[str]] = None,
        chunk_size: int = 400,
        chunk_overlap: int = 50,
    ) -> Dict[str, Any]:
        """Reads target files, splits them into language chunks, embeds, and stores in Qdrant using parallel workers."""
        from app.paths import ROOT

        p = Path(repo_path)
        base_dir = p.resolve()
        if not base_dir.exists() or not base_dir.is_dir():
            cand1 = (ROOT / p.name).resolve()
            cand2 = (ROOT / repo_path).resolve()
            if cand1.exists() and cand1.is_dir():
                base_dir = cand1
            elif cand2.exists() and cand2.is_dir():
                base_dir = cand2
            else:
                base_dir = ROOT

        valid_exts = {
            ".js", ".jsx", ".ts", ".tsx", ".py", ".json", ".md", ".html",
            ".css", ".sh", ".yaml", ".yml", ".sql", ".cjs", ".mjs", ".txt"
        }

        files_to_process: List[Path] = []
        if target_files:
            for rel in target_files:
                fpath = (base_dir / rel).resolve()
                if fpath.exists() and fpath.is_file():
                    files_to_process.append(fpath)
                else:
                    # Try matching filename in base_dir
                    matched = list(base_dir.rglob(Path(rel).name))
                    if matched:
                        files_to_process.append(matched[0])
        else:
            for p in base_dir.rglob("*"):
                if p.is_file() and p.suffix.lower() in valid_exts:
                    if not any(
                        part.startswith(".") or part in ("node_modules", ".venv", "__pycache__", "dist", "build")
                        for part in p.parts
                    ):
                        files_to_process.append(p)

        # Fallback if no files were found in base_dir
        if not files_to_process and base_dir != ROOT:
            demo_fallback = (ROOT / "demo-repo").resolve()
            if demo_fallback.exists():
                for p in demo_fallback.rglob("*"):
                    if p.is_file() and p.suffix.lower() in valid_exts:
                        files_to_process.append(p)
                base_dir = demo_fallback

        # Execute parallel worker pool for fast indexing across CPU cores
        max_workers = min(os.cpu_count() or 4, 8)
        tasks = [(fpath, base_dir, chunk_size, chunk_overlap) for fpath in files_to_process]

        results: List[Optional[Dict[str, Any]]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_process_single_file, tasks))

        points: List[PointStruct] = []
        point_id = 1
        total_chunks = 0
        file_summaries: List[Dict[str, Any]] = []

        for res in results:
            if not res:
                continue
            file_summaries.append({
                "path": res["rel_path"],
                "chunks": res["chunks_count"],
                "bytes": res["bytes"],
            })
            for emb, payload in res["chunk_items"]:
                total_chunks += 1
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=emb,
                        payload=payload,
                    )
                )
                point_id += 1

        if points:
            # Upsert into Qdrant DB
            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
            )

        return {
            "status": "success",
            "repository": str(base_dir),
            "indexedFiles": len(file_summaries),
            "totalChunks": total_chunks,
            "fileDetails": file_summaries,
            "collection": COLLECTION_NAME,
        }

    def search(
        self,
        query: str,
        limit: int = 5,
        target_files: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Performs vector similarity search in Qdrant vector DB."""
        if not query.strip():
            return []

        query_vec = embed_texts([query])[0]
        res_obj = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vec,
            limit=limit,
        )
        results = res_obj.points if hasattr(res_obj, "points") else res_obj

        formatted: List[Dict[str, Any]] = []
        for res in results:
            payload = res.payload or {}
            path = payload.get("path", "")
            if target_files and path not in target_files:
                continue

            formatted.append({
                "path": path,
                "content": payload.get("content", ""),
                "chunkIndex": payload.get("chunk_index", 0),
                "score": round(float(res.score), 4),
            })
        return formatted


    def get_status(self) -> Dict[str, Any]:
        """Returns Qdrant collection status and vector count."""
        try:
            info = self.client.get_collection(COLLECTION_NAME)
            return {
                "collection": COLLECTION_NAME,
                "vectorsCount": info.points_count,
                "indexed": info.points_count > 0,
            }
        except Exception:
            return {
                "collection": COLLECTION_NAME,
                "vectorsCount": 0,
                "indexed": False,
            }


# Global RAG Manager instance
rag_manager = QdrantRAGManager()
