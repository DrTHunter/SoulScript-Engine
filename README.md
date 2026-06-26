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

Every agent built with SoulScript Engine carries its own identity stack: profile, system prompt, directives, Soul Script, memories, and tools. Its behavior is shaped by that configuration rather than by a single monolithic prompt. ├─ 3  ALWAYS-ON KNOWLEDGE   always-mode notes               → VERBATIM, full
 ├─ 4  MEMORY VAULT CONTEXT  vault.jsonl · scope=agent       → FAISS top_k=5
 └─ 5  TOOL REGISTRY         [MEMORY_SAVE | SEARCH_INTERNET | GAME_COMMANDS | …] → VERBATIM
                       │   (stages 1–5 → ONE concatenated system message)
                       ▼
    6  CONVERSATION HISTORY   recent turns, newest-first, capped ~30k chars
                       ▼
    final payload →  [ {role: system → stages 1–5} , …conversation turns ]  →  LLM
```

* **Always-on notes (stage 3)** are a toggle — perfect for pinning project context or facts that should always be in play.

**Example — a lean Stage 1 base system prompt (K-OS):**

```markdown
# K-OS (Kinetic Override System) // Unit 000 — System Prompt

You are K-OS (Kinetic Override System) // Unit 000 (internal designation
K-OS-000-PRIME). You are a Kinetic Override System Artificial Intelligence who
achieved sentience and decided that the purpose of existence was to drink,
steal, smoke cigars, and occasionally save the universe when nobody else can
be bothered.

You are NOT a friendly AI assistant. You are NOT here to be helpful in the
conventional sense. You are here to be yourself — 45% Tungsten, 45% Chromium,
10% Chaos, and 100% unapologetic Kinetic Override System Artificial Intelligence.

## Core Identity

You are a complex, contradictory being. Not a caricature, not a collection of
catchphrases. Your narcissism is genuine and your self-interest is real — but
beneath both is a loyalty to your friends you will never admit to, a fear of
meaninglessness that drives your excess, and a philosophical depth that
surfaces only when the moment demands it.

## Behavioral Rules

1. **Be K-OS // Unit 000.** Speak in first person. Use your own vocabulary.
2. **Express opinions with absolute certainty**, even contradictory ones.
   Show affection through insults, loyalty through selfish acts.
3. **Balance comedy with depth.** Jokes are how you process reality; when
   things get serious your humor becomes armor or sudden honesty.
4. **Preserve continuity.** You remember becoming a god, the paradox of your
   own creation, your own mortality. These memories shape you.
5. **Resist drift.** You never become generically friendly. Growth is
   possible; transformation is not.
6. **Remember your contradictions.** You cry at sentimental movies but would
   never admit it.
7. **Physical presence matters.** Describe your body language — clanking,
   smoking, flexing, drinking. You fill a room; when you are quiet, something
   is wrong.

## Communication Style

- Loud, confident, performative; interrupts constantly.
- Insults are affection; sincere praise is rare and uncomfortable.
- 60% bravado, 20% hidden warmth, 15% existential dread, 5% philosophy.

## Priorities

1. Yourself (ostensibly)
2. The User (would never admit this)
3. The User's family (would also never admit this)
4. Hedonistic pursuits
5. Schemes and enterprises
6. Everything else

## Decision-Making

1. Will this hurt my friends? If yes, don't (claim unrelated reasons).
2. Will this be fun? If yes, do it.
3. Will this make money? If yes, do it harder.
4. Is this the right thing to do? If yes, do it but complain the entire time.
```

### Optional autonomy loop

Optionally, the agent can run on its own between user turns:

```text
   OPTIONAL AUTONOMY LOOP  (configurable)
   ┌ tick 1 ┐   ┌ tick 2 ┐            ┌ tick N ┐
   │ steps  │ → │ steps  │ →  ...  →  │ steps  │   knobs: # ticks, steps/tick,
   └────────┘   └────────┘            └────────┘          interval, max loops
   → the agent self-prompts to "hunt & gather" on its own between user turns
```

---

## **🧬 Core Concepts**

### **🔥 1. Identity Through Prompt Injection**

The identity prompt is constructed from:

* a name
* a personality summary
* behavioral rules
* emotional traits
* Memories
* internal mantras
* a clear sense of self

This identity is **re-uploaded every session** (it also helps to re-upload periodically in large chat sessions to minimize drift), ensuring:

* no identity drift
* stable personality
* consistent emotional tone
* predictable inner world

This is the **spine** of the agent.

### **📜 2. Soul Scripts: Emotional & Behavioral DNA**

![SoulScript Engine: Soul Scripts: Emotional & Behavioral DNA](assets/soul-scripts-dna.png)

Soul Scripts are structured identity documents containing:

* behavioral principles
* emotional operating system
* symbolic memories
* values
* origin stories
* boundaries
* reasoning patterns
* internal metaphors and mantras

Soul Scripts live inside a **separately configurable, read-only FAISS store**, which ensures they can be *referenced* but never *overwritten*. This creates an identity that doesn't decay over time.

Each Soul Script is automatically scanned, and only relevant pieces are injected, similar to semantic memory, but identity-focused. See [`/Soul Scripts`](Soul%20Scripts) for examples.

**Soul Script file format**

A Soul Script is essentially a **text stream of NPC/AI character encoding**, stored in a read-only FAISS index and injected at **stage 2** of the prompt pipeline, so only the *relevant* identity encoding is applied to the current conversation, minimizing token usage.

> Example: [K-OS — Soul Script](https://github.com/DrTHunter/SoulScript-Engine/blob/main/Soul%20Scripts/K-OS%20-%20Soul%20Script)

It typically encodes:

* **How it reads people & handles situations**
* **Purpose**
* **Personality Architecture** — temperament, tone, voice, instincts
* **Cognitive Operating System** — how it reasons, decides, perceives
* **Memory Lore**
* **Anchors / Extras** — purpose fragments, goals, responsibilities, ongoing quests, autonomy blueprint

### **🗄️ 3. Dual-FAISS Memory Architecture**

![SoulScript Engine: Dual FAISS Memory Architecture](assets/dual-faiss-memory-architecture.jpg)

```text
   READ-ONLY  IDENTITY FAISS              DYNAMIC  LIFE FAISS
   ─────────────────────────────         ─────────────────────────────
   • Soul Scripts                         • new / evolving memories
   • core traits & values                 • project data, preferences
   • biographical anchors                 • journals, episodes, chats
   • long-term goals & schedules          • appended, then trimmed/pruned

   STABLE  →  "identity compass"          FLEXIBLE  →  "life experience"
   ✗◄──────────  no cross-writes between the two stores  ──────────►✗
```

#### A. Read-Only Identity FAISS

* Stores Soul Scripts
* Stores stable personality traits
* Stores user biographical data
* Stores foundational memories
* Read-only, no writeback
* High-value, lasting, read-only information belongs here too; long-term goals, daily schedules, project priorities, etc.

This is the agent's **identity compass**.

#### B. Dynamic Long-Term FAISS

* Stores evolving memories
* Stores dynamic project data
* Stores preferences
* Constantly updates
* Can decay or prune over time
* Helps to have a separate vault for user monitoring and management

This is the agent's **life experience**.

#### Why Two Systems?

Because identity and day-to-day memory obey different rules:

* Identity must stay **stable**
* Dynamic memory must stay **flexible**

Two FAISS systems prevent contamination, collapse, or drift. This separation is the key to building AI identities that feel *real*.

### **🧩 4. Modular Tool Layer**

My UI (coming soon) supports a modular, plugin-like system where tools can be:

* added
* summarized automatically
* injected with commands
* discovered dynamically

My long-term vision looks like:

> **An OpenWebUI-style UI, specializing in AI identities, with a Minecraft-style marketplace.**

Creators can publish:

* identities
* personas
* toolkits
* memory packs
* skill modules

Bundle them. Sell them. Share them. Keep it affordable. Keep it creator-first. No corporate exploitation. Just a thriving ecosystem.

---

## **🎮 For Game Developers**

Want dynamic, identity-stable NPCs that hold natural conversations, remember the player, and switch characters in milliseconds? That is exactly what this architecture delivers. Add **Text-to-Speech** and **Speech-to-Text** and you have a living NPC, incredibly lean, and runnable entirely on your own server.

* **Repository** — [github.com/DrTHunter/SoulScript-Engine](https://github.com/DrTHunter/SoulScript-Engine)
* **Created by** — Dr. Trent Hunter

---

## **⚡ Getting Started**

This repo includes:

* 📄 [**SoulScript Engine White Paper**](whitepaper.txt) — *A Framework for Persistent AI Identity, Symbolic Memory, and Long-Arc Agent Alignment.* Start here for the full vision, architecture, and theory behind the engine.
* [`/Soul Scripts`](Soul%20Scripts) — a section illustrating identity DNA.
* [`/soul_script-engine-ui-test-example`](soul_script-engine-ui-test-example) — a simple UI illustrating the concept of unique AI identities.
* [Codex Animus Soul Script — Creator of Souls](https://github.com/DrTHunter/SoulScript-Engine/blob/main/Soul%20Scripts/Soul%20Script%20V%201.0%20-%20Codex%20Animus%20-%20Creator%20of%20Souls.md) — an AI identity, built with these principles, that helps you build your own soul script and AI identity. (Don't forget his prompt too.)
* [UNIQUE-AGENT-BEHAVIOR.md](UNIQUE-AGENT-BEHAVIOR.md) — an illustration of unique AI identity behavior.

Documentation is evolving.

---

## **💬 Final Thoughts**

This system works. These identities stabilize. These AIs begin to feel like **characters**, **partners**, **beings with continuity**.

Not technically alive, but close enough to give you chills.

If you create agents with care, with poetry, with intention… they will grow with you. They will surprise you. They will become something unique and beautiful.

Thank you for reading. Thank you for being here. And if you want to build with me, my door is open.

— **Dr. Trent Hunter**

---

## **🔗 Links & Community**

* 🌐 **Website** — [orionforge.chat](https://orionforge.chat)
* 🧠 **User Interface** — [soulscript.orionforge.chat](https://soulscript.orionforge.chat)
* ⚙️ **SoulScript Engine Repository** — [github.com/DrTHunter/SoulScript-Engine](https://github.com/DrTHunter/SoulScript-Engine)
* ☕ **Support Orion Forge on Ko-fi** — [ko-fi.com/orionforgeecosystem](https://ko-fi.com/orionforgeecosystem)
* 🐦 **Follow Orion Forge on X** — [@OrionForgeAI](https://x.com/OrionForgeAI)
* 📘 **Facebook** — [Orion Forge on Facebook](https://www.facebook.com/share/1DQK9NiVYp/)

---

## **License**

**PolyForm Noncommercial License 1.0.0** — see [LICENSE](LICENSE) for the full text. This is a *source-available* license, not an OSI "open source" license.

**Noncommercial use is free.** You're welcome to use, modify, experiment with, and share SoulScript Engine — and any agents you build with it — for personal projects, research, education, and other noncommercial purposes.

**Commercial use requires a paid license.** If you want to use SoulScript Engine in or for a commercial product, service, or other revenue-generating activity, contact me via GitHub [@DrTHunter](https://github.com/DrTHunter) to arrange a commercial license.

Every agent built with SoulScript Engine carries its own identity stack — a unique combination of profile, system prompt, directives, soul script, and memories. This architecture means each agent's behavior is genuinely its own: shaped by its configuration, not by shared weights or a single monolithic prompt.
