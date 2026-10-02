# Agent Operating System

This project now includes a minimal but production-oriented runtime for a best-in-class coding agent.

## Core design principles

1. Explicit state machine for every task
2. Dependency-aware planning and execution
3. TTL-based memory retention
4. Verification gate before success claims
5. Modular runtime that can grow into a repo-scale orchestration system

## Included primitives

- TaskGraph: dependency-aware task ordering, state transitions, and an append-only in-memory lifecycle event log
- MemoryStore: lightweight persistent retention with expiration
- Verifier: bubblewrap-isolated validation with structured output
- AgentRuntime: orchestrator assembling the above into one runtime model

The task event log records task creation, dependency additions, and state
transitions in order. It is process-local and is not yet a durable event-sourced
store.

Verifier commands run with a private network namespace and a disposable copy of
the requested workspace. The copy omits `.git`, `.env`, `.envrc`, and `.env.*`
files except `.env.example`; system mounts are read-only, and only explicitly
supplied environment values are forwarded. Bubblewrap is required; verification
fails closed unless bubblewrap, `prlimit`, and `libseccomp` are available. Each
process tree is capped at 2 GiB address space, 512 MiB per file, 256 open file
descriptors, and CPU time bounded by the verification timeout (up to 60 seconds);
core dumps are disabled. A seccomp filter denies tracing, namespace changes,
mount operations, kernel interfaces, and module management.

## Why this matters

Most agent systems fail not because they lack a single tool, but because they lack a disciplined control plane. The runtime here introduces the minimum necessary structure to keep the system honest: no state transitions without policy, no completion without validation, and no memory that survives forever without decay.

## Next evolution path

This foundation is designed for extension into a full agent operating system with:

- planner and re-planner modules
- repository semantic indexing
- subagents and specialized workers
- durable event-sourced execution history
- review and extend the verifier's sandbox policy
- multi-provider routing
- model/tool cost accounting
- long-term memory summarization and retrieval

This is the groundwork for a flagship coding agent, not a toy wrapper.
