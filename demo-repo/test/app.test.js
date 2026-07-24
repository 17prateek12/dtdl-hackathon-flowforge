import assert from "node:assert/strict";
import test from "node:test";
import { startServer } from "../src/app.js";

async function get(port, path) {
  const res = await fetch(`http://127.0.0.1:${port}${path}`);
  const body = await res.json();
  return { status: res.status, body };
}

test("GET / returns ok", async () => {
  const { server, port } = await startServer();
  try {
    const { status, body } = await get(port, "/");
    assert.equal(status, 200);
    assert.equal(body.status, "ok");
  } finally {
    server.close();
  }
});

test("GET /health returns healthy", async () => {
  const { server, port } = await startServer();
  try {
    const { status, body } = await get(port, "/health");
    assert.equal(status, 200);
    assert.equal(body.status, "healthy");
  } finally {
    server.close();
  }
});
