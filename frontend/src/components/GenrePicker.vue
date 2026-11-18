<script setup lang="ts">
import { ChevronDown, Tags, X } from '@lucide/vue'
import { computed, ref } from 'vue'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { GenreCount } from '@/lib/api'

const props = defineProps<{ options: GenreCount[] }>()
const selected = defineModel<string[]>({ required: true })

const query = ref('')

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  return q ? props.options.filter((o) => o.name.toLowerCase().includes(q)) : props.options
})

const sections = computed(() => [
  { label: 'Genres', items: filtered.value.filter((o) => o.is_primary) },
  { label: 'Tags', items: filtered.value.filter((o) => !o.is_primary) },
])

const label = computed(() => {
  if (!selected.value.length) return 'All genres & tags'
  if (selected.value.length <= 2) return selected.value.join(', ')
  return `${selected.value.length} selected`
})

function toggle(name: string, on: boolean) {
  selected.value = on ? [...selected.value, name] : selected.value.filter((g) => g !== name)
}
</script>

<template>
  <Popover>
    <PopoverTrigger as-child>
      <Button variant="outline" class="w-full justify-between font-normal sm:w-56">
        <span class="flex min-w-0 items-center gap-1.5">
          <Tags class="text-muted-foreground" />
          <span class="truncate" :class="{ 'text-muted-foreground': !selected.length }">{{ label }}</span>
        </span>
        <ChevronDown class="text-muted-foreground" />
      </Button>
    </PopoverTrigger>
    <PopoverContent align="start" class="w-72 p-0">
      <div class="border-b p-2">
        <Input v-model="query" placeholder="Filter genres & tags…" class="h-8" />
      </div>
      <div class="max-h-80 overflow-y-auto p-1">
        <template v-for="section in sections" :key="section.label">
          <div v-if="section.items.length">
            <p class="text-muted-foreground px-2 pt-2 pb-1 text-xs font-medium">{{ section.label }}</p>
            <label
              v-for="opt in section.items"
              :key="opt.name"
              class="hover:bg-muted flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm"
            >
              <Checkbox
                :model-value="selected.includes(opt.name)"
                @update:model-value="(v) => toggle(opt.name, v === true)"
              />
              <span class="flex-1 truncate">{{ opt.name }}</span>
              <span class="text-muted-foreground text-xs tabular-nums">{{ opt.game_count }}</span>
            </label>
          </div>
        </template>
        <p v-if="!filtered.length" class="text-muted-foreground px-2 py-6 text-center text-sm">
          No genre or tag matches “{{ query }}”.
        </p>
      </div>
      <div v-if="selected.length" class="border-t p-1">
        <Button variant="ghost" size="sm" class="w-full" @click="selected = []">
          <X /> Clear {{ selected.length }} selected
        </Button>
      </div>
    </PopoverContent>
  </Popover>
</template>
