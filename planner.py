#!/usr/bin/env python3
"""Planner with decomposition, confidence modeling, and adaptive replanning.

Core design:
- Hierarchical task decomposition
- Confidence scoring for each task
- Replanning triggers based on validation failures
- Risk estimation for changes
- Dependency-aware execution planning
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import uuid
from typing import Any


class TaskKind(str, Enum):
    investigate = "investigate"
    plan = "plan"
    edit = "edit"
    verify = "verify"
    review = "review"
    reflect = "reflect"


@dataclass
class PlanNode:
    """A node in a task decomposition tree."""
    id: str
    kind: TaskKind
    description: str
    acceptance_criteria: str = ""
    estimated_cost: float = 1.0
    risk_level: str = "medium"  # low, medium, high, critical
    confidence: float = 0.5  # 0.0 to 1.0
    parent_id: str | None = None
    children: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def investigate(cls, desc: str, *, confidence: float = 0.3) -> PlanNode:
        return cls(
            id=str(uuid.uuid4())[:12],
            kind=TaskKind.investigate,
            description=desc,
            confidence=confidence,
            risk_level="low",
            estimated_cost=0.5,
        )

    @classmethod
    def edit(cls, desc: str, *, risk: str = "medium", confidence: float = 0.5) -> PlanNode:
        return cls(
            id=str(uuid.uuid4())[:12],
            kind=TaskKind.edit,
            description=desc,
            confidence=confidence,
            risk_level=risk,
            estimated_cost=2.0,
        )

    @classmethod
    def verify(cls, desc: str, *, confidence: float = 0.8) -> PlanNode:
        return cls(
            id=str(uuid.uuid4())[:12],
            kind=TaskKind.verify,
            description=desc,
            confidence=confidence,
            risk_level="low",
            estimated_cost=1.0,
        )


class Planner:
    """A planner that decomposes goals, estimates confidence, and replans on failure."""

    def __init__(self) -> None:
        self._plan: dict[str, PlanNode] = {}
        self._execution_order: list[str] = []
        self._failed: set[str] = set()

    def decompose(self, goal: str) -> list[PlanNode]:
        """Decompose a goal into executable subtasks.

        Strategy:
        1. Always start with investigation (low confidence, low cost)
        2. Then plan (medium confidence)
        3. Then execute (higher risk, needs verification)
        4. Then verify (high confidence in mechanism)
        """
        tasks: list[PlanNode] = []

        # Phase 1: Investigate
        inv = PlanNode.investigate(f"Understand {goal}", confidence=0.3)
        tasks.append(inv)

        # Phase 2: Plan
        plan_node = PlanNode(
            id=str(uuid.uuid4())[:12],
            kind=TaskKind.plan,
            description=f"Design approach for {goal}",
            confidence=0.5,
            risk_level="low",
            estimated_cost=1.0,
            dependencies=[inv.id],
        )
        tasks.append(plan_node)

        # Phase 3: Execute
        exec_node = PlanNode.edit(
            f"Implement {goal}",
            risk="medium",
            confidence=0.6,
        )
        exec_node.dependencies = [plan_node.id]
        tasks.append(exec_node)

        # Phase 4: Verify
        ver = PlanNode.verify(f"Validate {goal}", confidence=0.8)
        ver.dependencies = [exec_node.id]
        tasks.append(ver)

        return tasks

    def plan(self, goal: str) -> dict[str, Any]:
        """Create a complete plan for a goal."""
        tasks = self.decompose(goal)
        for task in tasks:
            self._plan[task.id] = task

        return {
            "goal": goal,
            "tasks": [
                {
                    "id": t.id,
                    "kind": t.kind.value,
                    "description": t.description,
                    "confidence": t.confidence,
                    "risk": t.risk_level,
                    "dependencies": t.dependencies,
                }
                for t in tasks
            ],
            "total_confidence": self._aggregate_confidence(tasks),
            "total_risk": self._aggregate_risk(tasks),
        }

    def next_ready_tasks(self) -> list[str]:
        """Return the next tasks ready to execute (all dependencies met)."""
        ready = []
        for task_id, task in self._plan.items():
            if task_id in self._execution_order:
                continue
            if all(self._dep_satisfied(task, dep) for dep in task.dependencies):
                ready.append(task_id)
        return sorted(ready, key=lambda t: -self._plan[t].confidence)

    def _dep_satisfied(self, task: PlanNode, dep: str) -> bool:
        if dep not in self._execution_order:
            return False
        # Only recovery nodes may follow a failed attempt.
        return dep not in self._failed or bool(task.metadata.get("recovery"))

    def mark_executed(self, task_id: str, result: dict[str, Any] | None = None) -> None:
        """Mark a task as executed and optionally update its outcome."""
        if task_id not in self._execution_order:
            self._execution_order.append(task_id)
        if result:
            self._plan[task_id].metadata["result"] = result

    def replan_after_failure(self, failed_task_id: str, root_cause: str) -> list[PlanNode]:
        """Replan after a task fails.

        Strategy:
        1. Lower confidence on the failed task
        2. Record the failed attempt as executed so the diagnostic pass can follow
        3. Add a diagnostic task after the failed task before retrying
        4. Consider alternative approaches if confidence is very low
        """
        if failed_task_id not in self._plan:
            return []

        failed = self._plan[failed_task_id]
        failed.confidence = max(0.0, failed.confidence - 0.2)
        self.mark_executed(failed_task_id, {"status": "failed", "root_cause": root_cause})
        self._failed.add(failed_task_id)

        # A recovery pass should only begin after understanding the failure.
        diag = PlanNode.investigate(
            f"Diagnose failure in {failed.description}: {root_cause}",
            confidence=0.4,
        )
        diag.dependencies = [failed_task_id]
        diag.metadata["recovery"] = True
        self._plan[diag.id] = diag
        out = [diag]

        # If confidence is now very low, add an alternative exploration
        if failed.confidence < 0.3:
            alt = PlanNode(
                id=str(uuid.uuid4())[:12],
                kind=TaskKind.plan,
                description=f"Explore alternative approach for {failed.description}",
                confidence=0.4,
                risk_level="medium",
                estimated_cost=1.5,
                dependencies=[diag.id],
            )
            self._plan[alt.id] = alt
            out.append(alt)

        # Retry replaces the failed node for everything downstream of it.
        retry = PlanNode(
            id=str(uuid.uuid4())[:12],
            kind=failed.kind,
            description=f"Retry: {failed.description}",
            confidence=failed.confidence,
            risk_level=failed.risk_level,
            estimated_cost=failed.estimated_cost,
            dependencies=[out[-1].id],
        )
        self._plan[retry.id] = retry
        for node in self._plan.values():
            if node.id != retry.id and failed_task_id in node.dependencies and not node.metadata.get("recovery"):
                node.dependencies = [retry.id if d == failed_task_id else d for d in node.dependencies]
        out.append(retry)
        return out

    def _aggregate_confidence(self, tasks: list[PlanNode]) -> float:
        """Compute overall plan confidence (conservative: use minimum)."""
        if not tasks:
            return 1.0
        return min(t.confidence for t in tasks)

    def _aggregate_risk(self, tasks: list[PlanNode]) -> str:
        """Compute overall plan risk level (conservative: use maximum)."""
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        levels = [task.risk_level for task in tasks]
        max_level = max((risk_order.get(l, 0), l) for l in levels)
        return max_level[1]


__all__ = ["Planner", "PlanNode", "TaskKind"]
