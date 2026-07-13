# Codex Repo Notes

Last explored: 2026-07-13

## Workspace

- Package manager: npm (`package-lock.json` present).
- Nx projects:
  - `who-eats-whom`: React/Vite application at repo root, source in `src`.
  - `e2e`: Cypress project in `e2e`, depends on `who-eats-whom`.
- Use npm-prefixed Nx commands, per `AGENTS.md`.

## Common Commands

- List projects: `npm exec nx show projects -- --json`
- App config: `npm exec nx show project who-eats-whom -- --json`
- E2E config: `npm exec nx show project e2e -- --json`
- Serve app: `npm exec nx serve who-eats-whom`
- Build app: `npm exec nx build who-eats-whom`
- Unit tests: `npm exec nx test who-eats-whom`
- Lint app: `npm exec nx lint who-eats-whom`
- Cypress e2e: `npm exec nx e2e e2e`

## App Shape

- Entry point: `src/main.tsx`
- Routes: `src/routes.tsx`
- Shell/layout: `src/App/App.tsx` and `src/components/SiteWrapper`
- Home/search UI: `src/pages/Home/Home.tsx` renders `src/components/Web/Web.tsx`
- iNaturalist API client: `src/utils/api.ts`
- Domain types for observations/taxa: `src/components/Web/types.ts`
- Static assets live in `public`; `docs` appears to contain the GitHub Pages build output/assets.
- Vite dev server uses `localhost:4200`; preview uses `localhost:4300`.

## Behavior Notes

- Main functionality is the iNaturalist-backed food web search in `src/components/Web`.
- API base URL is `https://api.inaturalist.org/v1`.
- Important iNaturalist constants in `Web.tsx`:
  - project id `41347`
  - eater/eaten field id `12795`
  - partner field id `12796`
- Visual result modes include grid, graph, network, and map; D3 and Leaflet are dependencies.
- Routing uses `createBrowserRouter` with `basename: '/'`.

## Verification Notes

- Existing unit test coverage is minimal: `src/components/Web/Web.test.tsx` only imports setup currently.
- Existing Cypress smoke test checks the landing page title.
- For UI changes, prefer at least:
  - `npm exec nx test who-eats-whom`
  - `npm exec nx lint who-eats-whom`
  - `npm exec nx build who-eats-whom`
- For routed/user-flow changes, also run `npm exec nx e2e e2e` when practical.

## Repo-Specific Instructions

- Invoke the `nx-workspace` skill before exploring workspace structure.
- Invoke `nx-generate` before scaffolding apps/libs/project structure.
- Frequently pull the latest `production` from `origin` during work to stay current and reduce merge conflicts.
- Prefer Nx tasks over direct tool commands.
- Check Nx docs or `--help` before using unfamiliar Nx flags.
