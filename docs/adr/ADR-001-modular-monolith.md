# ADR-001: Modular Monolith

## Status

Accepted

## Context

Setu needs a production-oriented foundation that supports clear ownership,
independent domain evolution, and a maintainable deployment model.

## Decision

Setu will begin as a Modular Monolith with strict module boundaries and Clean
Architecture, allowing future extraction into microservices if required.

## Alternatives Considered

- Microservices from the outset
- A layered monolith without explicit module boundaries

## Consequences

The initial system can be deployed and operated as one application while domain
boundaries remain explicit. Modules must avoid direct coupling so that future
service extraction remains feasible.
