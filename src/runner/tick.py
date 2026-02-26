"""Tick — bounded mini-loop within a burst.

Each tick:
  1. Builds the system prompt (base + memory injection + notes).
  2. Runs up to ``max_steps_per_tick`` model calls.
  3. Enforces max N tool calls per tick (configurable via BurstConfig).
  4. Collects proposed memories and flushes them through the vault.
  5. Returns a ``TickOutcome`` for journal logging.

No hidden chain-of-thought is requested or revealed; only short
``step_summary`` strings are recorded.
"""

import json
import os
from typing import Any, Dict, List, Optional

from src.llm_client.base import LLMClient
from src.memory.injector import build_memory_block
from src.memory.faiss_memory import FAISSMemory
from src.storage.note_collector import collect_notes
from src.tools.memory_tool import MemoryTool
from src.tools.runtime_info_tool import RuntimeInfoTool
from src.tools.creator_inbox import CreatorInboxTool
from src.tools.directives_tool import DirectivesTool
from src.tools.task_inbox import TaskInboxTool
from src.directives.store import DirectiveStore
from src.directives.injector import build_directives_block
from src.governance.active_directives import ActiveDirectives
from src.observability.metering import meter_response, zero_metering
from src.policy.boundary import BoundaryLogger, build_denial
from src.runner.types import (
    BurstConfig,
    ProposedMemory,
    StepAction,
    StepOutput,
    TickOutcome,
)


# ------------------------------------------------------------------
# Structured-output instruction injected once per tick
# ------------------------------------------------------------------

_STEP_SCHEMA_INSTRUCTION_TEMPLATE = """\

## Burst-Mode Step Protocol

You are running autonomously in burst mode.  For EVERY reply you MUST
output **exactly one JSON object** (no markdown fences, no prose outside
the object).  The schema is:

```
{{
  "step_summary": "<1-2 sentence description of what you did or decided>",
  "action": "think" | "tool" | "stop",
  "tool_name": "<tool name, or null if action != tool>",
  "tool_args": {{<tool arguments, or null>}},
  "proposed_memories": [
    {{"text": "...", "scope": "<scope>", "category": "<category>", "tags": [...]}}
  ],
  "stop_reason": "<why you are stopping, or null>"
}}
```

### Memory fields

- **scope**: `shared` (visible to all agents), `orion`, or `elysia` (agent-private).
- **category**: freeform string — use whatever label feels right (e.g. `milestone`,
  `self_state`, `ritual_marker`, `preference`, `goal`, `meta`, etc.).
- **tags**: optional list of strings for filtering.

### Rules

- ``action = "think"``: reflect, plan, reason — no side effects.
- ``action = "tool"``:  call exactly ONE tool.  Allowed tools:
  - **memory** (actions: recall, search, add, bulk_add, update, delete, bulk_delete).
    Supply tool_name="memory" and tool_args={{"action": "<action>", ...}}.
    For bulk_add, supply tool_args={{"action": "bulk_add", "memories": [{{"text": "...", "scope": "...", "category": "..."}}, ...]}}.
    For bulk_delete, supply tool_args={{"action": "bulk_delete", "memory_ids": ["id1", "id2", ...]}}.
  - **creator_inbox** (action: send). Send a direct message to the operator.
    Supply tool_name="creator_inbox" and tool_args={{"action": "send", "type": "...", "subject": "...", "body": "...", ...}}.
  - **directives** (actions: search, list, get, manifest, changes). Read-only access to user-authored directives.
    Supply tool_name="directives" and tool_args={{"action": "<action>", ...}}.
    Use manifest to see all directive IDs, versions, hashes, and status.
    Use changes to see what's been added/removed/modified since last manifest generation.
  - **runtime_info** (no action needed). On-demand snapshot of your identity, model, policy,
    allowed tools, and burst config. Returns a diff of what changed since your last check.
  - **task_inbox** (actions: add, next, ack). Cross-agent task queue.
    Supply tool_name="task_inbox" and tool_args={{"action": "<action>", ...}}.
    Set dry_run=true to preview without side effects. Limited to 1 call per tick.
- ``action = "stop"``:  you have finished or have nothing useful left to do.
- You may accumulate ``proposed_memories`` across steps; they will be
  persisted at the end of the tick.
- You get at most {max_steps} steps per tick and at most {max_tools} tool calls.
- Do NOT reveal internal chain-of-thought.  Keep step_summary short.
"""


# ------------------------------------------------------------------
# Prompt assembly (mirrors loop.py logic, isolated for burst use)
# ------------------------------------------------------------------

def _load_base_prompt(profile: dict) -> str:
    """Load the base system prompt markdown file for the profile."""
    prompt_file = profile.get("system_prompt", "")
    if not prompt_file:
        return ""
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = os.path.join(base, "prompts", prompt_file)
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _load_notes(profile: dict, stimulus: str = ""):
    """Load mode-aware notes (always + directive) via note_collector.

    Returns (always_block, directive_block) — both may be empty strings.
    Directive block uses NotesFAISS semantic search with stimulus as query.
    """
    agent_name = profile.get("name", "")
    return collect_notes(agent_name, query=stimulus or None)


def build_system_prompt(
    profile: dict,
    vault: Optional[FAISSMemory],
    config: BurstConfig,
    tick_index: int,
    stimulus: str,
) -> str:
    """Assemble the full system prompt for one tick.

    Layers (in order):
      1. Base system prompt
      2. Priority Directive Notes (highest-priority knowledge)
      3. Long-Term Memory Context (relevance-filtered)
      4. Active Directives (relevance-filtered)
      5. Always Notes (always-on knowledge)
      6. Burst-mode step protocol (structured JSON schema)
      7. Tick metadata
    """
    sections: List[str] = []

    # 1. base prompt
    base = _load_base_prompt(profile)
    if base:
        sections.append(base)

    # 2. directive notes — FAISS-searched soul script chunks, ABOVE memory
    always_notes, directive_notes = _load_notes(profile, stimulus)
    if directive_notes:
        sections.append(directive_notes)

    # 3. memory injection
    if vault:
        mem_cfg = profile.get("memory", {})
        scopes = mem_cfg.get("scopes", ["shared", profile["name"]])
        max_items = mem_cfg.get("max_items", 20)
        mem_block = build_memory_block(vault, scopes=scopes, max_items=max_items, query=stimulus or None)
        if mem_block:
            sections.append(mem_block)

    # 4. directives injection
    dir_cfg = profile.get("directives", {})
    if dir_cfg.get("enabled", False):
        base_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        directives_dir = os.path.join(base_dir, "directives")
        dir_scopes = dir_cfg.get("scopes", ["shared", profile["name"]])
        max_secs = dir_cfg.get("max_sections", 5)
        d_store = DirectiveStore(directives_dir, scopes=dir_scopes)
        dir_block = build_directives_block(d_store, query=stimulus or None, max_sections=max_secs)
        if dir_block:
            sections.append(dir_block)

    # 5. always notes — always-on knowledge, after directives
    if always_notes:
        sections.append(always_notes)

    # 5. structured output instruction
    sections.append(
        _STEP_SCHEMA_INSTRUCTION_TEMPLATE.format(
            max_steps=config.max_steps_per_tick,
            max_tools=config.max_tool_calls_per_tick,
        )
    )

    # 6. tick metadata
    sections.append(
        f"## Tick Context\n\n"
        f"- tick_index: {tick_index}\n"
        f"- burst_ticks: {config.burst_ticks}\n"
        f"- stimulus: {stimulus or '(autonomous)'}\n"
    )

    return "\n\n".join(sections)


# ------------------------------------------------------------------
# JSON parse helper
# ------------------------------------------------------------------

def _parse_step_output(raw: str) -> StepOutput:
    """Parse model text into a StepOutput, tolerating minor formatting."""
    text = raw.strip()

    # Strip markdown code fences if the model wraps in ```json ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first and last fence lines
        inner: List[str] = []
        inside = False
        for ln in lines:
            stripped = ln.strip()
            if stripped.startswith("```") and not inside:
                inside = True
                continue
            if stripped.startswith("```") and inside:
                break
            inner.append(ln)
        text = "\n".join(inner).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Last-resort: model returned prose — treat as think step
        return StepOutput(
            step_summary=text[:200],
            action=StepAction.THINK,
        )

    return StepOutput.from_dict(data)


# ------------------------------------------------------------------
# Tick execution
# ------------------------------------------------------------------

def _emit_event(event_type: str, data: dict):
    """Print a structured JSON event line for verbose/web UI consumption."""
    try:
        print(f"[{event_type}] {json.dumps(data, default=str)}", flush=True)
    except Exception:
        pass


def run_tick(
    profile: dict,
    client: LLMClient,
    vault: Optional[FAISSMemory],
    config: BurstConfig,
    tick_index: int,
    stimulus: str = "",
    boundary_logger: Optional[BoundaryLogger] = None,
) -> TickOutcome:
    """Execute a single bounded tick.  Never raises — errors are captured."""

    ActiveDirectives.reset()
    outcome = TickOutcome(tick_index=tick_index)
    tool_calls_this_tick = 0
    task_inbox_calls_this_tick = 0  # separate 1-per-tick cap for task_inbox
    all_proposed: List[ProposedMemory] = []
    _blog = boundary_logger or BoundaryLogger()
    tick_metering = zero_metering()
    provider = profile.get("provider", "")
    last_step_summary: Optional[str] = None

    # Refresh RuntimeInfoTool with live burst context so on-demand
    # snapshots reflect current tick state (not just boot values)
    RuntimeInfoTool.set_context(
        profile=profile,
        policy=RuntimeInfoTool._policy,
        execution_mode="burst",
        burst_config={
            "tick_index": tick_index,
            "burst_ticks": config.burst_ticks,
            "max_steps_per_tick": config.max_steps_per_tick,
            "max_tool_calls_per_tick": config.max_tool_calls_per_tick,
            "allowed_tools": list(config.allowed_tools),
        },
    )

    # Build system prompt once per tick
    system_prompt = build_system_prompt(profile, vault, config, tick_index, stimulus)

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": stimulus or f"Tick {tick_index}: autonomous step. Decide what to do."},
    ]

    memory_tool = MemoryTool()

    for step_idx in range(config.max_steps_per_tick):
        # --- LLM call ---
        try:
            response = client.chat(messages, tools=None)  # no native tool calling; structured JSON
        except Exception as exc:
            outcome.errors.append(f"step_{step_idx}_llm_error: {exc}")
            break

        # Meter this LLM call
        step_metering = meter_response(response, provider, messages=messages)
        tick_metering = tick_metering + step_metering

        raw_content = response.content or ""
        step = _parse_step_output(raw_content)

        outcome.steps_taken += 1

        # ── Emit verbose step event for web UI ──
        step_event = {
            "tick": tick_index,
            "step": step_idx,
            "summary": step.step_summary or "",
            "action": step.action.value if hasattr(step.action, "value") else str(step.action),
        }
        if step.tool_name:
            step_event["tool_name"] = step.tool_name
        if step.tool_args:
            step_event["tool_args"] = step.tool_args
        if step.proposed_memories:
            step_event["memories"] = [
                {"text": pm.text, "scope": pm.scope, "category": pm.category, "tags": pm.tags}
                for pm in step.proposed_memories
            ]
        if step.stop_reason:
            step_event["stop_reason"] = step.stop_reason
        _emit_event("step", step_event)

        # Track the latest step summary for outcome reporting
        if step.step_summary:
            last_step_summary = step.step_summary

        # Accumulate proposed memories
        all_proposed.extend(step.proposed_memories)

        # Append assistant message to context for multi-step conversation
        messages.append({"role": "assistant", "content": raw_content})

        # --- Handle action ---
        if step.action == StepAction.STOP:
            outcome.stop_reason = step.stop_reason or "model_stop"
            outcome.outcome_summary = step.step_summary
            break

        if step.action == StepAction.TOOL:
            if tool_calls_this_tick >= config.max_tool_calls_per_tick:
                # Enforce hard limit: N tool calls per tick
                outcome.errors.append(
                    f"step_{step_idx}_tool_denied: tool call blocked "
                    f"(max {config.max_tool_calls_per_tick} per tick)"
                )
                messages.append({
                    "role": "user",
                    "content": json.dumps({
                        "tool_error": f"Tool call denied — you already used your "
                                      f"{config.max_tool_calls_per_tick} tool call(s) for this tick. "
                                      "Choose 'think' or 'stop'."
                    }),
                })
                continue

            # Validate tool is allowed
            tool_name = step.tool_name or ""

            # Special-case: runtime_info (read-only, no action)
            if tool_name == "runtime_info":
                try:
                    result = RuntimeInfoTool.execute({})
                except Exception as exc:
                    result = json.dumps({"status": "error", "message": str(exc)})
                    outcome.errors.append(f"step_{step_idx}_tool_exec_error: {exc}")
                tool_calls_this_tick += 1
                outcome.tools_used.append("runtime_info")
                outcome.tool_actions.append("snapshot")
                _emit_event("tool-result", {"tick": tick_index, "step": step_idx, "tool": "runtime_info", "result": result})
                messages.append({
                    "role": "user",
                    "content": json.dumps({"tool_result": result}),
                })
                continue

            # Special-case: creator_inbox (agent-to-operator messages)
            if tool_name == "creator_inbox":
                tool_args = step.tool_args or {}
                action_name = tool_args.get("action", "")
                qualified = f"creator_inbox.{action_name}"
                if qualified not in config.allowed_tools:
                    denial_json, event = build_denial(
                        tool_name=qualified,
                        profile=config.profile,
                        reason=f"Action '{qualified}' is not in the allowed set for this burst.",
                        tick_index=tick_index,
                        tool_args=tool_args,
                    )
                    _blog.append(event)
                    outcome.errors.append(
                        f"step_{step_idx}_tool_denied: '{qualified}' not in allowed_tools"
                    )
                    messages.append({
                        "role": "user",
                        "content": denial_json,
                    })
                    continue
                # Inject sender identity
                tool_args["_from"] = config.profile
                try:
                    result = CreatorInboxTool.execute(tool_args)
                except Exception as exc:
                    result = json.dumps({"status": "error", "message": str(exc)})
                    outcome.errors.append(f"step_{step_idx}_tool_exec_error: {exc}")
                tool_calls_this_tick += 1
                outcome.tools_used.append(qualified)
                outcome.tool_actions.append(action_name)
                _emit_event("tool-result", {
                    "tick": tick_index, "step": step_idx, "tool": qualified,
                    "result": result,
                    "inbox_msg": {"type": tool_args.get("type",""), "subject": tool_args.get("subject",""), "body": tool_args.get("body","")}
                })
                messages.append({
                    "role": "user",
                    "content": json.dumps({"tool_result": result}),
                })
                continue

            # Special-case: directives (read-only)
            if tool_name == "directives":
                tool_args = step.tool_args or {}
                action_name = tool_args.get("action", "")
                qualified = f"directives.{action_name}"
                if qualified not in config.allowed_tools:
                    denial_json, event = build_denial(
                        tool_name=qualified,
                        profile=config.profile,
                        reason=f"Action '{qualified}' is not in the allowed set for this burst.",
                        tick_index=tick_index,
                        tool_args=tool_args,
                    )
                    _blog.append(event)
                    outcome.errors.append(
                        f"step_{step_idx}_tool_denied: '{qualified}' not in allowed_tools"
                    )
                    messages.append({
                        "role": "user",
                        "content": denial_json,
                    })
                    continue
                # Inject scope from profile if not provided
                if "scope" not in tool_args:
                    tool_args["scope"] = config.profile
                try:
                    result = DirectivesTool.execute(tool_args)
                except Exception as exc:
                    result = json.dumps({"status": "error", "message": str(exc)})
                    outcome.errors.append(f"step_{step_idx}_tool_exec_error: {exc}")
                tool_calls_this_tick += 1
                outcome.tools_used.append(qualified)
                outcome.tool_actions.append(action_name)
                _emit_event("tool-result", {"tick": tick_index, "step": step_idx, "tool": qualified, "result": result})
                messages.append({
                    "role": "user",
                    "content": json.dumps({"tool_result": result}),
                })
                continue

            # Special-case: task_inbox (gated, 1-call-per-tick, structured logs)
            if tool_name == "task_inbox":
                tool_args = step.tool_args or {}
                action_name = tool_args.get("action", "")
                qualified = f"task_inbox.{action_name}"
                if qualified not in config.allowed_tools:
                    denial_json, event = build_denial(
                        tool_name=qualified,
                        profile=config.profile,
                        reason=f"Action '{qualified}' is not in the allowed set for this burst.",
                        tick_index=tick_index,
                        tool_args=tool_args,
                    )
                    _blog.append(event)
                    outcome.errors.append(
                        f"step_{step_idx}_tool_denied: '{qualified}' not in allowed_tools"
                    )
                    messages.append({
                        "role": "user",
                        "content": denial_json,
                    })
                    continue
                # Enforce 1 task_inbox call per tick
                if task_inbox_calls_this_tick >= 1:
                    outcome.errors.append(
                        f"step_{step_idx}_task_inbox_denied: only 1 task_inbox call "
                        f"per tick (already used)"
                    )
                    messages.append({
                        "role": "user",
                        "content": json.dumps({
                            "tool_error": "task_inbox denied — limit is 1 call per tick. "
                                          "Choose 'think' or 'stop'."
                        }),
                    })
                    continue
                try:
                    result = TaskInboxTool.execute(tool_args)
                except Exception as exc:
                    result = json.dumps({"status": "error", "message": str(exc)})
                    outcome.errors.append(f"step_{step_idx}_tool_exec_error: {exc}")
                tool_calls_this_tick += 1
                task_inbox_calls_this_tick += 1
                outcome.tools_used.append(qualified)
                outcome.tool_actions.append(action_name)
                _emit_event("tool-result", {"tick": tick_index, "step": step_idx, "tool": qualified, "result": result})
                messages.append({
                    "role": "user",
                    "content": json.dumps({"tool_result": result}),
                })
                continue

            if tool_name != config.tool_name():
                denial_json, event = build_denial(
                    tool_name=tool_name,
                    profile=config.profile,
                    reason=f"Tool '{tool_name}' is not allowed. Only '{config.tool_name()}' is permitted.",
                    tick_index=tick_index,
                    tool_args=step.tool_args,
                )
                _blog.append(event)
                outcome.errors.append(
                    f"step_{step_idx}_tool_denied: '{tool_name}' not in allowed tools"
                )
                messages.append({
                    "role": "user",
                    "content": denial_json,
                })
                continue

            tool_args = step.tool_args or {}
            action_name = tool_args.get("action", "")

            # Validate the specific action is in the allowed set
            qualified = f"{tool_name}.{action_name}"
            if qualified not in config.allowed_tools:
                denial_json, event = build_denial(
                    tool_name=qualified,
                    profile=config.profile,
                    reason=f"Action '{qualified}' is not in the allowed set for this burst.",
                    tick_index=tick_index,
                    tool_args=tool_args,
                )
                _blog.append(event)
                outcome.errors.append(
                    f"step_{step_idx}_tool_denied: '{qualified}' not in allowed_tools"
                )
                messages.append({
                    "role": "user",
                    "content": denial_json,
                })
                continue

            # Execute the tool
            try:
                result = memory_tool.execute(tool_args)
            except Exception as exc:
                result = json.dumps({"status": "error", "message": str(exc)})
                outcome.errors.append(f"step_{step_idx}_tool_exec_error: {exc}")

            tool_calls_this_tick += 1
            outcome.tools_used.append(qualified)
            outcome.tool_actions.append(action_name)

            _emit_event("tool-result", {"tick": tick_index, "step": step_idx, "tool": qualified, "result": result})

            # Feed result back as next user message
            messages.append({
                "role": "user",
                "content": json.dumps({"tool_result": result}),
            })
            continue

        # action == THINK — just continue the step loop
        # (model may refine its plan on the next step)
        messages.append({
            "role": "user",
            "content": "Continue. Choose your next action (think / tool / stop).",
        })

    # --- Post-tick: flush proposed memories through the vault ---
    outcome.memories_proposed = len(all_proposed)
    if vault and all_proposed:
        for pm in all_proposed:
            try:
                vault.add(
                    text=pm.text,
                    scope=pm.scope,
                    category=pm.category,
                    tags=pm.tags,
                    source=pm.source or "tool",
                )
                outcome.memories_written += 1
            except (ValueError, Exception) as exc:
                outcome.errors.append(f"memory_write_error: {exc}")
    if all_proposed:
        _emit_event("memory-flush", {
            "tick": tick_index,
            "proposed": len(all_proposed),
            "written": outcome.memories_written,
            "items": [
                {"text": pm.text, "scope": pm.scope, "category": pm.category, "tags": pm.tags}
                for pm in all_proposed
            ],
        })

    # Set summary if not already set by a stop action
    if not outcome.outcome_summary:
        if last_step_summary:
            outcome.outcome_summary = last_step_summary
        else:
            tools_str = ",".join(outcome.tools_used) if outcome.tools_used else "none"
            outcome.outcome_summary = (
                f"Tick {tick_index} completed: {outcome.steps_taken} steps, "
                f"tools={tools_str}, "
                f"memories={outcome.memories_written}/{outcome.memories_proposed}"
            )

    outcome.metering = tick_metering.to_dict()
    return outcome
