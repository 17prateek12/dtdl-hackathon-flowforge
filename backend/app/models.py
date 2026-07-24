from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


NodeType = Literal[
    "input",
    "agent",
    "command",
    "validator",
    "decision",
    "humanGate",
    "success",
    "stop",
]
NodeStatus = Literal[
    "idle", "running", "completed", "failed", "waiting", "skipped"
]
AgentRole = Literal["successCriteria", "planning", "execution", "validation"]
RunStatus = Literal[
    "idle", "running", "waiting_for_human", "succeeded", "stopped", "failed"
]


class WorkflowNodeConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str
    description: Optional[str] = None
    nodeType: NodeType
    role: Optional[AgentRole] = None
    instructions: Optional[str] = None
    model: Optional[str] = None
    tools: Optional[list[str]] = None
    maxRetries: Optional[int] = None
    timeout: Optional[int] = None
    command: Optional[str] = None
    fileChecks: Optional[list[str]] = None
    objective: Optional[str] = None
    constraints: Optional[str] = None
    targetRepo: Optional[str] = None
    mainTargetFile: Optional[str] = None
    targetFiles: Optional[list[str]] = None
    validateCommand: Optional[str] = None


class Position(BaseModel):
    x: float
    y: float


class WorkflowNode(BaseModel):
    id: str
    type: str = "loopNode"
    position: Position
    data: WorkflowNodeConfig


class WorkflowEdge(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    label: Optional[str] = None
    style: Optional[dict[str, Any]] = None
    animated: Optional[bool] = None


class Workflow(BaseModel):
    id: str
    name: str
    maxAttempts: int = 3
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]


class ConsoleEvent(BaseModel):
    id: str
    ts: str
    level: Literal["info", "success", "warn", "error"]
    nodeId: Optional[str] = None
    message: str


class FileChange(BaseModel):
    path: str
    action: Literal["created", "modified", "deleted"]
    linesAdded: Optional[int] = None
    linesRemoved: Optional[int] = None


class NodeExecutionReceipt(BaseModel):
    nodeId: str
    status: NodeStatus
    input: Optional[str] = None
    output: Optional[str] = None
    evidence: Optional[str] = None
    commands: Optional[list[str]] = None
    filesChanged: Optional[list[FileChange]] = None
    retryReason: Optional[str] = None
    startedAt: Optional[str] = None
    finishedAt: Optional[str] = None


class PendingHumanGate(BaseModel):
    nodeId: str
    kind: Literal["criteria", "plan", "final", "extra_files"]
    title: str
    summary: str
    editableText: Optional[str] = None
    extraFiles: Optional[list[str]] = None


class RunRecord(BaseModel):
    id: str
    workflowId: str
    status: RunStatus
    attempt: int
    maxAttempts: int
    currentNodeId: Optional[str] = None
    nodeStatuses: dict[str, NodeStatus] = Field(default_factory=dict)
    receipts: dict[str, NodeExecutionReceipt] = Field(default_factory=dict)
    events: list[ConsoleEvent] = Field(default_factory=list)
    filesChanged: list[FileChange] = Field(default_factory=list)
    pendingGate: Optional[PendingHumanGate] = None
    objective: str = ""
    constraints: str = ""
    targetRepo: str = ""
    mainTargetFile: str = ""
    targetFiles: list[str] = Field(default_factory=list)
    approvedExtraFiles: list[str] = Field(default_factory=list)
    validateCommand: str = ""
    criteria: list[str] = Field(default_factory=list)
    plan: str = ""
    validationEvidence: Optional[str] = None
    lastError: Optional[str] = None
    startedAt: str
    updatedAt: str
    finishedAt: Optional[str] = None
    baselineCommit: Optional[str] = None


class HumanGateDecision(BaseModel):
    action: Literal["approve", "reject", "edit"]
    editedText: Optional[str] = None
    feedback: Optional[str] = None


class StartRunBody(BaseModel):
    workflowId: str = "default"
