# Example scenarios

Three real runs of `agentic_system.cli`, captured verbatim from `run.json`, one for each case the assignment asks for. Each doc shows the same three things: how the requirement was decomposed, how the orchestrator moved through the task graph, and how the result was validated.

| Scenario | Requirement | Result | Approval |
| --- | --- | --- | --- |
| [Greenfield](greenfield.md) | Build a scalable URL shortener service with APIs, persistence, and analytics. | `completed` | Human-approved up front |
| [Brownfield](brownfield.md) | Add expiry support to the existing URL shortener | `completed` | Human-approved up front (brownfield always requires it) |
| [Ambiguous](ambiguous.md) | Make analytics better | `awaiting_approval` | Blocked — no human approval was given |

Reproduce any of them:

```powershell
python -m agentic_system.cli --clean --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." --approve
python -m agentic_system.cli --requirement "Add expiry support to the existing URL shortener" --repository-path url_shortener --approve
python -m agentic_system.cli --requirement "Make analytics better"
```
