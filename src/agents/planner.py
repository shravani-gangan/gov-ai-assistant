"""
Planner Agent — decomposes user requests into executable SubTask DAGs.
"""
from __future__ import annotations

import json
import re
from typing import Any

import structlog

from src.agents.base import BaseAgent
from src.core.config import get_config
from src.core.schemas import AgentRole, ExecutionPlan, SubTask, TaskStatus
from src.memory.manager import MemoryManager
from src.models.ollama_client import OllamaClient

logger = structlog.get_logger(__name__)

_PLANNER_SYSTEM = """\
You are an expert government workflow planner. Decompose user requests into
structured subtasks for a multi-agent AI system. Always return valid JSON.
"""

_PLANNER_PROMPT = """\
Decompose this government officer request into subtasks.

REQUEST: {request}
HAS_DOCUMENT: {has_document}

Return ONLY a JSON object:
{{
  "tasks": [
    {{
      "name": "<task name>",
      "description": "<what to do>",
      "assigned_agent": "<planner|analyst|drafter|critic|hermes>",
      "dependencies": [],
      "priority": <1-5>,
      "estimated_tokens": <int>
    }}
  ],
  "ambiguities_detected": ["<unclear aspect>"]
}}
"""


class PlannerAgent(BaseAgent):
    role = AgentRole.PLANNER

    def __init__(self, memory: MemoryManager) -> None:
        config = get_config()
        llm = OllamaClient(model=config.ollama.planner_model)
        super().__init__(llm=llm, memory=memory)

    async def _run(self, request: str, has_document: bool = False) -> ExecutionPlan:
        prompt = _PLANNER_PROMPT.format(
            request=request, has_document=has_document
        )
        response = await self._llm.generate(
            prompt=prompt, system=_PLANNER_SYSTEM, temperature=0.0
        )
        parsed = self._parse_json(response)

        raw_tasks = parsed.get("tasks", [])
        # Assign sequential IDs so dependencies can reference them
        task_id_map: dict[int, str] = {}
        subtasks: list[SubTask] = []

        for i, t in enumerate(raw_tasks):
            task = SubTask(
                name=t.get("name", f"task_{i}"),
                description=t.get("description", ""),
                assigned_agent=AgentRole(t.get("assigned_agent", "analyst")),
                dependencies=[task_id_map[j] for j in t.get("dependencies", []) if j in task_id_map],
                priority=int(t.get("priority", 3)),
                estimated_tokens=int(t.get("estimated_tokens", 500)),
                status=TaskStatus.PENDING,
            )
            task_id_map[i] = task.task_id
            subtasks.append(task)

        return ExecutionPlan(
            original_request=request,
            tasks=subtasks,
            estimated_total_tokens=sum(t.estimated_tokens for t in subtasks),
            ambiguities_detected=parsed.get("ambiguities_detected", []),
        )

    def _parse_json(self, response: str) -> dict[str, Any]:
        cleaned = re.sub(r"^```(?:json)?\n?", "", response.strip())
        cleaned = re.sub(r"\n?```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            self._log.warning("planner.json_parse_failed")
            return {"tasks": [], "ambiguities_detected": ["Failed to parse plan"]}