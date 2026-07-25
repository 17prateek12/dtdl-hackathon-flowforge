from __future__ import annotations

import os
import json
from typing import Optional, TYPE_CHECKING

from app.models import RunRecord, MySQLRunData, AgentRunData, Workflow

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    mysql = None  # type: ignore[assignment]
    MYSQL_AVAILABLE = False

# NOTE: workflow_store is NOT imported at module level to avoid a circular
# import (workflow_store → mysql_db → workflow_store).  It is imported
# lazily inside sync_run_to_mysql() where it is actually needed.

# Retrieve configuration from environment variables
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "flowforge")


def get_connection(with_db: bool = True):
    """Establishes and returns a connection to the MySQL server."""
    if not MYSQL_AVAILABLE:
        raise RuntimeError("mysql-connector-python package is not installed.")
    config = {
        "host": MYSQL_HOST,
        "port": MYSQL_PORT,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
    }
    if with_db:
        config["database"] = MYSQL_DATABASE
    return mysql.connector.connect(**config)



def init_db() -> None:
    """Initializes the MySQL database and creates tables if they don't exist."""
    conn = None
    cursor = None
    try:
        # Step 1: Ensure database exists
        conn = get_connection(with_db=False)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE}")
        conn.commit()
        cursor.close()
        conn.close()

        # Step 2: Ensure tables exist
        conn = get_connection(with_db=True)
        cursor = conn.cursor()

        # Pipelines (run) table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipelines (
                run_id VARCHAR(100) PRIMARY KEY,
                pipeline_data JSON NOT NULL
            )
        """)

        # Agents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                run_id VARCHAR(100) PRIMARY KEY,
                agent_data JSON NOT NULL
            )
        """)

        # Verdicts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verdicts (
                run_id VARCHAR(100) PRIMARY KEY,
                verdict VARCHAR(50) NOT NULL,
                evidence LONGTEXT
            )
        """)

        # Saved workflows (pipeline definitions) table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                workflow_id VARCHAR(100) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                workflow_data JSON NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        print("[MySQL] Database and tables successfully initialized.")
    except Exception as exc:
        print(f"[MySQL Error] Failed to initialize database: {exc}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def calculate_verdict(run: RunRecord) -> str:
    """Calculates the best representation of a run's verdict."""
    # 1. Respect terminal run states
    if run.status == "succeeded":
        return "PASS"
    if run.status == "failed":
        return "FAIL"
    if run.status == "stopped":
        return "STOPPED"

    # 2. Check the decision node receipt
    decision_receipt = run.receipts.get("decision")
    if decision_receipt:
        if decision_receipt.output == "pass":
            return "PASS"
        if decision_receipt.output == "fail":
            return "FAIL"

    # 3. Check the validation node receipt
    validation_receipt = run.receipts.get("validation")
    if validation_receipt:
        if validation_receipt.status == "completed":
            return "PASS"
        if validation_receipt.status == "failed":
            return "FAIL"

    # 4. Check if any node has raised an error or failed
    for receipt in run.receipts.values():
        if receipt.status == "failed":
            return "FAIL"

    # 5. Default to PENDING if still running or waiting
    return "PENDING"


def sync_run_to_mysql(run: RunRecord) -> None:
    """Synchronizes a RunRecord to the MySQL tables using Pydantic serialization."""
    # Ensure tables are initialized (safe to call multiple times)
    init_db()

    conn = None
    cursor = None
    try:
        # 1. Load Workflow (Pipeline) — lazy import avoids circular dependency
        from app.store.workflow_store import load_workflow  # noqa: PLC0415
        workflow: Workflow = load_workflow(run.workflowId)

        # 2. Extract Agent Nodes data & receipts
        agent_nodes = []
        for node in workflow.nodes:
            if node.data.nodeType == "agent":
                status = run.nodeStatuses.get(node.id, "idle")
                receipt = run.receipts.get(node.id)
                agent_nodes.append(
                    AgentRunData(
                        node_id=node.id,
                        label=node.data.label,
                        role=node.data.role,
                        model=node.data.model,
                        status=status,
                        receipt=receipt,
                    )
                )

        # 3. Determine Verdict & Evidence
        verdict = calculate_verdict(run)
        evidence = run.validationEvidence or run.lastError or ""


        # 4. Construct Pydantic model
        mysql_run_data = MySQLRunData(
            run_id=run.id,
            pipeline=workflow,
            agents=agent_nodes,
            verdict=verdict,
            evidence=evidence,
        )

        # 5. Serialize data to JSON strings
        pipeline_json = mysql_run_data.pipeline.model_dump_json()
        # Serialize list of AgentRunData objects
        agents_json = json.dumps([agent.model_dump(mode="json") for agent in mysql_run_data.agents])

        # 6. Save to MySQL
        conn = get_connection(with_db=True)
        cursor = conn.cursor()

        # Save Pipeline
        cursor.execute(
            "INSERT INTO pipelines (run_id, pipeline_data) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE pipeline_data = %s",
            (mysql_run_data.run_id, pipeline_json, pipeline_json)
        )

        # Save Agents
        cursor.execute(
            "INSERT INTO agents (run_id, agent_data) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE agent_data = %s",
            (mysql_run_data.run_id, agents_json, agents_json)
        )

        # Save Verdict
        cursor.execute(
            "INSERT INTO verdicts (run_id, verdict, evidence) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE verdict = %s, evidence = %s",
            (mysql_run_data.run_id, mysql_run_data.verdict, mysql_run_data.evidence,
             mysql_run_data.verdict, mysql_run_data.evidence)
        )

        conn.commit()
        print(f"[MySQL] Run {run.id} synchronized successfully (Verdict: {verdict}).")
    except Exception as exc:
        print(f"[MySQL Error] Failed to sync run {run.id}: {exc}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def save_workflow_to_mysql(workflow: "Workflow") -> None:
    """Persists a workflow definition to the MySQL workflows table."""
    init_db()
    conn = None
    cursor = None
    try:
        workflow_json = workflow.model_dump_json()
        conn = get_connection(with_db=True)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO workflows (workflow_id, name, workflow_data) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE name = %s, workflow_data = %s, updated_at = CURRENT_TIMESTAMP",
            (workflow.id, workflow.name, workflow_json, workflow.name, workflow_json),
        )
        conn.commit()
        print(f"[MySQL] Workflow '{workflow.name}' ({workflow.id}) saved.")
    except Exception as exc:
        print(f"[MySQL Error] Failed to save workflow {workflow.id}: {exc}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def list_workflows_from_mysql() -> list[dict]:
    """Returns all saved workflow summaries (id, name, updated_at) from MySQL."""
    init_db()
    conn = None
    cursor = None
    try:
        conn = get_connection(with_db=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT workflow_id, name, updated_at FROM workflows ORDER BY updated_at DESC"
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r["workflow_id"],
                "name": r["name"],
                "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        print(f"[MySQL Error] Failed to list workflows: {exc}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def rename_workflow_in_mysql(workflow_id: str, new_name: str) -> None:
    """Renames a workflow in MySQL."""
    init_db()
    conn = None
    cursor = None
    try:
        conn = get_connection(with_db=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT workflow_data FROM workflows WHERE workflow_id = %s", (workflow_id,))
        row = cursor.fetchone()
        new_json = None
        if row and row.get("workflow_data"):
            try:
                raw_data = row["workflow_data"]
                data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                data["name"] = new_name
                new_json = json.dumps(data)
            except Exception:
                pass
        
        if new_json:
            cursor.execute(
                "UPDATE workflows SET name = %s, workflow_data = %s WHERE workflow_id = %s",
                (new_name, new_json, workflow_id)
            )
        else:
            cursor.execute(
                "UPDATE workflows SET name = %s WHERE workflow_id = %s",
                (new_name, workflow_id)
            )
        conn.commit()
        print(f"[MySQL] Workflow '{workflow_id}' renamed to '{new_name}'.")
    except Exception as exc:
        print(f"[MySQL Error] Failed to rename workflow {workflow_id}: {exc}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def delete_workflow_from_mysql(workflow_id: str) -> None:
    """Deletes a workflow from MySQL."""
    init_db()
    conn = None
    cursor = None
    try:
        conn = get_connection(with_db=True)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflows WHERE workflow_id = %s", (workflow_id,))
        conn.commit()
        print(f"[MySQL] Workflow '{workflow_id}' deleted.")
    except Exception as exc:
        print(f"[MySQL Error] Failed to delete workflow {workflow_id}: {exc}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

