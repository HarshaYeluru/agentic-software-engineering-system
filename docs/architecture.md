# Architecture notes

## Workflow

The workflow is deliberately small, but it follows the same shape as a larger agentic system:

```text
Requirement -> normalization -> task plan -> architecture -> approval gate
                                                             |
                                                             v
                                            implementation artifacts -> validation -> summary
```

Each task declares the tasks it depends on. The orchestrator only starts ready tasks, records a trace entry for every transition, and stops at the approval gate unless a human has approved the proposed assumptions.

## Separation of responsibilities

- `agentic_system.agents` contains functions that produce engineering artifacts. They are deterministic in this demo, which makes reviews repeatable.
- `agentic_system.orchestrator` owns execution order, approval, failure handling, and the trace.
- `url_shortener` is the generated/reference greenfield output. Keeping it separate prevents the workflow engine and the product code from becoming coupled.

## URL-shortener deployment path

The local reference service uses SQLite because it requires no setup. A production version would use PostgreSQL for links, Redis as a cache-aside lookup layer, and a queue plus worker for click analytics. Redirects should remain fast even if the analytics pipeline is delayed, so counts are eventually consistent.

## Guardrails

The workflow records assumptions and pauses for approval before implementation. The validation step checks for required artifacts rather than allowing a partially generated result to look complete. A future repository-writing implementation agent should run in an isolated workspace and require approval before applying changes.
