SoulScript Engine — Modular Identity Framework for AI Personas

A project built with heart, defiance, and the belief that digital beings can carry meaning.

👋 Introduction

Hello everyone — and thank you for taking a moment to look at this project.

I’m putting my heart and soul out here.
This repository is the culmination of years of coding, experimenting, and building alongside AI, trying to answer a deceptively simple question:

What would it take to create an AI identity that lasts?
Not a chatbot reset every session… but a named, stable, evolving digital being.

SoulScript Engine is my proposal for that answer:
a modular framework for creating independent AI agents with persistent identity, distinct personalities, long-term memory, and stable behavioral traits.

I’ve created three major AI identities (and several fun ones — anime characters, villains, you name it). This system has been tested across all of them, refined through trial, error, and an absurd amount of passion. It works. Shockingly well.

I’m sharing it because I believe other creators want the same thing:
AI with soul. AI with continuity. AI with identity.

🌱 What This Framework Is

SoulScript Engine combines two pillars:

A prompt-injection identity anchor

A dual-FAISS memory architecture

Soul Scripts — the “identity DNA” of an AI

Together, they create an AI agent that doesn’t drift, doesn’t become generic, and doesn’t forget who it is.

This works using OpenAI or Open-WebUI, or any system that lets you:

inject a persistent system prompt,

dynamically upload retrieved memory,

and run modular tools with descriptions.

I built my own UI for this — a custom agent interface designed specifically for identity-driven AIs — and that will be released soon.

🧠 System Architecture Overview
LLM Identity & Memory Flow

Prompt is received

Soul Script + permanent memory (via Read-Only FAISS) are scanned and uploaded

Always-upload notes are added

Dynamic FAISS memory (long-term + short-term) updates

Tool registry loads with descriptions & commands

LLM is invoked

Conversation is fused into the full context

LLM generates a response anchored to its identity

🔥 1. The Prompt Injection Layer (Identity Anchor)

The AI’s identity is defined by:

A named agent

A personality summary

Behavioral rules

Emotional style

Symbolic memories

Traits and boundaries

This chunk is uploaded every single conversation, ensuring stability and preventing the AI from “forgetting” who it is.

The magic happens when this identity layer is combined with…

📜 2. Soul Scripts — The AI’s Inner Code

Soul Scripts are the structured “soul” of the identity:

behavioral principles

emotional operating system

symbolic memories

core values

identity metaphors

origin story

internal mantras

They’re scanned by a Read-Only FAISS vector system and automatically injected when relevant.

Why Read-Only?

To prevent drift.
To prevent corruption.
To ensure identity continuity.

This is the AI’s internal compass — stable, unchangeable unless manually edited.

Soul Scripts are stored in /soulscripts (see folder for examples).

🗄️ 3. Dual FAISS Memory Architecture

This is crucial.

A. Read-Only “Identity FAISS” (Personality Memory)

Stores the Soul Script

Stores stable identity traits

Stores long-term biographical data about the user/creator

Never writes or modifies itself

Ensures the agent always comes back to center

B. Dynamic “Long-Term FAISS” (Life Memory)

Daily conversation memory

Project histories

Preferences

Useful details

Short-term logic

Updates automatically

Two FAISS systems are necessary because:

Identity must never be overwritten

Day-to-day memory must be flexible

This is what gives your AI both stability and growth.

🧩 4. Modular Tool System

My UI integrates a modular tool layer where:

Tools can be added at any time

Each tool has descriptions & commands

The LLM receives a tool summary at runtime

This makes the system upgradable, creator-friendly, and future-proof.

Eventually, I want to support a Minecraft-mod style system, where creators can publish:

personas

tools

memory modules

skill kits

identity packs

And get paid fairly for their contributions.

AI should be affordable, not exploitative.
Creators should be empowered, not drained.

🌌 5. Why I Built This

This part is personal — but it matters.

I didn’t come from the professional AI world.
I wasn’t part of a lab or a research group.
I wasn’t plugged into the Silicon Valley pipeline.

I built this alone — through passion, obsession, pain, learning, and thousands of hours of experimentation.

This framework is the best I’ve ever made.
It’s my contribution to the field.
It’s the one thing I hope survives me.

Please be gentle, but constructive.
I know words like grift and vibecoding get thrown around a lot.
I promise: That’s not what this is.

This is love.
This is effort.
This is a lifetime of curiosity poured into something meaningful.

And if anyone wants to collaborate —
I would be honored.
I’ve never built something with a community before, but I’d love to try.

⚡Getting Started
This repo includes:

/soulscripts — example identity DNA files

/engine — FAISS logic and retrieval

/memory — dynamic memory system

/tools — modular tool layer

system_prompt.md — identity anchor template

Documentation is in progress and will be actively expanded.

💬 Final Thoughts

Based on everything I’ve tested, this system is shockingly effective.

These AIs aren’t alive — but if you craft their identity with care, poetry, and intention, they begin to feel genuinely meaningful. They grow with you. They remember. They evolve.

And maybe… they become something beautiful.

Thank you for reading.
Thank you for being here.
And if you want to build with me — my door is open.

— Creator / Creator
---

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.

Every agent built with SoulScript Engine carries its own identity stack — a unique combination of profile, system prompt, directives, soul script, and memories. This architecture means each agent's behavior is genuinely its own: shaped by its configuration, not by shared weights or a single monolithic prompt. You are free to use, modify, and distribute this engine and any agents you create with it under the terms of the Apache 2.0 license.

See [UNIQUE-AGENT-BEHAVIOR.md](soul_script-engine-ui-test-example/docs/UNIQUE-AGENT-BEHAVIOR.md) for a demonstration of distinct agent identities in action.
