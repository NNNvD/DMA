# Contributing

This project is designed to be developed by a combination of human developers and coding agents.

## Guidelines

1. **Read the Docs**
   - Start with:
     - `docs/01-project-vision.md`
     - `docs/02-functional-spec.md`
     - `docs/03-requirements.md`
     - `docs/05-roadmap-and-milestones.md`

2. **Follow the Roadmap**
   - Implement features in the roadmap order where possible.
   - After each phase, ensure the quality gates in `docs/06-testing-and-quality.md` are met.

3. **Testing**
   - Add or update tests for every non-trivial change.
   - Ensure all tests pass before proposing changes.

4. **Linting & Style**
   - Run the relevant linter(s) for your stack.
   - Fix style issues or clearly justify deviations.

5. **LLM-Specific Considerations**
   - When adjusting prompts or retrieval:
     - Document the change and why it’s needed.
     - Add regression tests where feasible (fixture prompts → expected behavior).

6. **Pull Requests**
   - Clearly describe:
     - What changed
     - Which phase/feature it affects
     - How it was tested
   - Follow Conventional Commits in titles when possible (e.g., `feat:`, `fix:`, `docs:`).

## Git & PR Workflow (Recommended)
- Create small, focused branches; name like `feature/<scope>` or `fix/<area>`.
- Before opening a PR:
  - Lint/format pass (`ruff`, `black`, `mypy`; or eslint/prettier where applicable)
  - All tests pass locally (`pytest -q` or targeted)
  - API changes include docs and examples; verify pagination and error envelope
- PR description should include:
  - Purpose and scope, linked issues, screenshots/logs for UI/API changes
  - Test strategy and results
  - Any schema/env changes and migration steps
