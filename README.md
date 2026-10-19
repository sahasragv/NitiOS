# Setu

**One chat. All your apps.**

Setu (Sanskrit for "bridge") is an AI assistant platform that connects a chat
agent to the apps and tools you already use through the Model Context Protocol
(MCP). It runs on any model, including fully local ones via Ollama.

## Vision

Provide a secure, observable foundation for AI workflows that can evolve with
enterprise needs.

## Tech Stack

Python, FastAPI, PostgreSQL, Redis, RabbitMQ, Qdrant, Celery, Docker,
Kubernetes, OpenTelemetry, Langfuse, OpenAI, Ollama, MCP, and LangGraph.

## High-Level Architecture

The backend starts as a Modular Monolith organized around Clean Architecture,
with strict module boundaries to support future service extraction.

## Development Principles

Production-quality code, Clean Architecture, SOLID, repository abstractions,
dependency injection, typed interfaces, structured errors, logging, and tests.

## Folder Structure

```text
backend/        Backend application, tests, scripts, and dependencies
docs/           Architecture decision records and project documentation
frontend/       Frontend application
infrastructure/ Deployment and operational configuration
```
