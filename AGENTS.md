<!-- nx configuration start-->
<!-- Leave the start & end comments to automatically receive updates. -->

# General Guidelines for working with Nx

- For navigating/exploring the workspace, invoke the `nx-workspace` skill first - it has patterns for querying projects, targets, and dependencies
- When running tasks (for example build, lint, test, e2e, etc.), always prefer running the task through `nx` (i.e. `nx run`, `nx run-many`, `nx affected`) instead of using the underlying tooling directly
- Prefix nx commands with the workspace's package manager (e.g., `pnpm nx build`, `npm exec nx test`) - avoids using globally installed CLI
- You have access to the Nx MCP server and its tools, use them to help the user
- For Nx plugin best practices, check `node_modules/@nx/<plugin>/PLUGIN.md`. Not all plugins have this file - proceed without it if unavailable.
- NEVER guess CLI flags - always check nx_docs or `--help` first when unsure

## Scaffolding & Generators

- For scaffolding tasks (creating apps, libs, project structure, setup), ALWAYS invoke the `nx-generate` skill FIRST before exploring or calling MCP tools

## When to use nx_docs

- USE for: advanced config options, unfamiliar flags, migration guides, plugin configuration, edge cases
- DON'T USE for: basic generator syntax (`nx g @nx/react:app`), standard commands, things you already know
- The `nx-generate` skill handles generator discovery internally - don't call nx_docs just to look up generator syntax

<!-- nx configuration end-->

# Codex Workflow

- Once the scope of a requested code or repo change is clear, create a new branch before editing.
- Use short, descriptive branch names. Prefer `ai-<task-name>` when no naming convention is specified.
- Do not commit directly to `production`; use `production` as the PR base branch.
- Commit completed work automatically, including repo notes such as `.codex/repo-notes.md`.
- Open a ready-for-review PR when the task is complete. Do not open draft PRs unless checks are blocked by unrelated failures or external constraints.
- Try to make relevant checks pass before opening a PR. If failures are unrelated or cannot be resolved in scope, document them in the PR.
- For app changes, default to `npm exec nx -- run-many -t lint test build -p who-eats-whom --nxBail --outputStyle=static`.
- For UI, routing, or user-flow changes, also run `npm exec nx -- e2e e2e --outputStyle=static`.
- Include screenshots in PRs for frontend-visible changes.
- Never auto-merge PRs.
- Preserve unrelated user changes in the worktree and avoid destructive git commands unless explicitly requested.
