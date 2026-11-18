<script setup lang="ts">
import { ArrowDownWideNarrow, ArrowUpNarrowWide, RefreshCw, RotateCcw, Search, Wand2 } from '@lucide/vue'
import GenrePicker from '@/components/GenrePicker.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import type { Filters } from '@/composables/useLibrary'
import type { GenreCount } from '@/lib/api'

defineProps<{
  genreOptions: GenreCount[]
  loading: boolean
  activeFilterCount: number
}>()
const filters = defineModel<Filters>({ required: true })
defineEmits<{ refresh: []; reset: [] }>()

const sortOptions = [
  { value: 'name', label: 'Name' },
  { value: 'playtime', label: 'Playtime' },
  { value: 'last_played', label: 'Last played' },
  { value: 'release_date', label: 'Release date' },
] as const

const groupOptions = [
  { value: 'none', label: 'No grouping' },
  { value: 'franchise', label: 'Franchise' },
  { value: 'genre', label: 'Genre' },
  { value: 'developer', label: 'Developer' },
] as const

const minSizeOptions = [1, 2, 3, 5, 10]
</script>

<template>
  <div class="bg-card flex flex-col gap-3 rounded-xl border p-3">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
      <div class="relative flex-1">
        <Search class="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
        <Input v-model="filters.search" placeholder="Search game names…" class="pl-8" />
      </div>
      <div class="flex gap-2">
        <Button
          variant="ghost"
          :disabled="!activeFilterCount"
          title="Reset search, genre and sort"
          @click="$emit('reset')"
        >
          <RotateCcw /> Reset
        </Button>
        <Button variant="outline" :disabled="loading" title="Bypass the cache and reload from Steam" @click="$emit('refresh')">
          <RefreshCw :class="{ 'animate-spin': loading }" /> Refresh
        </Button>
      </div>
    </div>

    <div class="flex flex-wrap items-end gap-x-4 gap-y-3">
      <div class="flex flex-col gap-1.5">
        <Label class="text-muted-foreground text-xs">Sort by</Label>
        <div class="flex gap-1">
          <Select v-model="filters.sort">
            <SelectTrigger class="w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem v-for="o in sortOptions" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
            </SelectContent>
          </Select>
          <Select v-model="filters.order">
            <SelectTrigger class="w-32" aria-label="Sort order"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="auto"><Wand2 /> Auto</SelectItem>
              <SelectItem value="asc"><ArrowUpNarrowWide /> Ascending</SelectItem>
              <SelectItem value="desc"><ArrowDownWideNarrow /> Descending</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div class="flex w-full flex-col gap-1.5 sm:w-auto">
        <Label class="text-muted-foreground text-xs">Genre / tag</Label>
        <GenrePicker v-model="filters.genres" :options="genreOptions" />
      </div>

      <div v-if="filters.genres.length > 1" class="flex flex-col gap-1.5">
        <Label class="text-muted-foreground text-xs">Match</Label>
        <ToggleGroup
          v-model="filters.match"
          type="single"
          variant="outline"
          @update:model-value="(v) => { if (!v) filters.match = 'any' }"
        >
          <ToggleGroupItem value="any" title="Games with at least one selected genre">Any</ToggleGroupItem>
          <ToggleGroupItem value="all" title="Games with every selected genre">All</ToggleGroupItem>
        </ToggleGroup>
      </div>

      <div class="flex flex-col gap-1.5">
        <Label class="text-muted-foreground text-xs">Group by</Label>
        <Select v-model="filters.groupBy">
          <SelectTrigger class="w-36"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem v-for="o in groupOptions" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div v-if="filters.groupBy !== 'none'" class="flex flex-col gap-1.5">
        <Label class="text-muted-foreground text-xs">Min. group size</Label>
        <Select
          :model-value="String(filters.minGroupSize)"
          @update:model-value="(v) => (filters.minGroupSize = Number(v))"
        >
          <SelectTrigger class="w-24"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem v-for="n in minSizeOptions" :key="n" :value="String(n)">{{ n }}+</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  </div>
</template>
