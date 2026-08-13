# Project Instructions

## Project

This is a Python Telegram bot built with aiogram.

The project follows a layered architecture:

Telegram Update
→ Dispatcher
→ Middleware
→ Router / Filter
→ Handler
→ Service
→ Repository
→ Database

## Architecture Rules

- Handler is responsible only for Telegram interaction.
- Business logic belongs in Services.
- Data access belongs in Repositories.
- Handler must not access the database directly.
- Service must not depend on aiogram/Telegram APIs.
- Repository must not contain business logic.
- Dependencies should be injected rather than created deep inside layers.
- Keep dependency direction:
  Handler → Service → Repository → Database.

## Database

- Use SQLAlchemy for database access.
- Use asynchronous SQLAlchemy APIs.
- Keep Session lifecycle outside Repository.
- Repository receives the required Session/dependency instead of creating its own database connection/session.
- Do not commit after every repository operation.
- Transaction boundaries must be deliberate and handled at the appropriate application/request level.

## Code Quality

- Prefer simple, readable solutions over unnecessary abstractions.
- Do not introduce patterns or layers unless they solve a real problem.
- Follow existing project conventions before introducing new ones.
- Use type hints.
- Avoid `Any` unless there is a clear reason.
- Do not duplicate business logic.
- Do not refactor unrelated code.

## Changes

Before making non-trivial changes:

1. Inspect the existing architecture and relevant files.
2. Explain the proposed approach briefly.
3. Make the smallest change that solves the task.
4. Run relevant tests/checks when available.
5. Report what changed and any remaining concerns.

Do not modify unrelated files.

Do not rewrite working code just for stylistic reasons.

If an architectural decision is unclear, stop and ask before making a significant change.

## Communication

- Be concise.
- Do not repeat information unnecessarily.
- Explain important architectural decisions briefly.
- Do not provide long introductions or generic explanations.
- When something is uncertain, say so instead of guessing.

## Safety

Never delete, overwrite, or significantly restructure project files without explicit justification.

For database migrations, configuration changes, dependency changes, or broad refactors, explain the impact before proceeding.