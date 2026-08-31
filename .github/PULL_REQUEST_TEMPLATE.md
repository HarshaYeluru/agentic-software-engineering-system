## Summary

<!-- What changed, and why. One or two sentences. -->

## Type of change

- [ ] Feature (`feature/`)
- [ ] Fix (`fix/`)
- [ ] Chore / CI / docs (`chore/`)
- [ ] Agent-authored (`agents/`)

## Risk level

<!-- Mirrors this project's own risk_level concept: how much blast radius does this
     change have, and why? A high-risk change (touches orchestrator.py, agents.py,
     the approval gate, or anything that writes to disk) should get more review. -->

- [ ] Low — docs, tests, tooling; no behavior change
- [ ] Medium — new functionality, additive, backward compatible
- [ ] High — changes orchestration/approval logic, touches generated-file writing, or is a breaking change

## Validation

<!-- What did you actually run? Paste the relevant output if useful. -->

- [ ] `python -m unittest discover -s tests -v` passes
- [ ] `ruff check .` passes
- [ ] `bandit -q -r agentic_system url_shortener` passes
- [ ] `pip-audit` passes
- [ ] Manually exercised the change (describe how, if not covered by the above)

## Checklist

- [ ] Docs updated if behavior or setup steps changed
- [ ] No secrets, credentials, or local paths committed
