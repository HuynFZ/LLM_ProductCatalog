<script setup>
import { CheckCircle2, Info, AlertCircle, X, Sparkles } from 'lucide-vue-next'

defineProps({
  toasts: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close'])
</script>

<template>
  <div class="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none max-w-sm w-full">
    <TransitionGroup 
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="transform translate-y-2 opacity-0"
      enter-to-class="transform translate-y-0 opacity-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="transform translate-y-0 opacity-100"
      leave-to-class="transform translate-y-2 opacity-0"
    >
      <div 
        v-for="toast in toasts" 
        :key="toast.id"
        class="pointer-events-auto flex items-center justify-between gap-3 p-3.5 rounded-xl shadow-xl border text-xs font-semibold backdrop-blur-md"
        :class="{
          'bg-zinc-950/95 text-white border-pink-500/40 shadow-pink-500/10': toast.type === 'success' || !toast.type,
          'bg-zinc-900/95 text-white border-pink-400/30': toast.type === 'info',
          'bg-rose-950/95 text-white border-rose-600': toast.type === 'error'
        }"
      >
        <div class="flex items-center gap-2.5">
          <Sparkles v-if="toast.type === 'success' || !toast.type" class="w-4 h-4 text-pink-400 shrink-0 animate-pulse" />
          <Info v-else-if="toast.type === 'info'" class="w-4 h-4 text-pink-400 shrink-0" />
          <AlertCircle v-else class="w-4 h-4 text-rose-400 shrink-0" />
          <span class="leading-snug">{{ toast.message }}</span>
        </div>

        <button 
          @click="emit('close', toast.id)"
          class="text-zinc-400 hover:text-white transition-colors p-0.5 cursor-pointer"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
