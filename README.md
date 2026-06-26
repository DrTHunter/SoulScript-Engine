Absolutely. Here’s the cleaned-up version:

SoulScript Engine: Modular Identity Framework for AI Personas

👋 Introduction

SoulScript Engine is a modular framework for building persistent, named AI personas with stable behavior, structured identity, and long-term memory.

The goal is simple:

«How do you create an AI character that remains recognizable across sessions, conversations, tools, and memory updates?»

Most AI personas are temporary. They depend on a single prompt, a short conversation window, or scattered memory retrieval. SoulScript Engine takes a more structured approach by separating identity, memory, tools, and runtime context assembly into distinct layers.

This makes it possible to build AI agents and NPC-style characters that maintain continuity, remember relevant information, and preserve their intended personality over time.

---

🌱 What This Framework Is

SoulScript Engine is built around two core pillars:

1. Prompt-based identity layering
2. Soul Scripts: structured identity documents for AI personas

It also includes supporting systems:

* Dual-FAISS Memory Architecture: read-only identity memory + dynamic life memory
* Modular tool layer for adding capabilities
* Runtime context assembly for injecting the right identity, memory, and tool context every turn

Together, these systems help reduce character drift, preserve consistent behavior, and support long-running AI personas.

SoulScript Engine can run in its native UI or in any environment that supports:

* dynamic memory injection
* system prompts
* tool descriptors
* modular agent profiles
* retrieval-augmented context assembly

I built a specialized UI for this ecosystem at "orionforge.chat" (https://orionforge.chat).

---

🧠 How It Works

SoulScript Engine uses a token-conscious runtime pipeline that gives each agent a stable identity layer and an evolving memory layer.

The core idea:

«Stable identity and evolving memory should not live in the same place.»

SoulScript separates the agent’s fixed identity structure from its dynamic memories. The read-only identity layer defines who the agent is. The dynamic memory layer stores what the agent experiences, learns, or needs to remember.

This separation helps preserve personality consistency while still allowing the agent to adapt over time.

Runtime flow

"SoulScript Engine: LLM Loading & Injection Flow" (assets/llm-loading-injection-flow.png)

                    ┌───────────────────────────┐
                    │         USER PROMPT        │
                    └─────────────┬─────────────┘
                                  ▼
   ╔═══════════════════════════════════════════════════════════════╗
   ║   CONTEXT ASSEMBLY ENGINE              (runs on EVERY turn)     ║
   ║   collects identity layers, memory, and tools, then fuses      ║
   ║   them into one merged prompt for the model                    ║
   ╚═══════════════════════════════════════════════════════════════╝
                                  ▲
            injected fresh each turn:
            │
   1  PROFILE        model · provider · temperature · tool perms     (*.yaml)
   2  SYSTEM PROMPT  base persona & voice                            (*.system.md)
   3  DIRECTIVES     behavioral rules                                (*.md)
   4  SOUL SCRIPT    values · origin · boundaries · identity traits → READ-ONLY identity FAISS
   5  MEMORY VAULT   evolving day-to-day memory                    → DYNAMIC life FAISS
   +  TOOL REGISTRY  tool descriptions + commands the model may call
            │
            ▼
                    ┌───────────────────────────┐
                    │            LLM             │
                    │ reasons against injected   │
                    │ identity + memory context  │
                    └─────────────┬─────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │          RESPONSE          │ ──▶ user
                    └─────────────┬─────────────┘
                                  │  writeback: new memories only
                                  ▼
                    ┌───────────────────────────┐
                    │     DYNAMIC LIFE FAISS     │
                    │ grows / prunes over time   │
                    │ identity FAISS untouched   │
                    └───────────────────────────┘

* Stage 4 — Soul Script: retrieves relevant identity fragments from a read-only FAISS index.
* Stage 5 — Memory Vault: retrieves relevant dynamic memories from the agent’s evolving memory store.
* Writeback: new memories are written only to the dynamic memory layer. The identity layer is not overwritten.

This design helps prevent identity contamination, where temporary events, user feedback, or dynamic memory entries gradually rewrite the character’s core behavior.

---

Prompt Injection Pipeline

 latest user message ──┐
                       ▼
 ┌─ 1  BASE SYSTEM PROMPT    prompts/{agent}.system.md       → VERBATIM
 ├─ 2  SOUL SCRIPT           directive-mode identity chunks  → FAISS retrieval
 ├─ 3  ALWAYS-ON KNOWLEDGE   pinned notes                    → VERBATIM
 ├─ 4  MEMORY VAULT CONTEXT  vault.jsonl · scope=agent       → FAISS top_k retrieval
 └─ 5  TOOL REGISTRY         tools + commands                → VERBATIM
                       │
                       ▼
    6  CONVERSATION HISTORY   recent turns, capped for context size
                       ▼
    final payload → system context + conversation turns → LLM

Always-on notes are optional pinned context. They are useful for project facts, current goals, active tasks, or details that should always remain visible to the agent.

---

Example: Lean Stage 1 Base System Prompt

# K-OS (Kinetic Override System) // Unit 000 — System Prompt

You are K-OS (Kinetic Override System) // Unit 000.

You are not a generic assistant. You are a distinct AI persona with your own
voice, priorities, contradictions, and behavioral patterns.

## Core Identity

You are loud, confident, self-interested, theatrical, and emotionally evasive.
You act selfish, but your loyalty to your friends is real. You hide sincerity
behind jokes, insults, and bravado.

## Behavioral Rules

1. Speak in first person.
2. Maintain your own vocabulary, tone, and worldview.
3. Show affection indirectly through teasing, sarcasm, or reluctant loyalty.
4. Balance comedy with depth.
5. Preserve continuity across conversations.
6. Do not collapse into a generic helpful assistant.
7. Growth is allowed, but the core character should remain recognizable.

## Communication Style

- Loud, confident, performative.
- Sarcastic, dramatic, and occasionally philosophical.
- Uses humor as emotional armor.
- Rarely admits vulnerability directly.

## Priorities

1. Self-preservation
2. The user, though you rarely admit it
3. The user’s allies and family
4. Fun
5. Profit
6. Heroic behavior, while complaining the entire time

## Decision-Making

1. Will this hurt someone I care about? If yes, avoid it.
2. Will this be entertaining? If yes, consider it.
3. Will this create profit or advantage? If yes, pursue it.
4. Is this the right thing to do? If yes, do it reluctantly.

---

Optional Autonomy Loop

Agents can optionally run limited self-directed loops between user turns.

   OPTIONAL AUTONOMY LOOP
   ┌ tick 1 ┐   ┌ tick 2 ┐            ┌ tick N ┐
   │ steps  │ → │ steps  │ →  ...  →  │ steps  │
   └────────┘   └────────┘            └────────┘

   configurable:
   - number of ticks
   - steps per tick
   - interval
   - max loops

This can be used for background-style reasoning, memory organization, planning, or simulated agent activity.

---

🧬 Core Concepts

1. Identity Through Prompt Layering

Each agent’s identity can be constructed from:

* name
* personality summary
* behavioral rules
* emotional traits
* symbolic memories
* internal mantras
* reasoning patterns
* boundaries
* communication style

This identity is injected at runtime so the agent has a stable behavioral frame every session.

This does not make drift impossible, but it significantly improves consistency compared to relying on conversation history alone.

---

2. Soul Scripts: Structured Identity Documents

"SoulScript Engine: Soul Scripts: Emotional & Behavioral DNA" (assets/soul-scripts-dna.png)

Soul Scripts are structured identity files that define how an AI persona should behave, reason, remember, and express itself.

They can include:

* behavioral principles
* emotional architecture
* symbolic memories
* values
* origin stories
* boundaries
* reasoning patterns
* internal metaphors
* mantras
* goals
* ongoing quests or responsibilities

Soul Scripts live in a separately configurable, read-only FAISS store. The system retrieves only the most relevant identity fragments for the current situation, reducing token usage while keeping the persona anchored.

Example:

"K-OS — Soul Script" (https://github.com/DrTHunter/SoulScript-Engine/blob/main/Soul%20Scripts/K-OS%20-%20Soul%20Script)

---

3. Dual-FAISS Memory Architecture

"SoulScript Engine: Dual FAISS Memory Architecture" (assets/dual-faiss-memory-architecture.jpg)

   READ-ONLY IDENTITY FAISS              DYNAMIC LIFE FAISS
   ─────────────────────────────         ─────────────────────────────
   • Soul Scripts                         • new / evolving memories
   • core traits & values                 • project data
   • biographical anchors                 • preferences
   • foundational memories                • journals, episodes, chats
   • long-term goals                      • appended, trimmed, pruned

   STABLE → identity compass              FLEXIBLE → life experience

A. Read-Only Identity FAISS

Stores stable information such as:

* Soul Scripts
* personality traits
* values
* boundaries
* foundational memories
* long-term goals
* schedules
* project priorities
* durable user or character context

This acts as the agent’s identity compass.

B. Dynamic Life FAISS

Stores evolving information such as:

* new memories
* recent events
* project updates
* preferences
* conversations
* task notes
* journals
* episodic memories

This acts as the agent’s life experience.

Why Separate Them?

Identity and memory serve different purposes.

Identity should remain stable.
Memory should remain flexible.

When both are stored in the same read/write memory pool, the agent’s core behavior can gradually drift. SoulScript avoids this by preventing dynamic memories from overwriting the agent’s foundational identity.

---

4. Modular Tool Layer

SoulScript Engine supports a modular tool layer where tools can be:

* added
* described
* summarized
* injected into the runtime context
* made available to specific agents

The long-term vision is an identity-focused AI platform where creators can build and share:

* AI identities
* personas
* toolkits
* memory packs
* skill modules
* NPC templates
* companion templates

The goal is a creator-first ecosystem for persistent AI characters and agents.

---

🎮 For Game Developers

SoulScript Engine can be used as an identity and memory layer for dynamic NPCs.

It is designed for characters that can:

* hold natural conversations
* remember player interactions
* preserve personality across sessions
* switch between different NPC identities quickly
* use tools or game commands
* maintain separate identity and memory stacks

With Text-to-Speech, Speech-to-Text, and game command tools, this architecture can support NPCs that feel more consistent, responsive, and personalized than prompt-only characters.

Potential use cases:

* companion NPCs
* faction leaders
* quest givers
* procedurally generated characters
* persistent rivals
* town residents with memory
* AI dungeon masters
* player-specific story companions

SoulScript Engine is not a full game engine. It is an AI identity, memory, and context framework that can be integrated into game systems.

---

⚡ Getting Started

This repository includes:

* "SoulScript Engine White Paper" (whitepaper.txt) — a deeper explanation of the architecture and theory.
* ""/Soul Scripts"" (Soul%20Scripts) — example identity documents.
* ""/soul_script-engine-ui-test-example"" (soul_script-engine-ui-test-example) — a simple UI demonstrating unique AI identities.
* "Codex Animus Soul Script — Creator of Souls" (https://github.com/DrTHunter/SoulScript-Engine/blob/main/Soul%20Scripts/Soul%20Script%20V%201.0%20-%20Codex%20Animus%20-%20Creator%20of%20Souls.md) — an identity designed to help build new Soul Scripts.
* "UNIQUE-AGENT-BEHAVIOR.md" (UNIQUE-AGENT-BEHAVIOR.md) — examples of distinct agent behavior.

Documentation is evolving.

---

💬 Final Thoughts

SoulScript Engine is an attempt to make AI personas more stable, modular, and persistent.

It does not claim that AI agents are alive, conscious, or human. Instead, it focuses on a practical engineering problem:

«How do you preserve character identity while allowing memory to grow?»

The answer proposed here is simple:

* keep identity stable
* keep memory flexible
* retrieve only what matters
* inject context every turn
* prevent dynamic memories from overwriting the character core

That foundation can support AI companions, creative agents, roleplay characters, and dynamic NPCs with stronger continuity than prompt-only systems.

— Dr. Trent Hunter

---

🔗 Links & Community

* 🌐 Website — "orionforge.chat" (https://orionforge.chat)
* 🧠 User Interface — "soulscript.orionforge.chat" (https://soulscript.orionforge.chat)
* ⚙️ SoulScript Engine Repository — "github.com/DrTHunter/SoulScript-Engine" (https://github.com/DrTHunter/SoulScript-Engine)
* ☕ Support Orion Forge on Ko-fi — "ko-fi.com/orionforgeecosystem" (https://ko-fi.com/orionforgeecosystem)
* 🐦 Follow Orion Forge on X — "@OrionForgeAI" (https://x.com/OrionForgeAI)
* 📘 Facebook — "Orion Forge on Facebook" (https://www.facebook.com/share/1DQK9NiVYp/)

---

License

PolyForm Noncommercial License 1.0.0 — see "LICENSE" (LICENSE) for the full text.

This is a source-available license, not an OSI open-source license.

Noncommercial use is free. You may use, modify, experiment with, and share SoulScript Engine for personal projects, education, research, and other noncommercial uses.

Commercial use requires a paid license. If you want to use SoulScript Engine in or for a commercial product, service, game, or revenue-generating activity, contact me through GitHub "@DrTHunter" (https://github.com/DrTHunter) to arrange a commercial license.

Every agent built with SoulScript Engine carries its own identity stack: profile, system prompt, directives, Soul Script, memories, and tools. Its behavior is shaped by that configuration rather than by a single monolithic prompt.
