// Typed client for the Steam Wrap API (see docs/API.md in the repo root).

export type SortField = 'name' | 'playtime' | 'last_played' | 'release_date'
export type SortOrder = 'asc' | 'desc'
export type MatchMode = 'any' | 'all'
export type GroupBy = 'franchise' | 'genre' | 'developer'
export type GenreScope = 'genres' | 'tags' | 'all'

export interface GameRef {
  id: number
  name: string
  description: string | null
}

export interface LibraryInfo {
  steamid: string
  total_games: number
  metadata_missing: number
  fetched_at: string
}

export interface Page {
  page: number
  page_size: number
  total: number
  pages: number
}

export interface GameListResponse {
  library: LibraryInfo
  page: Page
  filters: Record<string, unknown>
  only_names: false
  items: GameRef[]
}

export interface GenreCount {
  name: string
  game_count: number
  is_primary: boolean
}

export interface GenreListResponse {
  scope: GenreScope
  library: LibraryInfo
  aliases: Record<string, string[]>
  items: GenreCount[]
}

export interface GameGroup {
  name: string
  size: number
  games: GameRef[]
}

export interface GroupsResponse {
  by: GroupBy
  library: LibraryInfo
  groups: GameGroup[]
}

export interface Platforms {
  windows: boolean
  mac: boolean
  linux: boolean
  steam_deck: 'verified' | 'playable' | 'unsupported' | 'unknown'
}

export interface GameDetail {
  appid: number
  name: string
  playtime_minutes: number
  playtime_2weeks_minutes: number
  last_played_at: string | null
  genres: string[]
  tags: string[]
  franchises: string[]
  developers: string[]
  publishers: string[]
  short_description: string | null
  is_free: boolean
  release_date: string | null
  platforms: Platforms
  icon_url: string | null
  header_image_url: string | null
  store_url: string
  metadata_available: boolean
  similar_to: GameRef[]
}

export interface MeResponse {
  steamid: string
  token_expires_at: string | null
  profile: {
    persona_name: string | null
    profile_url: string | null
    avatar_url: string | null
    country_code: string | null
  } | null
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null

  constructor(message: string, status: number, code: string, requestId: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

/** Empty by default: the Vite dev server proxies `/api` to the backend. */
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''

/** The server caps `page_size` at `pagination.max_page_size` (200 by default). */
const PAGE_SIZE = 200

type QueryValue = string | number | boolean | undefined | null | readonly string[]

async function request<T>(
  path: string,
  token: string,
  query: Record<string, QueryValue> = {},
  signal?: AbortSignal,
): Promise<T> {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v))
    else params.append(key, String(value))
  }
  const qs = params.toString()
  // Always send the token in the header, never in the URL (it would leak into logs/history).
  let res: Response
  try {
    res = await fetch(`${BASE_URL}/api/v1${path}${qs ? `?${qs}` : ''}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      signal,
    })
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err
    throw new ApiError('Could not reach the Steam Wrap API. Is the backend running?', 0, 'network_error')
  }
  if (!res.ok) {
    let body: { error?: { code?: string; message?: string; request_id?: string } } = {}
    try {
      body = await res.json()
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(
      body.error?.message ?? `Request failed with HTTP ${res.status}`,
      res.status,
      body.error?.code ?? 'http_error',
      body.error?.request_id ?? res.headers.get('X-Request-ID'),
    )
  }
  return (await res.json()) as T
}

export interface GameQuery {
  genre?: string[]
  match?: MatchMode
  sort?: SortField
  order?: SortOrder
  refresh?: boolean
}

/**
 * Fetch every matching game by walking all pages at the maximum page size.
 * The first page tells us how many pages exist; the rest are fetched in parallel
 * (the library is cached server-side after the first call, so they are cheap).
 */
export async function fetchAllGames(
  token: string,
  query: GameQuery,
  signal?: AbortSignal,
): Promise<{ library: LibraryInfo; items: GameRef[] }> {
  const base = {
    genre: query.genre,
    match: query.genre && query.genre.length > 1 ? query.match : undefined,
    sort: query.sort,
    order: query.order,
    only_names: false,
    page_size: PAGE_SIZE,
  }
  const first = await request<GameListResponse>(
    '/games',
    token,
    { ...base, page: 1, refresh: query.refresh || undefined },
    signal,
  )
  const rest = await Promise.all(
    Array.from({ length: Math.max(0, first.page.pages - 1) }, (_, i) =>
      request<GameListResponse>('/games', token, { ...base, page: i + 2 }, signal),
    ),
  )
  return {
    library: first.library,
    items: [first, ...rest].flatMap((r) => r.items),
  }
}

export const getMe = (token: string, signal?: AbortSignal) =>
  request<MeResponse>('/me', token, {}, signal)

export const getGenres = (token: string, scope: GenreScope = 'all', signal?: AbortSignal) =>
  request<GenreListResponse>('/genres', token, { scope }, signal)

/** `min_size=1` so the client can apply its own threshold after filtering. */
export const getGroups = (token: string, by: GroupBy, signal?: AbortSignal) =>
  request<GroupsResponse>('/groups', token, { by, min_size: 1 }, signal)

export const getGame = (token: string, appid: number, signal?: AbortSignal) =>
  request<GameDetail>(`/games/${appid}`, token, { similar_limit: 10 }, signal)

/**
 * Accept either the bare token or the whole JSON blob from
 * store.steampowered.com/pointssummary/ajaxgetasyncconfig.
 */
export function extractToken(raw: string): string {
  const text = raw.trim().replace(/^Bearer\s+/i, '')
  if (text.startsWith('{')) {
    try {
      const parsed = JSON.parse(text) as { data?: { webapi_token?: string }; webapi_token?: string }
      return (parsed.data?.webapi_token ?? parsed.webapi_token ?? '').trim()
    } catch {
      return text
    }
  }
  return text
}
