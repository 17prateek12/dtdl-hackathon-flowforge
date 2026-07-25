from app.models import RunRecord
from app.store.mysql_db import init_db, sync_run_to_mysql, get_connection
import json

def test():
    print("Initializing Database...")
    init_db()
    
    # Create a mock run record
    run = RunRecord(
        id="test-run-12345",
        workflowId="default",
        status="running",
        attempt=1,
        maxAttempts=3,
        currentNodeId="criteria",
        nodeStatuses={"criteria": "completed", "planning": "idle"},
        receipts={},
        events=[],
        filesChanged=[],
        startedAt="2026-07-24T20:30:00Z",
        updatedAt="2026-07-24T20:30:00Z",
    )
    
    print("Syncing run to MySQL...")
    sync_run_to_mysql(run)
    
    print("Reading data back from MySQL to verify...")
    conn = get_connection(with_db=True)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM pipelines WHERE run_id = 'test-run-12345'")
    pipeline_row = cursor.fetchone()
    print("Pipeline Row:", pipeline_row)
    
    cursor.execute("SELECT * FROM agents WHERE run_id = 'test-run-12345'")
    agents_row = cursor.fetchone()
    print("Agents Row:", agents_row)
    
    cursor.execute("SELECT * FROM verdicts WHERE run_id = 'test-run-12345'")
    verdict_row = cursor.fetchone()
    print("Verdict Row:", verdict_row)
    
    cursor.close()
    conn.close()
    
    assert pipeline_row is not None, "Pipeline data not stored"
    assert agents_row is not None, "Agents data not stored"
    assert verdict_row is not None, "Verdict data not stored"
    print("All assertions passed. Test passed successfully!")

if __name__ == "__main__":
    test()
