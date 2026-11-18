<script setup lang="ts">
import type { GameRef } from '@/lib/api'

withDefaults(defineProps<{ games: GameRef[]; showDescriptions?: boolean }>(), {
  showDescriptions: true,
})
defineEmits<{ select: [appid: number] }>()
</script>

<template>
  <ul class="marker:text-muted-foreground list-disc space-y-1.5 pl-6">
    <li v-for="game in games" :key="game.id" class="pl-1">
      <button
        type="button"
        class="hover:text-primary text-left font-medium underline-offset-4 hover:underline focus-visible:underline focus-visible:outline-none"
        @click="$emit('select', game.id)"
      >
        {{ game.name }}
      </button>
      <p
        v-if="showDescriptions && game.description"
        class="text-muted-foreground line-clamp-1 text-sm"
        :title="game.description"
      >
        {{ game.description }}
      </p>
    </li>
  </ul>
</template>
