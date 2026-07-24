import { spawn } from "node:child_process";
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
  console.error(
    "Backend virtualenv not found. Run: npm run backend:install",
  );
  process.exit(1);
}

const port = process.env.LOOPFORGE_API_PORT || "8000";

const child = spawn(
  venvPython,
  [
    "-m",
    "uvicorn",
    "app.main:app",
    "--reload",
    "--host",
    "127.0.0.1",
    "--port",
    port,
  ],
  {
    cwd: backendDir,
    stdio: "inherit",
    env: process.env,
  },
);

child.on("exit", (code) => process.exit(code ?? 1));
