# Changelog

## v0.1.0

### Added

- Initial public release of Agent Playpen
- Support for local and cloud LLM backends
- ReAct planner loop and planner abstractions
- Tool registry and callable tool execution model
- Memory, tracing, and observability helpers
- Browser-based dashboard for configuration and task execution
- Full README documentation and project onboarding guidance

### Changed

- Standardized the default local backend to LM Studio
- Cleaned up backend registration and optional dependency loading
- Improved project structure and documentation for easier exploration

### Fixed

- Repaired runtime bugs in backend initialization, tool invocation, and dashboard flow
- Aligned tool implementations with the shared BaseTool contract
- Restored path and config hygiene for local project usage

## Unreleased

- Live dashboard activity stream, elapsed timer, Stop Run, retained failed traces,
  redacted actionable errors, and explicit incomplete outcomes.
- Search source URLs, recoverable ReAct action formats, and OpenRouter response
  metadata/empty-output diagnostics. Added stream lifecycle and DOM smoke tests.

- Encrypted native OS credential manager for all cloud backends and search keys,
  hidden CLI entry, legacy migration, presence-only status, and export filtering.
- OpenRouter dashboard/CLI setup, model selection and discovery, trusted endpoint
  routing, and provider presets.
- Local session/origin/host protections, no-store/CSP headers, sanitized errors,
  credential-path restrictions, and dashboard arbitrary-Python removal.
- Regression suite and repaired package/CLI startup, planner execution, memory,
  dashboard validation, provider construction, and evaluator parsing.
- Updated setup, dashboard, extension, testing, and credential-security guides.

- Repository polish, asset cleanup, and documentation improvements
- GitHub metadata and release preparation work
- Optional refinements for production hardening and packaging
