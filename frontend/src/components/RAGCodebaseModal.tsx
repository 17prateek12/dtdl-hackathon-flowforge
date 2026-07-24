"use client";

import React, { useState, useEffect } from "react";
import {
  Database,
  CheckCircle,
  RefreshCw,
  X,
  FileCode,
  Folder,
  FolderOpen,
  Layers,
  ChevronRight,
  ArrowLeft,
  Check,
} from "lucide-react";

interface RAGCodebaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetRepo?: string;
  targetFiles?: string[];
  onSelectTargetRepo?: (repo: string) => void;
  onSelectTargetFiles?: (files: string[]) => void;
}

interface IndexResult {
  status: string;
  repository: string;
  indexedFiles: number;
  totalChunks: number;
  collection: string;
  fileDetails?: { path: string; chunks: number; bytes: number }[];
}

interface BrowseItem {
  name: string;
  path: string;
  isDir: boolean;
}

interface BrowseResponse {
  currentPath: string;
  parentPath: string | null;
  items: BrowseItem[];
}

export const RAGCodebaseModal: React.FC<RAGCodebaseModalProps> = ({
  isOpen,
  onClose,
  targetRepo = "./demo-repo",
  targetFiles = [],
  onSelectTargetRepo,
  onSelectTargetFiles,
}) => {
  const [repoPath, setRepoPath] = useState(targetRepo);
  const [selectedFiles, setSelectedFiles] = useState<string[]>(targetFiles);
  const [chunkSize, setChunkSize] = useState(400);
  const [chunkOverlap, setChunkOverlap] = useState(50);
  const [indexing, setIndexing] = useState(false);
  const [indexResult, setIndexResult] = useState<IndexResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [vectorCount, setVectorCount] = useState<number | null>(null);

  // Folder browser state
  const [isBrowsing, setIsBrowsing] = useState(false);
  const [browseData, setBrowseData] = useState<BrowseResponse | null>(null);
  const [loadingBrowse, setLoadingBrowse] = useState(false);
  const [browseInputPath, setBrowseInputPath] = useState(repoPath || ".");

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/rag/status`);
      if (res.ok) {
        const data = await res.json();
        setVectorCount(data.vectorsCount ?? 0);
      }
    } catch (err) {
      console.error("Failed to fetch RAG status", err);
    }
  };

  const fetchBrowse = async (path: string) => {
    setLoadingBrowse(true);
    try {
      const res = await fetch(
        `${backendUrl}/api/fs/browse?path=${encodeURIComponent(path)}`
      );
      if (res.ok) {
        const data: BrowseResponse = await res.json();
        setBrowseData(data);
        setBrowseInputPath(data.currentPath);
      }
    } catch (err) {
      console.error("Browse failed", err);
    } finally {
      setLoadingBrowse(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleIndex = async () => {
    setIndexing(true);
    setError(null);
    try {
      const res = await fetch(`${backendUrl}/api/rag/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          targetRepo: repoPath,
          targetFiles: selectedFiles.length > 0 ? selectedFiles : null,
          chunkSize,
          chunkOverlap,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to index codebase in Qdrant");
      }

      const data: IndexResult = await res.json();
      setIndexResult(data);
      setVectorCount(data.totalChunks);
    } catch (err: any) {
      setError(err.message || "An error occurred during Qdrant indexing");
    } finally {
      setIndexing(false);
    }
  };

  const openFolderBrowser = () => {
    setIsBrowsing(true);
    fetchBrowse(repoPath || ".");
  };

  const handleSelectFolder = (path: string) => {
    setRepoPath(path);
    if (onSelectTargetRepo) onSelectTargetRepo(path);
    setIsBrowsing(false);
  };

  const toggleFileSelection = (fileName: string) => {
    const next = selectedFiles.includes(fileName)
      ? selectedFiles.filter((f) => f !== fileName)
      : [...selectedFiles, fileName];
    setSelectedFiles(next);
    if (onSelectTargetFiles) onSelectTargetFiles(next);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-3xl max-h-[85vh] bg-slate-900 border border-slate-700/60 rounded-xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                Import Codebase & Qdrant RAG Chunking
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                  {vectorCount !== null ? `${vectorCount} vectors` : "Qdrant DB"}
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Select codebase folder, configure chunk parameters, and vectorize into Qdrant DB
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!isBrowsing ? (
            /* Main Form View */
            <div className="space-y-5">
              {/* Codebase Folder Selection */}
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/80 space-y-3">
                <label className="block text-xs font-semibold text-slate-300 flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <FolderOpen className="w-4 h-4 text-indigo-400" />
                    Codebase Directory Path
                  </span>
                  <button
                    onClick={openFolderBrowser}
                    className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium bg-indigo-500/10 px-2.5 py-1 rounded border border-indigo-500/20 transition"
                  >
                    <Folder className="w-3.5 h-3.5" />
                    Select Folder…
                  </button>
                </label>
                <input
                  type="text"
                  value={repoPath}
                  onChange={(e) => {
                    setRepoPath(e.target.value);
                    if (onSelectTargetRepo) onSelectTargetRepo(e.target.value);
                  }}
                  className="w-full text-xs font-mono px-3 py-2 bg-slate-900 border border-slate-700/80 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
                  placeholder="./demo-repo or /absolute/path/to/project"
                />
              </div>

              {/* Target File Filter */}
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/80 space-y-3">
                <label className="block text-xs font-semibold text-slate-300 flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-indigo-400" />
                  Target Files Selection (Optional)
                </label>
                <input
                  type="text"
                  value={selectedFiles.join(", ")}
                  onChange={(e) => {
                    const val = e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean);
                    setSelectedFiles(val);
                    if (onSelectTargetFiles) onSelectTargetFiles(val);
                  }}
                  className="w-full text-xs font-mono px-3 py-2 bg-slate-900 border border-slate-700/80 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
                  placeholder="Leave empty to index all codebase files, or specify e.g. src/app.js"
                />
              </div>

              {/* Chunking Parameters */}
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/80 space-y-3">
                <h3 className="text-xs font-semibold text-slate-300 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-indigo-400" />
                  Model Chunking Parameters
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Chunk Size (characters)
                    </label>
                    <input
                      type="number"
                      value={chunkSize}
                      onChange={(e) => setChunkSize(Number(e.target.value))}
                      className="w-full text-xs font-mono px-3 py-1.5 bg-slate-900 border border-slate-700/80 rounded-lg text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Chunk Overlap (characters)
                    </label>
                    <input
                      type="number"
                      value={chunkOverlap}
                      onChange={(e) => setChunkOverlap(Number(e.target.value))}
                      className="w-full text-xs font-mono px-3 py-1.5 bg-slate-900 border border-slate-700/80 rounded-lg text-slate-200"
                    />
                  </div>
                </div>
              </div>

              {/* Actions & Result */}
              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={handleIndex}
                  disabled={indexing}
                  className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-lg shadow-indigo-600/20 transition"
                >
                  {indexing ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Database className="w-4 h-4" />
                  )}
                  {indexing ? "Chunking & Indexing in Qdrant..." : "Index Codebase in Qdrant DB"}
                </button>

                {indexResult && (
                  <div className="flex items-center gap-2 text-xs text-emerald-400 font-mono bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
                    <CheckCircle className="w-4 h-4" />
                    Indexed {indexResult.indexedFiles} files ({indexResult.totalChunks} chunks)
                  </div>
                )}
              </div>

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
                  {error}
                </div>
              )}

              {/* Indexed Files breakdown */}
              {indexResult?.fileDetails && indexResult.fileDetails.length > 0 && (
                <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/80 space-y-2">
                  <h4 className="text-xs font-semibold text-slate-300">
                    Indexed Files Detail
                  </h4>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {indexResult.fileDetails.map((f, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between text-xs font-mono px-3 py-1.5 bg-slate-900 rounded border border-slate-800"
                      >
                        <span className="text-slate-300">{f.path}</span>
                        <span className="text-slate-400 text-[11px]">
                          {f.chunks} chunks ({f.bytes} B)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Filesystem Folder Selector View */
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <button
                  onClick={() => setIsBrowsing(false)}
                  className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 font-medium"
                >
                  <ArrowLeft className="w-4 h-4" /> Back to settings
                </button>

                {browseData?.currentPath && (
                  <button
                    onClick={() => handleSelectFolder(browseData.currentPath)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow transition"
                  >
                    <Check className="w-3.5 h-3.5" />
                    Select This Folder
                  </button>
                )}
              </div>

              {/* System Path Input & Go Button */}
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <FolderOpen className="w-4 h-4 absolute left-3 top-2.5 text-indigo-400" />
                  <input
                    type="text"
                    value={browseInputPath}
                    onChange={(e) => setBrowseInputPath(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") fetchBrowse(browseInputPath);
                    }}
                    placeholder="Enter any system path (e.g. /home/administrator or /)"
                    className="w-full text-xs font-mono pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <button
                  onClick={() => fetchBrowse(browseInputPath)}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
                >
                  Go
                </button>
              </div>

              {/* Quick Jump Shortcuts */}
              <div className="flex items-center gap-2 text-[11px]">
                <span className="text-slate-500 font-medium">Quick Jump:</span>
                <button
                  onClick={() => fetchBrowse("/home/administrator")}
                  className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-indigo-300 font-mono transition"
                >
                  ~ (Home)
                </button>
                <button
                  onClick={() => fetchBrowse("/")}
                  className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-indigo-300 font-mono transition"
                >
                  / (Root)
                </button>
                <button
                  onClick={() => fetchBrowse(".")}
                  className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-indigo-300 font-mono transition"
                >
                  Project Root
                </button>
              </div>

              <div className="space-y-1 max-h-72 overflow-y-auto bg-slate-950 p-2 rounded-xl border border-slate-800">
                {browseData?.parentPath && (
                  <button
                    onClick={() => fetchBrowse(browseData.parentPath!)}
                    className="w-full text-left flex items-center gap-2 px-3 py-2 text-xs font-mono text-slate-400 hover:bg-slate-900 rounded transition"
                  >
                    <Folder className="w-4 h-4 text-amber-500" />
                    .. (Parent Directory)
                  </button>
                )}

                {loadingBrowse ? (
                  <div className="py-8 text-center text-xs text-slate-500 font-mono">
                    Loading directory contents…
                  </div>
                ) : (
                  browseData?.items.map((item, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between px-3 py-2 hover:bg-slate-900 rounded text-xs font-mono transition group"
                    >
                      {item.isDir ? (
                        <div className="flex items-center justify-between w-full">
                          <button
                            onClick={() => fetchBrowse(item.path)}
                            className="flex items-center gap-2 text-slate-200 hover:text-indigo-400 font-medium text-left flex-1"
                            title="Click to open folder"
                          >
                            <Folder className="w-4 h-4 text-amber-400 shrink-0" />
                            <span className="truncate">{item.name}</span>
                            <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
                          </button>
                          <button
                            onClick={() => handleSelectFolder(item.path)}
                            className="ml-3 px-2 py-1 bg-indigo-600/80 hover:bg-indigo-600 text-white text-[11px] font-medium rounded border border-indigo-500/40 shadow-sm transition"
                          >
                            Select Folder
                          </button>
                        </div>
                      ) : (
                        <div
                          onClick={() => toggleFileSelection(item.name)}
                          className="flex items-center gap-2 text-slate-300 cursor-pointer flex-1 py-0.5 hover:text-white"
                        >
                          <FileCode className="w-4 h-4 text-indigo-400 shrink-0" />
                          <span className="truncate">{item.name}</span>
                          {selectedFiles.includes(item.name) ? (
                            <span className="ml-auto text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded border border-indigo-500/30 font-medium">
                              Selected ✓
                            </span>
                          ) : (
                            <span className="ml-auto text-[10px] text-slate-500 group-hover:text-slate-400">
                              Click to select file
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
