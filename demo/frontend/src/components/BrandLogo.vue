<script setup>
defineProps({
  size: {
    type: String,
    default: 'w-8 h-8'
  },
  showBadge: {
    type: Boolean,
    default: true
  }
})
</script>

<template>
  <div 
    class="relative flex items-center justify-center shrink-0 transition-transform hover:scale-105"
    :class="[
      showBadge ? 'p-1 bg-white rounded-xl shadow-sm border border-pink-200/80 ring-1 ring-black/5' : '',
      size
    ]"
  >
    <!-- Custom Pink & Black Tech Shopping Bag Logo SVG matching user's exact logo -->
    <svg viewBox="0 0 100 100" class="w-full h-full drop-shadow-xs" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <!-- Hot Pink Gradient -->
        <linearGradient id="pinkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#ff1493" />
          <stop offset="40%" stop-color="#ff2a8d" />
          <stop offset="100%" stop-color="#e11d48" />
        </linearGradient>
        
        <!-- Black Carbon Gradient -->
        <linearGradient id="darkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#2d2d30" />
          <stop offset="100%" stop-color="#0c0c0e" />
        </linearGradient>

        <!-- Subtle Glow Filter -->
        <filter id="pinkGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#ff2a8d" flood-opacity="0.3" />
        </filter>
      </defs>

      <!-- Bag Handle (Black) -->
      <path 
        d="M37 28 C37 15, 63 15, 63 28" 
        stroke="#0c0c0e" 
        stroke-width="7.5" 
        stroke-linecap="round" 
      />

      <!-- Handle Rivets -->
      <circle cx="37" cy="28" r="4.5" fill="#0c0c0e" />
      <circle cx="63" cy="28" r="4.5" fill="#0c0c0e" />

      <!-- Left Pink Body -->
      <path 
        d="M27 26 L65 26 C68 26, 71 28, 73 31 L84 48 C86 51, 86 55, 84 58 L58 84 C54 88, 48 88, 44 84 L24 64 C20 60, 20 54, 20 48 L20 33 C20 29, 23 26, 27 26 Z" 
        fill="url(#pinkGrad)" 
      />

      <!-- Right Dark Tech Segment -->
      <path 
        d="M52 38 L78 44 C82 45, 84 49, 84 53 L84 60 C84 64, 82 68, 78 70 L58 84 C54 88, 48 88, 44 84 L38 78 L52 38 Z" 
        fill="url(#darkGrad)" 
      />

      <!-- White Inner Cutout / Negative Space -->
      <rect x="42" y="42" width="22" height="22" rx="4" transform="rotate(45 53 53)" fill="#ffffff" />

      <!-- Left Tech Speed Stream Dots / Lines -->
      <line x1="8" y1="46" x2="22" y2="46" stroke="#ff2a8d" stroke-width="3.5" stroke-linecap="round" />
      <line x1="12" y1="54" x2="22" y2="54" stroke="#ff2a8d" stroke-width="3.5" stroke-linecap="round" />
      <line x1="6" y1="62" x2="22" y2="62" stroke="#ff2a8d" stroke-width="3.5" stroke-linecap="round" />
      <circle cx="7" cy="46" r="2.5" fill="#ff2a8d" />
      <circle cx="11" cy="54" r="2.5" fill="#ff2a8d" />
      <circle cx="5" cy="62" r="2.5" fill="#ff2a8d" />

      <!-- Right Circuit Lines on Dark Segment -->
      <path d="M68 52 L78 52 L83 56" stroke="#ff2a8d" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
      <circle cx="68" cy="52" r="2" fill="#ff2a8d" />
      
      <path d="M64 60 L74 60 L80 66" stroke="#ff2a8d" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
      <circle cx="64" cy="60" r="2" fill="#ff2a8d" />

      <path d="M70 68 L78 68" stroke="#ff2a8d" stroke-width="2.5" stroke-linecap="round" />
      <circle cx="70" cy="68" r="2" fill="#ff2a8d" />
    </svg>
  </div>
</template>
