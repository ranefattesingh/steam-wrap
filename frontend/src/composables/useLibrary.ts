import { computed, reactive, ref, shallowRef, watch } from 'vue'
import {
  ApiError,
  fetchAllGames,
  getGenres,
  getGroups,
  getMe,
  type GameGroup,
  type GameRef,
  type GenreCount,
  type GroupBy,
  type LibraryInfo,
  type MatchMode,
  type MeResponse,
  type SortField,
  type SortOrder,
} from '@/lib/api'

export interface Filters {
  search: string
  sort: SortField
  /** `auto` lets the API pick (asc for name, desc otherwise). */
  order: SortOrder | 'auto'
  genres: string[]
  match: MatchMode
  groupBy: GroupBy | 'none'
  minGroupSize: number
}

export interface DisplayGroup {
  name: string
  games: GameRef[]
  /** True for the catch-all bucket of games that fell in no group. */
  isRemainder?: boolean
}

const defaultFilters = (): Filters => ({
  search: '',
  sort: 'name',
  order: 'auto',
  genres: [],
  match: 'any',
  groupBy: 'none',
  minGroupSize: 2,
})

function toMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const hint =
      err.status === 401 ? ' Get a fresh token from Steam and try again.' : ''
    return `${err.message}${hint}`
  }
  return err instanceof Error ? err.message : String(err)
}

const isAbort = (err: unknown) => err instanceof Error && err.name === 'AbortError'

export function useLibrary() {
  // Kept in memory only: the token is a credential, so it is never persisted.
  const token = ref('')
  const me = shallowRef<MeResponse | null>(null)
  const library = shallowRef<LibraryInfo | null>(null)
  const games = shallowRef<GameRef[]>([])
  const genreOptions = shallowRef<GenreCount[]>([])
  const groupsCache = shallowRef<Partial<Record<GroupBy, GameGroup[]>>>({})

  const loading = ref(false)
  const groupsLoading = ref(false)
  const error = ref<string | null>(null)
  const filters = reactive<Filters>(defaultFilters())

  let gamesController: AbortController | null = null

  async function loadGames(refresh = false) {
    if (!token.value) return
    gamesController?.abort()
    const controller = new AbortController()
    gamesController = controller
    loading.value = true
    error.value = null
    try {
      const result = await fetchAllGames(
        token.value,
        {
          genre: filters.genres,
          match: filters.match,
          sort: filters.sort,
          order: filters.order === 'auto' ? undefined : filters.order,
          refresh,
        },
        controller.signal,
      )
      library.value = result.library
      games.value = result.items
    } catch (err) {
      if (!isAbort(err)) error.value = toMessage(err)
    } finally {
      if (gamesController === controller) loading.value = false
    }
  }

  async function loadGroups(by: GroupBy) {
    if (!token.value || groupsCache.value[by]) return
    groupsLoading.value = true
    try {
      const res = await getGroups(token.value, by)
      groupsCache.value = { ...groupsCache.value, [by]: res.groups }
    } catch (err) {
      error.value = toMessage(err)
    } finally {
      groupsLoading.value = false
    }
  }

  /** Entry point from the token form: load everything for a new token. */
  async function connect(newToken: string) {
    token.value = newToken
    me.value = null
    library.value = null
    games.value = []
    genreOptions.value = []
    groupsCache.value = {}
    Object.assign(filters, defaultFilters())

    // Library first: it warms the server cache that /me, /genres and /groups reuse.
    await loadGames()
    if (error.value) return
    const [meRes, genresRes] = await Promise.allSettled([
      getMe(newToken),
      getGenres(newToken, 'all'),
    ])
    if (meRes.status === 'fulfilled') me.value = meRes.value
    if (genresRes.status === 'fulfilled') genreOptions.value = genresRes.value.items
  }

  async function refresh() {
    groupsCache.value = {}
    await loadGames(true)
    if (filters.groupBy !== 'none') await loadGroups(filters.groupBy)
    if (token.value) {
      getGenres(token.value, 'all')
        .then((r) => (genreOptions.value = r.items))
        .catch(() => {})
    }
  }

  function signOut() {
    gamesController?.abort()
    token.value = ''
    me.value = null
    library.value = null
    games.value = []
    error.value = null
  }

  function resetFilters() {
    Object.assign(filters, { ...defaultFilters(), groupBy: filters.groupBy })
  }

  // Filters the API applies: refetch every page when they change.
  watch(
    () => [filters.sort, filters.order, filters.match, [...filters.genres].join('\u0000')],
    () => {
      if (library.value) void loadGames()
    },
  )

  watch(
    () => filters.groupBy,
    (by) => {
      if (by !== 'none') void loadGroups(by)
    },
  )

  // Name search is applied client-side so typing doesn't refetch the whole library.
  const visibleGames = computed(() => {
    const q = filters.search.trim().toLowerCase()
    if (!q) return games.value
    return games.value.filter((g) => g.name.toLowerCase().includes(q))
  })

  /**
   * Intersect the server's groups with the current filtered + sorted list, so
   * filters and sorting still apply inside groups. Games in no remaining group
   * are collected into a final "Other" bucket so nothing disappears.
   */
  const groupedGames = computed<DisplayGroup[] | null>(() => {
    if (filters.groupBy === 'none') return null
    const groups = groupsCache.value[filters.groupBy]
    if (!groups) return null

    const rank = new Map(visibleGames.value.map((g, i) => [g.id, i]))
    const placed = new Set<number>()
    const result: DisplayGroup[] = []
    for (const group of groups) {
      const members = group.games
        .filter((g) => rank.has(g.id))
        .sort((a, b) => rank.get(a.id)! - rank.get(b.id)!)
      if (members.length < filters.minGroupSize) continue
      members.forEach((g) => placed.add(g.id))
      result.push({ name: group.name, games: members })
    }
    result.sort((a, b) => b.games.length - a.games.length || a.name.localeCompare(b.name))

    const remainder = visibleGames.value.filter((g) => !placed.has(g.id))
    if (remainder.length) result.push({ name: '__remainder__', games: remainder, isRemainder: true })
    return result
  })

  const activeFilterCount = computed(
    () =>
      (filters.search.trim() ? 1 : 0) +
      filters.genres.length +
      (filters.sort !== 'name' || filters.order !== 'auto' ? 1 : 0),
  )

  return {
    token,
    me,
    library,
    games,
    genreOptions,
    filters,
    loading,
    groupsLoading,
    error,
    visibleGames,
    groupedGames,
    activeFilterCount,
    connect,
    refresh,
    signOut,
    resetFilters,
  }
}

export type LibraryStore = ReturnType<typeof useLibrary>
