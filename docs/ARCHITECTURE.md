# Architecture

The public runtime has one trust boundary: the assessment specification. Validation and preflight run before policy evaluation, so a report cannot be generated from a specification that requests broad access.

```mermaid
flowchart TB
    Spec[Versioned assessment specification]
    Validate[Contract validator]
    Preflight[Least-privilege preflight]
    Telemetry[Synthetic telemetry now<br/>Approved provider adapters later]
    Policies[Deterministic policy engine]
    Findings[Structured findings]
    Outputs[Markdown report<br/>JSON findings<br/>PNG evidence cards]

    Spec --> Validate --> Preflight --> Telemetry --> Policies --> Findings --> Outputs
```

The policy engine records evidence and assumptions separately. A cost signal can justify an investigation, but the current implementation does not turn it into a savings claim.

