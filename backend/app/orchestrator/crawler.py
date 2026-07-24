from __future__ import annotations
import json
import re
from pathlib import Path

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "env",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    ".flowforge",
    "data",
    ".next",
    "out"
}

IGNORE_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig.tsbuildinfo"
}

ALLOWED_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx",
    ".py", ".json", ".md", ".yml", ".yaml",
    ".html", ".css", ".sh"
}

def extract_python_outline(content: str) -> tuple[list[str], list[str], list[str]]:
    classes = []
    functions = []
    imports = []
    
    class_regex = re.compile(r"^class\s+(\w+)", re.MULTILINE)
    fn_regex = re.compile(r"^def\s+(\w+)", re.MULTILINE)
    import_regex = re.compile(r"^(?:import\s+(\S+)|from\s+(\S+)\s+import)", re.MULTILINE)

    classes = class_regex.findall(content)
    functions = fn_regex.findall(content)
    
    for match in import_regex.findall(content):
        imp = match[0] or match[1]
        if imp:
            imports.append(imp.strip())
            
    return classes, functions, list(set(imports))

def extract_js_ts_outline(content: str) -> tuple[list[str], list[str], list[str]]:
    classes = []
    functions = []
    imports = []
    
    class_regex = re.compile(r"(?:export\s+)?class\s+(\w+)", re.MULTILINE)
    fn_regex = re.compile(r"(?:export\s+)?function\s+(\w+)|(?:export\s+)?const\s+(\w+)\s*=\s*(?:\([^)]*\)|[^=])\s*=>", re.MULTILINE)
    import_regex = re.compile(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"]\)", re.MULTILINE)

    classes = class_regex.findall(content)
    
    for match in fn_regex.findall(content):
        name = match[0] or match[1]
        if name:
            functions.append(name)
            
    for match in import_regex.findall(content):
        imp = match[0] or match[1]
        if imp:
            imports.append(imp)
            
    return classes, functions, list(set(imports))

def generate_codebase_outline(repo_dir: Path) -> dict:
    repo_dir = repo_dir.resolve()
    outline_files = []
    
    def walk(directory: Path) -> None:
        for entry in directory.iterdir():
            if entry.name in IGNORE_DIRS:
                continue
            if entry.is_dir():
                walk(entry)
            elif entry.is_file():
                if entry.name in IGNORE_FILES:
                    continue
                ext = entry.suffix.lower()
                if ext not in ALLOWED_EXTENSIONS:
                    continue
                
                rel_path = entry.relative_to(repo_dir).as_posix()
                size = entry.stat().st_size
                
                classes = []
                functions = []
                imports = []
                
                try:
                    if size < 500000:
                        content = entry.read_text(encoding="utf-8", errors="ignore")
                        if ext == ".py":
                            classes, functions, imports = extract_python_outline(content)
                        elif ext in {".js", ".jsx", ".ts", ".tsx"}:
                            classes, functions, imports = extract_js_ts_outline(content)
                except Exception:
                    pass
                
                outline_files.append({
                    "path": rel_path,
                    "sizeBytes": size,
                    "classes": classes,
                    "functions": functions,
                    "imports": imports
                })

    if repo_dir.exists() and repo_dir.is_dir():
        walk(repo_dir)
        
    return {"files": outline_files}

def save_codebase_outline(repo_dir: Path, output_file: Path) -> None:
    outline = generate_codebase_outline(repo_dir)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(outline, indent=2), encoding="utf-8")
