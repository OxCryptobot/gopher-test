# Agent Operating System

This project now includes a minimal but production-oriented runtime for a best-in-class coding agent.

## Core design principles

1. Explicit state machine for every task
2. Dependency-aware planning and execution
3. TTL-based memory retention
4. Verification gate before success claims
5. Modular runtime that can grow into a repo-scale orchestration system

## Included primitives

- TaskGraph: dependency-aware task ordering, state transitions, and an append-only, event-sourced lifecycle log
- MemoryStore: lightweight persistent retention with expiration
- Verifier: bubblewrap-isolated validation with structured output
- AgentRuntime: orchestrator assembling the above into one runtime model

The task event log records task creation, dependency additions, and state
transitions in order. All graph state is derived by folding these events
through a single `_apply` function, used both for live mutations and for
replay, so the two paths can never drift apart. Event storage is pluggable
via the `EventStore` protocol: `InMemoryEventStore` (the default) keeps the
log in process memory, while `JsonlEventStore` persists each event as a
fsynced JSON line on disk. Pointing a new `TaskGraph` (or `AgentRuntime`) at
an existing `JsonlEventStore` file replays the full history and reconstructs
identical task state, dependencies, metadata, and status after a process
restart or crash. The JSONL loader tolerates a truncated trailing line (an
interrupted write), discarding only the incomplete final event rather than
losing prior history. Event persistence happens before in-process state is
mutated, so a storage failure (e.g. disk full) fails the operation atomically
instead of leaving live state ahead of the durable log. An OS-level advisory
lock guards each read and write against torn access from another process (or
another `JsonlEventStore` instance) touching the same file, and a loaded log
is validated as a strict, gap-free `1..N` sequence, raising immediately if
corruption or an uncoordinated second writer is detected rather than silently
reconstructing incorrect state.

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
- review and extend the verifier's sandbox policy
- multi-provider routing
- model/tool cost accounting
- long-term memory summarization and retrieval

This is the groundwork for a flagship coding agent, not a toy wrapper.
