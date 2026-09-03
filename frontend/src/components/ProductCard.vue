<script setup>
import { computed } from 'vue'
import { 
  ShoppingCart, 
  Eye, 
  Star, 
  Heart, 
  Sparkles 
} from 'lucide-vue-next'

const props = defineProps({
  product: {
    type: Object,
    required: true
  },
  isHighlighted: {
    type: Boolean,
    default: false
  },
  isWishlisted: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['add-to-cart', 'view-details', 'toggle-wishlist'])

const formatCurrency = (val) => {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val)
}

const formattedOriginalPrice = computed(() => formatCurrency(props.product.originalPrice))
const formattedFinalPrice = computed(() => formatCurrency(props.product.finalPrice))
const formattedSavings = computed(() => formatCurrency(props.product.originalPrice - props.product.finalPrice))
</script>

<template>
  <div 
    class="group relative flex flex-col bg-white rounded-xl border transition-all duration-300 overflow-hidden"
    :class="[
      isHighlighted 
        ? 'border-pink-500 ring-2 ring-pink-500/25 shadow-lg shadow-pink-500/10 transform -translate-y-1' 
        : 'border-zinc-200 hover:border-pink-300 shadow-xs hover:shadow-md'
    ]"
  >
    <!-- AI Highlight & Match Score Badge in Hot Pink -->
    <div 
      v-if="isHighlighted || product.matchScore" 
      class="absolute top-3 left-3 z-10 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gradient-to-r from-pink-600 to-rose-600 text-white text-[11px] font-black shadow-md shadow-pink-500/30"
      :class="{ 'animate-pulse': isHighlighted }"
    >
      <Sparkles class="w-3 h-3" />
      <span>{{ product.matchScore ? `${Math.round(product.matchScore * 100)}% Khớp AI` : 'Gợi ý AI' }}</span>
    </div>

    <!-- Image Area with Light Gray Background -->
    <div class="relative w-full aspect-[4/3] bg-zinc-100/80 overflow-hidden flex items-center justify-center">
      <img 
        :src="product.image" 
        :alt="product.name"
        class="w-full h-full object-cover object-center transition-transform duration-500 group-hover:scale-105"
        loading="lazy"
        @error="(e) => e.target.src = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80'"
      />

      <!-- Discount Badge in Hot Pink -->
      <div 
        v-if="product.discountPercent > 0"
        class="absolute top-3 right-3 z-10 flex items-center justify-center px-2 py-0.5 rounded-full bg-pink-50 border border-pink-200 text-pink-600 text-xs font-black tracking-tight shadow-xs"
      >
        -{{ product.discountPercent }}%
      </div>

      <!-- Quick Action Wishlist -->
      <button 
        @click.stop="emit('toggle-wishlist', product)"
        class="absolute bottom-3 right-3 p-2 rounded-full bg-white/90 backdrop-blur-xs text-zinc-600 hover:text-pink-600 shadow-sm transition-all opacity-0 group-hover:opacity-100 hover:scale-110 cursor-pointer"
        :class="{ 'opacity-100 text-pink-600': isWishlisted }"
        title="Lưu vào danh sách yêu thích"
      >
        <Heart class="w-4 h-4" :class="{ 'fill-pink-600 text-pink-600': isWishlisted }" />
      </button>
    </div>

    <!-- Content Area -->
    <div class="flex flex-col flex-1 p-4">
      <!-- Category & Rating -->
      <div class="flex items-center justify-between gap-2 text-xs text-zinc-500 mb-1.5">
        <span class="font-bold uppercase tracking-wider text-zinc-400 text-[11px]">{{ product.category }}</span>
        <div class="flex items-center gap-1 text-amber-500 font-semibold">
          <Star class="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
          <span>{{ product.rating }}</span>
          <span class="text-zinc-400 font-normal">({{ product.reviewsCount }})</span>
        </div>
      </div>

      <!-- Product Name (Bold, Dark text) -->
      <h3 
        @click="emit('view-details', product)"
        class="font-bold text-zinc-900 text-base leading-snug line-clamp-1 group-hover:text-pink-600 transition-colors cursor-pointer"
        :title="product.name"
      >
        {{ product.name }}
      </h3>

      <!-- Feature Tags -->
      <div class="flex flex-wrap gap-1.5 mt-2 mb-3">
        <span 
          v-for="tag in product.tags.slice(0, 2)" 
          :key="tag"
          class="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-100 text-zinc-700"
        >
          {{ tag }}
        </span>
      </div>

      <!-- Spacer -->
      <div class="mt-auto"></div>

      <!-- Pricing Section in Pink & Black -->
      <div class="pt-2 border-t border-zinc-100 flex items-baseline justify-between mb-3.5">
        <div class="flex flex-col">
          <!-- Final Price (Large, Hot Pink text) -->
          <span class="text-lg font-black text-pink-600 tracking-tight">
            {{ formattedFinalPrice }}
          </span>
          <!-- Original Price (Strikethrough, Small Gray text) -->
          <span class="text-xs text-zinc-400 line-through font-normal">
            {{ formattedOriginalPrice }}
          </span>
        </div>
        <span class="text-[11px] font-bold text-pink-700 bg-pink-50 px-2 py-0.5 rounded border border-pink-200">
          Tiết kiệm {{ formattedSavings }}
        </span>
      </div>

      <!-- Action Buttons -->
      <div class="grid grid-cols-2 gap-2">
        <button 
          @click="emit('view-details', product)"
          class="w-full py-2 px-3 rounded-lg border border-zinc-200 text-xs font-bold text-zinc-700 bg-white hover:bg-zinc-50 hover:border-pink-300 hover:text-pink-600 transition-all flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <Eye class="w-3.5 h-3.5 text-zinc-400 group-hover:text-pink-600" />
          <span>Chi tiết</span>
        </button>

        <button 
          @click="emit('add-to-cart', product)"
          class="w-full py-2 px-3 rounded-lg bg-zinc-950 hover:bg-gradient-to-r hover:from-pink-600 hover:to-rose-600 active:scale-98 text-xs font-bold text-white shadow-sm transition-all flex items-center justify-center gap-1.5 cursor-pointer hover:shadow-md hover:shadow-pink-500/20"
        >
          <ShoppingCart class="w-3.5 h-3.5" />
          <span>Thêm giỏ</span>
        </button>
      </div>
    </div>
  </div>
</template>
