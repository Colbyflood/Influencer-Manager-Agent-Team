# Coding Conventions

**Analysis Date:** 2026-02-18

## Project Status

This codebase is in **early development**. No application source code, linting configuration, or coding standards have been established yet. This document will be populated as the technology stack is selected and development begins.

## Naming Patterns

**Current State:**
- No naming conventions established

**Guidance for Initial Development:**
When selecting a language and framework, establish clear naming patterns for:
- **Files:** Recommend kebab-case for file names (e.g., `user-service.ts`, `user-profile.component.tsx`)
- **Functions:** Use camelCase for function and method names (e.g., `getUserProfile()`, `calculateEngagementRate()`)
- **Variables:** Use camelCase for variable names. Use CONSTANT_CASE for constants (e.g., `const MAX_RETRIES = 3`)
- **Types:** Use PascalCase for TypeScript types/interfaces (e.g., `UserProfile`, `CampaignMetrics`)
- **Classes:** Use PascalCase (e.g., `UserService`, `InfluencerOutreach`)

## Code Style

**Formatting:**
- Not yet established
- Recommend selecting a code formatter (Prettier for JavaScript/TypeScript, black for Python, etc.) and enforcing via CI/CD

**Linting:**
- Not yet established
- Recommend selecting a linter (ESLint for JavaScript/TypeScript, pylint for Python, etc.)
- Suggest enforcing consistent style in pre-commit hooks and CI/CD

## Import Organization

**Current State:**
- No standards established

**Recommended Pattern (when implemented):**
For JavaScript/TypeScript projects, organize imports in this order:
1. Node.js standard library (`fs`, `path`, etc.)
2. Third-party packages (`express`, `axios`, etc.)
3. Application code (`@/services`, `@/utils`, etc.)
4. Relative imports (`../`, `./`)
5. Side effects (imports for side effects only)

**Path Aliases:**
- Not yet configured
- Recommend using path aliases (e.g., `@/services`, `@/utils`) to avoid deeply nested relative imports

## Error Handling

**Current State:**
- No patterns established

**Guidance:**
When implementing error handling:
- Create custom error classes for different failure scenarios (e.g., `ValidationError`, `NotFoundError`, `ExternalServiceError`)
- Use try-catch for async operations
- Avoid silent failures - always log or escalate errors appropriately
- Return meaningful error messages that aid debugging

## Logging

**Current State:**
- No logging framework selected

**Recommended Approach:**
- For Node.js/TypeScript: Consider Winston, Pino, or Bunyan
- For Python: Use Python's built-in logging module or structlog
- Establish log levels: DEBUG, INFO, WARN, ERROR, FATAL
- Include context (request ID, user ID, operation name) in log entries
- Avoid logging sensitive data (passwords, tokens, API keys)

## Comments

**Current State:**
- No comment standards established

**Guidance:**
- Comment the "why" not the "what" - code should be self-documenting for the "what"
- Use comments for non-obvious business logic
- Keep comments up-to-date with code changes
- Use TODO/FIXME comments sparingly and always with context

**JSDoc/TSDoc:**
- Not yet in use
- Recommend adding JSDoc/TSDoc comments for all public functions, classes, and interfaces
- Include parameter types, return types, and examples where helpful

## Function Design

**Current State:**
- No guidelines established

**Recommended Patterns:**
- **Size:** Keep functions focused on a single responsibility. Aim for <50 lines, break down larger functions
- **Parameters:** Limit to 3-4 parameters. Use objects/interfaces for multiple related parameters
- **Return Values:** Clear return types. Use union types (TypeScript) to indicate possible failure states
- **Naming:** Function names should clearly describe what they do (e.g., `getUserByIdOrThrow()` vs `getUser()`)

## Module Design

**Current State:**
- No module structure established

**Guidance When Implementing:**
- **Exports:** Be explicit about public API. Export only what needs to be used externally
- **Barrel Files:** Use `index.ts` files to aggregate exports from a directory for cleaner imports
- **Single Responsibility:** Each module should have one primary reason to change
- **Dependency Injection:** Consider using DI for services to improve testability

## State Management

**Current State:**
- Not yet applicable - no application code exists

**Guidance for When Implementing:**
For the influencer marketing system, consider:
- **Backend State:** Use databases for persistent state (define schema carefully)
- **API State:** Consider pagination, caching strategies for influencer data and metrics
- **Frontend State (if applicable):** Establish pattern early (Redux, Context API, local state)
- **Session State:** Define session handling for authentication/authorization

## Documentation

**Current State:**
- Only CLAUDE.md project overview exists

**Establish When Development Begins:**
- Keep README.md updated with setup instructions
- Document API endpoints with examples
- Add inline comments for complex business logic
- Maintain database schema documentation
- Keep architecture decisions in an ADR (Architecture Decision Record) format

---

*Convention analysis: 2026-02-18*
