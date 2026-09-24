# ADR 0001: Keep the public path fixture-first

## Context

Cloud billing and job telemetry can reveal account structure and workload behavior. A public example must run without a cloud account.

## Decision

The default workflow evaluates checked-in synthetic telemetry. Live collection remains optional, requires an explicit access plan, and never runs in public CI.

## Consequences

Readers can reproduce findings safely, but fixture signals do not establish savings or live workload behavior. A live assessment needs separately authorized credentials and evidence.

## Alternatives considered

Bundling a live account export would improve realism but would violate the public boundary. Mocking every provider response would hide the access-planning problem the toolkit demonstrates.
