<script setup lang="ts">
import { useDark, useToggle } from '@vueuse/core'
import { AlertCircle, ChevronRight, Gamepad2, Library, LogOut, Moon, Sun } from '@lucide/vue'
import { computed, ref } from 'vue'
import GameDetailDialog from '@/components/GameDetailDialog.vue'
import GameList from '@/components/GameList.vue'
import LibraryToolbar from '@/components/LibraryToolbar.vue'
import TokenForm from '@/components/TokenForm.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { useLibrary } from '@/composables/useLibrary'

const isDark = useDark()
const toggleDark = useToggle(isDark)

const store = useLibrary()
const { filters } = store

const selectedGame = ref<number | null>(null)
const showDescriptions = ref(true)
/** Groups the user has collapsed (all groups start expanded). */
const collapsed = ref(new Set<string>())

const connected = computed(() => !!store.library.value)
const initialLoading = computed(() => store.loading.value && !connected.value)

function toggleGroup(name: string, open: boolean) {
  const next = new Set(collapsed.value)
  if (open) next.delete(name)
  else next.add(name)
  collapsed.value = next
}

function setAllGroups(open: boolean) {
  collapsed.value = open ? new Set() : new Set(store.groupedGames.value?.map((g) => g.name) ?? [])
}

const summary = computed(() => {
  const lib = store.library.value
  if (!lib) return ''
  const shown = store.visibleGames.value.length
  const parts = [`${shown.toLocaleString()} of ${lib.total_games.toLocaleString()} games`]
  if (store.groupedGames.value) {
    const real = store.groupedGames.value.filter((g) => !g.isRemainder).length
    parts.push(`${real.toLocaleString()} groups`)
  }
  return parts.join(' · ')
})
</script>

<template>
  <div class="bg-background text-foreground min-h-svh">
    <header class="bg-background/80 sticky top-0 z-40 border-b backdrop-blur">
      <div class="mx-auto flex h-14 max-w-5xl items-center gap-3 px-4">
        <Gamepad2 class="size-5" />
        <span class="font-semibold">Steam Wrap</span>
        <div class="ml-auto flex items-center gap-2">
          <template v-if="connected">
            <a
              v-if="store.me.value?.profile"
              :href="store.me.value.profile.profile_url ?? undefined"
              target="_blank"
              rel="noopener noreferrer"
              class="flex items-center gap-2 text-sm"
            >
              <img
                v-if="store.me.value.profile.avatar_url"
                :src="store.me.value.profile.avatar_url"
                alt=""
                class="size-7 rounded-full"
              />
              <span class="hidden sm:inline">{{ store.me.value.profile.persona_name }}</span>
            </a>
            <Button variant="ghost" size="sm" title="Forget token" @click="store.signOut()">
              <LogOut /> <span class="hidden sm:inline">Sign out</span>
            </Button>
          </template>
          <Button variant="ghost" size="icon" :title="isDark ? 'Light mode' : 'Dark mode'" @click="toggleDark()">
            <Sun v-if="isDark" />
            <Moon v-else />
          </Button>
        </div>
      </div>
    </header>

    <main class="mx-auto max-w-5xl px-4 py-8">
      <!-- Home: token entry -->
      <section v-if="!connected" class="mx-auto flex max-w-xl flex-col gap-6 pt-[10vh]">
        <div class="space-y-2 text-center">
          <Library class="mx-auto size-10" />
          <h1 class="text-3xl font-semibold tracking-tight">Explore your Steam library</h1>
          <p class="text-muted-foreground">
            Enter your Steam access token to list every game you own, then sort, filter and group them.
          </p>
        </div>

        <TokenForm :loading="initialLoading" @submit="store.connect" />

        <Alert v-if="store.error.value" variant="destructive">
          <AlertCircle />
          <AlertTitle>Couldn't load your library</AlertTitle>
          <AlertDescription>{{ store.error.value }}</AlertDescription>
        </Alert>

        <div v-if="initialLoading" class="space-y-2">
          <p class="text-muted-foreground text-center text-sm">
            Loading your library… the first load can take a while for large libraries.
          </p>
          <Skeleton v-for="i in 5" :key="i" class="h-5" :style="{ width: `${90 - i * 8}%` }" />
        </div>

        <details class="text-muted-foreground rounded-lg border p-3 text-sm">
          <summary class="text-foreground cursor-pointer font-medium">Where do I get my token?</summary>
          <ol class="mt-2 list-decimal space-y-1 pl-5">
            <li>Log in at <a class="underline" href="https://store.steampowered.com" target="_blank" rel="noopener noreferrer">store.steampowered.com</a>.</li>
            <li>
              Open
              <a class="underline break-all" href="https://store.steampowered.com/pointssummary/ajaxgetasyncconfig" target="_blank" rel="noopener noreferrer">
                store.steampowered.com/pointssummary/ajaxgetasyncconfig
              </a>
              in the same browser.
            </li>
            <li>Copy <code class="bg-muted rounded px-1">data.webapi_token</code> (or paste the whole JSON, we'll pick it out).</li>
          </ol>
          <p class="mt-2">The token stays in this tab's memory only and is sent solely to this app's API.</p>
        </details>
      </section>

      <!-- Library -->
      <section v-else class="flex flex-col gap-4">
        <LibraryToolbar
          v-model="store.filters"
          :genre-options="store.genreOptions.value"
          :loading="store.loading.value"
          :active-filter-count="store.activeFilterCount.value"
          @refresh="store.refresh()"
          @reset="store.resetFilters()"
        />

        <Alert v-if="store.error.value" variant="destructive">
          <AlertCircle />
          <AlertDescription>{{ store.error.value }}</AlertDescription>
        </Alert>

        <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span class="text-muted-foreground">{{ summary }}</span>
          <Badge v-if="store.library.value!.metadata_missing" variant="outline" title="Store metadata couldn't be loaded for these games, so they won't match genre filters">
            {{ store.library.value!.metadata_missing }} without metadata
          </Badge>
          <span v-if="store.loading.value" class="text-muted-foreground animate-pulse">Updating…</span>
          <div class="ml-auto flex items-center gap-4">
            <template v-if="store.groupedGames.value">
              <Button variant="link" size="sm" class="h-auto px-0" @click="setAllGroups(true)">Expand all</Button>
              <Button variant="link" size="sm" class="h-auto px-0" @click="setAllGroups(false)">Collapse all</Button>
            </template>
            <div class="flex items-center gap-2">
              <Switch id="desc" v-model="showDescriptions" />
              <Label for="desc" class="font-normal">Descriptions</Label>
            </div>
          </div>
        </div>

        <div :class="{ 'opacity-60 transition-opacity': store.loading.value }">
          <p v-if="!store.visibleGames.value.length" class="text-muted-foreground py-12 text-center">
            No games match these filters.
          </p>

          <!-- Grouped -->
          <template v-else-if="filters.groupBy !== 'none'">
            <div v-if="!store.groupedGames.value" class="space-y-2">
              <Skeleton v-for="i in 6" :key="i" class="h-8" />
            </div>
            <div v-else class="flex flex-col gap-2">
              <Collapsible
                v-for="group in store.groupedGames.value"
                :key="group.name"
                :open="!collapsed.has(group.name)"
                class="rounded-lg border"
                @update:open="(v: boolean) => toggleGroup(group.name, v)"
              >
                <CollapsibleTrigger
                  class="hover:bg-muted/50 group flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left"
                >
                  <ChevronRight class="text-muted-foreground size-4 transition-transform group-data-[state=open]:rotate-90" />
                  <span class="font-medium" :class="{ 'text-muted-foreground italic': group.isRemainder }">
                    {{ group.isRemainder ? `Not in any ${filters.groupBy} group` : group.name }}
                  </span>
                  <Badge variant="secondary" class="ml-auto tabular-nums">{{ group.games.length }}</Badge>
                </CollapsibleTrigger>
                <CollapsibleContent class="px-3 pb-3">
                  <GameList :games="group.games" :show-descriptions="showDescriptions" @select="selectedGame = $event" />
                </CollapsibleContent>
              </Collapsible>
            </div>
          </template>

          <!-- Flat bullet list -->
          <GameList
            v-else
            :games="store.visibleGames.value"
            :show-descriptions="showDescriptions"
            @select="selectedGame = $event"
          />
        </div>
      </section>
    </main>

    <GameDetailDialog v-model="selectedGame" :token="store.token.value" />
  </div>
</template>
