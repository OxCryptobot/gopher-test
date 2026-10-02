#!/usr/bin/env python3
"""Tests for the planner with confidence and replanning."""
from __future__ import annotations

import unittest

from planner import Planner, PlanNode, TaskKind


class PlannerTests(unittest.TestCase):
    def test_decompose_creates_phases(self) -> None:
        planner = Planner()
        tasks = planner.decompose("fix a bug")

        kinds = [t.kind for t in tasks]
        self.assertEqual(kinds[0], TaskKind.investigate)
        self.assertEqual(kinds[1], TaskKind.plan)
        self.assertEqual(kinds[2], TaskKind.edit)
        self.assertEqual(kinds[3], TaskKind.verify)

    def test_plan_creates_ordered_tasks(self) -> None:
        planner = Planner()
        result = planner.plan("add a feature")

        self.assertIn("goal", result)
        self.assertIn("tasks", result)
        self.assertGreater(len(result["tasks"]), 0)
        self.assertIn("total_confidence", result)
        self.assertIn("total_risk", result)

    def test_confidence_is_conservative(self) -> None:
        planner = Planner()
        tasks = planner.decompose("test task")

        confidences = [t.confidence for t in tasks]
        self.assertTrue(all(0.0 <= c <= 1.0 for c in confidences))

        # Aggregate should be minimum (conservative)
        agg = planner._aggregate_confidence(tasks)
        self.assertEqual(agg, min(confidences))

    def test_next_ready_tasks_respects_dependencies(self) -> None:
        planner = Planner()
        tasks = planner.decompose("work")
        for task in tasks:
            planner._plan[task.id] = task

        # Initially, only tasks with no dependencies are ready
        ready = planner.next_ready_tasks()
        self.assertEqual(len(ready), 1)
        self.assertEqual(planner._plan[ready[0]].kind, TaskKind.investigate)

        # After executing the investigate task, plan becomes ready
        planner.mark_executed(ready[0])
        ready = planner.next_ready_tasks()
        self.assertEqual(len(ready), 1)
        self.assertEqual(planner._plan[ready[0]].kind, TaskKind.plan)

    def test_replan_after_failure(self) -> None:
        planner = Planner()
        tasks = planner.decompose("risky task")
        for task in tasks:
            planner._plan[task.id] = task
            if task.kind == TaskKind.edit:
                edit_task = task

        initial_conf = edit_task.confidence
        recovery_tasks = planner.replan_after_failure(edit_task.id, "patch failed to compile")

        # Confidence should decrease
        self.assertLess(planner._plan[edit_task.id].confidence, initial_conf)

        # A diagnostic task should be added
        self.assertGreater(len(recovery_tasks), 0)
        self.assertEqual(recovery_tasks[0].kind, TaskKind.investigate)

    def test_replan_adds_dependency_chain_after_failure(self) -> None:
        planner = Planner()
        tasks = planner.decompose("break it")
        for task in tasks:
            planner._plan[task.id] = task
            if task.kind == TaskKind.edit:
                edit_task = task

        recovery_tasks = planner.replan_after_failure(edit_task.id, "runtime crash")
        diag = recovery_tasks[0]
        self.assertIn(edit_task.id, diag.dependencies)

        if len(recovery_tasks) > 1:
            alt = recovery_tasks[1]
            self.assertIn(diag.id, alt.dependencies)

    def test_replan_makes_recovery_ready_after_failed_attempt(self) -> None:
        planner = Planner()
        tasks = planner.decompose("broken task")
        for task in tasks:
            planner._plan[task.id] = task
            if task.kind == TaskKind.edit:
                edit_task = task

        recovery_tasks = planner.replan_after_failure(edit_task.id, "runtime crash")
        ready = planner.next_ready_tasks()
        self.assertIn(recovery_tasks[0].id, ready)

    def test_replan_explores_alternatives_when_very_low_confidence(self) -> None:
        planner = Planner()
        tasks = planner.decompose("task")
        for task in tasks:
            planner._plan[task.id] = task
            if task.kind == TaskKind.edit:
                edit_task = task

        # Simulate multiple failures to drop confidence very low
        edit_task.confidence = 0.25
        recovery_tasks = planner.replan_after_failure(edit_task.id, "repeated failure")

        # Should have both diagnostic and alternative
        self.assertGreaterEqual(len(recovery_tasks), 2)
        kinds = [t.kind for t in recovery_tasks]
        self.assertIn(TaskKind.investigate, kinds)
        self.assertIn(TaskKind.plan, kinds)

    def test_node_factories_create_correct_kinds(self) -> None:
        inv = PlanNode.investigate("look around")
        self.assertEqual(inv.kind, TaskKind.investigate)
        self.assertLess(inv.confidence, 0.5)

        edt = PlanNode.edit("make change")
        self.assertEqual(edt.kind, TaskKind.edit)
        self.assertGreater(edt.estimated_cost, 1.0)

        ver = PlanNode.verify("check result")
        self.assertEqual(ver.kind, TaskKind.verify)
        self.assertGreater(ver.confidence, 0.6)


if __name__ == "__main__":
    unittest.main()
