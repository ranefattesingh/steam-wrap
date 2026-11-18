# Steam Wrap — web UI

Vue 3 + Vite + TypeScript, Tailwind CSS v4 and [shadcn-vue](https://www.shadcn-vue.com) components.

Paste a Steam access token, hit **Find**, and the app loads your **entire** library
(every page of `GET /api/v1/games`, no page-size limit) as a bullet list, with:

- **Search** by name (instant, client-side)
- **Sort** by name, playtime, last played or release date, ascending/descending/auto
- **Filter** by one or more genres/tags, matching *any* or *all*
- **Group** by franchise, genre or developer, with a minimum group size; games in no group are listed last
- **Details** dialog per game (playtime, platforms, tags, similar games in your library)

## Run

```bash
pnpm install
pnpm dev          # http://localhost:5173
```

The API must be running on `:8000` (`make run` in the repo root); Vite proxies
`/api` to it. To call a different backend, set `VITE_API_BASE_URL`
(e.g. `VITE_API_BASE_URL=https://api.example.com pnpm build`). That origin must
be allowed by the API's `app.cors_origins`.

```bash
pnpm build        # vue-tsc type-check + production build into dist/
pnpm preview      # serve dist/
```

## Layout

```
src/
  lib/api.ts                  typed API client (+ fetchAllGames page walker)
  composables/useLibrary.ts   state: token, filters, loading, grouping
  components/
    TokenForm.vue             home page token input
    LibraryToolbar.vue        search / sort / genre / group controls
    GenrePicker.vue           searchable multi-select for genres & tags
    GameList.vue              the bullet list
    GameDetailDialog.vue      per-game details and similar games
    ui/                       generated shadcn-vue components
```

The token is held in memory only (reloading the page forgets it) and is sent
as an `Authorization: Bearer` header, never in a URL.
