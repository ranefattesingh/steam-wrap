<script setup lang="ts">
import { Eye, EyeOff, Loader2, Search } from '@lucide/vue'
import { ref } from 'vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { extractToken } from '@/lib/api'

defineProps<{ loading?: boolean; compact?: boolean }>()
const emit = defineEmits<{ submit: [token: string] }>()

const raw = ref('')
const reveal = ref(false)
const localError = ref<string | null>(null)

function onSubmit() {
  const token = extractToken(raw.value)
  if (!token) {
    localError.value = 'Paste your Steam access token first.'
    return
  }
  if (token.split('.').length !== 3) {
    localError.value = "That doesn't look like a Steam access token (expected a JWT: xxx.yyy.zzz)."
    return
  }
  localError.value = null
  emit('submit', token)
}
</script>

<template>
  <form class="flex w-full flex-col gap-2" @submit.prevent="onSubmit">
    <Label v-if="!compact" for="token" class="text-sm">Steam access token</Label>
    <div class="flex gap-2">
      <div class="relative flex-1">
        <Input
          id="token"
          v-model="raw"
          :type="reveal ? 'text' : 'password'"
          placeholder="eyJhbGciOi… (or paste the whole ajaxgetasyncconfig JSON)"
          autocomplete="off"
          spellcheck="false"
          class="h-10 pr-10 font-mono text-sm"
          :aria-invalid="!!localError"
        />
        <button
          type="button"
          class="text-muted-foreground hover:text-foreground absolute inset-y-0 right-0 flex w-10 items-center justify-center"
          :aria-label="reveal ? 'Hide token' : 'Show token'"
          @click="reveal = !reveal"
        >
          <EyeOff v-if="reveal" class="size-4" />
          <Eye v-else class="size-4" />
        </button>
      </div>
      <Button type="submit" size="lg" class="h-10 px-4" :disabled="loading">
        <Loader2 v-if="loading" class="animate-spin" />
        <Search v-else />
        Find
      </Button>
    </div>
    <p v-if="localError" class="text-destructive text-sm">{{ localError }}</p>
  </form>
</template>
