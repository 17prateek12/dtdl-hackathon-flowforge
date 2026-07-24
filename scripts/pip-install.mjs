import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const backendDir = path.join(root, "backend");
const venvPython =
  process.platform === "win32"
    ? path.join(backendDir, ".venv", "Scripts", "python.exe")
    : path.join(backendDir, ".venv", "bin", "python");

if (!existsSync(venvPython)) {
  console.error("Expected virtualenv at", venvPython);
  process.exit(1);
}

const result = spawnSync(
  venvPython,
  ["-m", "pip", "install", "-r", "requirements.txt"],
  { cwd: backendDir, stdio: "inherit" },
);

process.exit(result.status ?? 1);
