<script setup lang="ts">
import { ArrowLeft, ExternalLink, Gamepad2, Monitor } from '@lucide/vue'
import { computed, ref, shallowRef, watch } from 'vue'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError, getGame, type GameDetail } from '@/lib/api'

const props = defineProps<{ token: string }>()
/** App id of the game to show; `null` closes the dialog. */
const appid = defineModel<number | null>({ required: true })

const detail = shallowRef<GameDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
/** Games visited via "similar" links, so the user can step back. */
const history = ref<number[]>([])
let controller: AbortController | null = null

const open = computed({
  get: () => appid.value !== null,
  set: (v) => {
    if (!v) {
      appid.value = null
      history.value = []
    }
  },
})

watch(appid, async (id) => {
  controller?.abort()
  if (id === null) return
  controller = new AbortController()
  const current = controller
  loading.value = true
  error.value = null
  detail.value = null
  try {
    detail.value = await getGame(props.token, id, current.signal)
  } catch (err) {
    if ((err as Error).name !== 'AbortError')
      error.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    if (controller === current) loading.value = false
  }
})

function openSimilar(id: number) {
  if (appid.value !== null) history.value.push(appid.value)
  appid.value = id
}

function back() {
  const prev = history.value.pop()
  if (prev !== undefined) appid.value = prev
}

function hours(minutes: number) {
  if (!minutes) return 'Never played'
  if (minutes < 60) return `${minutes} min`
  return `${(minutes / 60).toLocaleString(undefined, { maximumFractionDigits: 1 })} h`
}

function date(value: string | null) {
  return value ? new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—'
}

const platforms = computed(() => {
  const p = detail.value?.platforms
  if (!p) return []
  return [p.windows && 'Windows', p.mac && 'macOS', p.linux && 'Linux'].filter(Boolean) as string[]
})
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
      <template v-if="loading">
        <Skeleton class="aspect-[460/215] w-full rounded-lg" />
        <Skeleton class="h-6 w-2/3" />
        <Skeleton class="h-4 w-full" />
        <Skeleton class="h-4 w-5/6" />
      </template>

      <Alert v-else-if="error" variant="destructive">
        <AlertDescription>{{ error }}</AlertDescription>
      </Alert>

      <template v-else-if="detail">
        <img
          v-if="detail.header_image_url"
          :src="detail.header_image_url"
          :alt="detail.name"
          class="aspect-[460/215] w-full rounded-lg object-cover"
          loading="lazy"
        />
        <DialogHeader>
          <div class="flex items-center gap-2">
            <Button v-if="history.length" variant="ghost" size="icon-sm" title="Back" @click="back">
              <ArrowLeft />
            </Button>
            <DialogTitle class="text-lg">{{ detail.name }}</DialogTitle>
          </div>
          <DialogDescription v-if="detail.short_description">{{ detail.short_description }}</DialogDescription>
        </DialogHeader>

        <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
          <div>
            <dt class="text-muted-foreground text-xs">Playtime</dt>
            <dd>{{ hours(detail.playtime_minutes) }}</dd>
          </div>
          <div>
            <dt class="text-muted-foreground text-xs">Last 2 weeks</dt>
            <dd>{{ detail.playtime_2weeks_minutes ? hours(detail.playtime_2weeks_minutes) : '—' }}</dd>
          </div>
          <div>
            <dt class="text-muted-foreground text-xs">Last played</dt>
            <dd>{{ date(detail.last_played_at) }}</dd>
          </div>
          <div>
            <dt class="text-muted-foreground text-xs">Released</dt>
            <dd>{{ date(detail.release_date) }}</dd>
          </div>
          <div>
            <dt class="text-muted-foreground text-xs">Developer</dt>
            <dd>{{ detail.developers.join(', ') || '—' }}</dd>
          </div>
          <div>
            <dt class="text-muted-foreground text-xs">Publisher</dt>
            <dd>{{ detail.publishers.join(', ') || '—' }}</dd>
          </div>
          <div v-if="detail.franchises.length">
            <dt class="text-muted-foreground text-xs">Franchise</dt>
            <dd>{{ detail.franchises.join(', ') }}</dd>
          </div>
          <div>
            <dt class="text-muted-foreground text-xs">Platforms</dt>
            <dd class="flex items-center gap-1">
              <Monitor class="text-muted-foreground size-3.5" />{{ platforms.join(', ') || '—' }}
            </dd>
          </div>
          <div>
            <dt class="text-muted-foreground text-xs">Steam Deck</dt>
            <dd class="flex items-center gap-1 capitalize">
              <Gamepad2 class="text-muted-foreground size-3.5" />{{ detail.platforms.steam_deck }}
            </dd>
          </div>
        </dl>

        <div v-if="detail.genres.length || detail.tags.length" class="flex flex-wrap gap-1">
          <Badge v-for="g in detail.genres" :key="`g-${g}`">{{ g }}</Badge>
          <Badge
            v-for="t in detail.tags.filter((t) => !detail!.genres.includes(t)).slice(0, 15)"
            :key="`t-${t}`"
            variant="secondary"
          >
            {{ t }}
          </Badge>
        </div>
        <p v-if="!detail.metadata_available" class="text-muted-foreground text-xs">
          Store metadata isn't available for this game (delisted or Steam error).
        </p>

        <template v-if="detail.similar_to.length">
          <Separator />
          <div>
            <h3 class="mb-2 text-sm font-medium">Similar games in your library</h3>
            <ul class="marker:text-muted-foreground list-disc space-y-1 pl-6 text-sm">
              <li v-for="g in detail.similar_to" :key="g.id">
                <button
                  type="button"
                  class="hover:text-primary text-left underline-offset-4 hover:underline"
                  @click="openSimilar(g.id)"
                >
                  {{ g.name }}
                </button>
              </li>
            </ul>
          </div>
        </template>

        <div class="flex justify-end">
          <Button as="a" :href="detail.store_url" target="_blank" rel="noopener noreferrer" variant="outline">
            Open in Steam store <ExternalLink />
          </Button>
        </div>
      </template>
    </DialogContent>
  </Dialog>
</template>
