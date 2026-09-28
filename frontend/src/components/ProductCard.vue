<script setup>
import { ref, computed, watch } from 'vue'
import { 
  ShoppingCart, 
  Eye, 
  Star, 
  Heart, 
  Sparkles,
  Check
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

// Trạng thái màu sắc đang được chọn trên thẻ sản phẩm
const activeColor = ref(props.product.color || 'Tiêu chuẩn')

watch(() => props.product.color, (newColor) => {
  if (newColor) {
    activeColor.value = newColor
  }
})

// Chi tiết màu sắc tương ứng từ CSDL (ảnh, SKU, giá, tồn kho)
const activeColorDetail = computed(() => {
  if (props.product.colorDetails && props.product.colorDetails[activeColor.value]) {
    return props.product.colorDetails[activeColor.value]
  }
  return null
})

// Ảnh tự động đổi theo màu đang chọn
const displayImage = computed(() => {
  if (activeColorDetail.value && activeColorDetail.value.image_url) {
    return activeColorDetail.value.image_url
  }
  if (props.product.colorImages && props.product.colorImages[activeColor.value]) {
    return props.product.colorImages[activeColor.value]
  }
  return props.product.image
})

// Mã SKU (Article ID) theo màu sắc đang chọn
const displayArticleId = computed(() => {
  if (activeColorDetail.value && activeColorDetail.value.article_id) {
    return activeColorDetail.value.article_id
  }
  return props.product.articleId || props.product.id
})

// Tồn kho theo màu
const displayStock = computed(() => {
  if (activeColorDetail.value && activeColorDetail.value.stock_quantity !== undefined) {
    return activeColorDetail.value.stock_quantity
  }
  return props.product.stockQuantity
})

// Giá theo màu
const displayOriginalPrice = computed(() => {
  if (activeColorDetail.value && activeColorDetail.value.price) {
    return activeColorDetail.value.price
  }
  return props.product.originalPrice
})

const displayFinalPrice = computed(() => {
  const orig = displayOriginalPrice.value
  const disc = props.product.discountPercent || 0
  return disc > 0 ? (orig * (1 - disc / 100)) : orig
})

const formatCurrency = (val) => {
  const num = Number(val || 0)
  if (num > 0 && num < 1000) {
    return `$${num.toFixed(2)}`
  }
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(num)
}

const displayMatchScore = computed(() => {
  if (props.product.matchScore === undefined || props.product.matchScore === null) return null
  return props.product.matchScore > 1 ? Math.round(props.product.matchScore) : Math.round(props.product.matchScore * 100)
})

const matchScoreLabel = computed(() => {
  if (!displayMatchScore.value) return 'Gợi ý AI'
  if (displayMatchScore.value >= 95) return `🔥 ${displayMatchScore.value}% Khớp chuẩn`
  if (displayMatchScore.value >= 80) return `✨ ${displayMatchScore.value}% Liên quan`
  return `💡 ${displayMatchScore.value}% Tương đồng`
})

const formattedOriginalPrice = computed(() => formatCurrency(displayOriginalPrice.value))
const formattedFinalPrice = computed(() => formatCurrency(displayFinalPrice.value))
const formattedSavings = computed(() => formatCurrency(displayOriginalPrice.value - displayFinalPrice.value))

// Chuyển đổi tên màu sang mã màu trực quan
const getColorHex = (name) => {
  if (!name) return '#a1a1aa'
  const lower = name.toLowerCase()
  if (lower.includes('off white')) return '#fcfaf2'
  if (lower.includes('white')) return '#ffffff'
  if (lower.includes('black')) return '#18181b'
  if (lower.includes('dark grey') || lower.includes('dark gray')) return '#4b5563'
  if (lower.includes('light grey') || lower.includes('light gray')) return '#d1d5db'
  if (lower.includes('grey') || lower.includes('gray')) return '#9ca3af'
  if (lower.includes('dark blue') || lower.includes('navy')) return '#1e3a8a'
  if (lower.includes('light blue')) return '#93c5fd'
  if (lower.includes('blue')) return '#3b82f6'
  if (lower.includes('dark pink')) return '#db2777'
  if (lower.includes('light pink')) return '#fbcfe8'
  if (lower.includes('pink')) return '#f472b6'
  if (lower.includes('dark red') || lower.includes('burgundy')) return '#881337'
  if (lower.includes('red')) return '#ef4444'
  if (lower.includes('light orange')) return '#fed7aa'
  if (lower.includes('orange')) return '#f97316'
  if (lower.includes('dark yellow')) return '#ca8a04'
  if (lower.includes('yellow')) return '#facc15'
  if (lower.includes('light green')) return '#86efac'
  if (lower.includes('dark green')) return '#14532d'
  if (lower.includes('green') || lower.includes('khaki')) return '#16a34a'
  if (lower.includes('dark beige')) return '#d4c5b9'
  if (lower.includes('light beige')) return '#f5f0eb'
  if (lower.includes('beige')) return '#e5dfd3'
  if (lower.includes('purple')) return '#9333ea'
  if (lower.includes('turquoise')) return '#06b6d4'
  if (lower.includes('gold')) return '#eab308'
  if (lower.includes('silver')) return '#cbd5e1'
  return '#cbd5e1'
}

const handleViewDetails = () => {
  emit('view-details', {
    ...props.product,
    color: activeColor.value,
    image: displayImage.value,
    originalPrice: displayOriginalPrice.value,
    finalPrice: displayFinalPrice.value,
    stockQuantity: displayStock.value,
    articleId: displayArticleId.value
  })
}

const handleAddToCart = () => {
  emit('add-to-cart', {
    ...props.product,
    color: activeColor.value,
    image: displayImage.value,
    originalPrice: displayOriginalPrice.value,
    finalPrice: displayFinalPrice.value,
    stockQuantity: displayStock.value,
    articleId: displayArticleId.value
  })
}
</script>

<template>
  <div 
    class="group relative flex flex-col bg-white rounded-xl border transition-all duration-300 overflow-hidden"
    :class="[
      isHighlighted 
        ? 'border-pink-500 ring-2 ring-pink-500/30 shadow-lg shadow-pink-500/15 transform -translate-y-1' 
        : 'border-zinc-200 hover:border-pink-300 shadow-xs hover:shadow-md'
    ]"
  >
    <!-- AI Highlight & Match Score Badge in Hot Pink / Rose / Violet -->
    <div 
      v-if="isHighlighted || displayMatchScore" 
      class="absolute top-3 left-3 z-10 flex items-center gap-1 px-2.5 py-1 rounded-full text-white text-[11px] font-black shadow-md tracking-tight"
      :class="[
        displayMatchScore >= 95
          ? 'bg-gradient-to-r from-pink-600 via-rose-600 to-amber-500 shadow-pink-500/40 ring-1 ring-white/50 animate-pulse'
          : displayMatchScore >= 80
            ? 'bg-gradient-to-r from-pink-600 to-purple-600 shadow-pink-500/30'
            : 'bg-gradient-to-r from-zinc-800 to-zinc-700 shadow-zinc-500/20'
      ]"
    >
      <Sparkles class="w-3 h-3 shrink-0" />
      <span>{{ matchScoreLabel }}</span>
    </div>

    <!-- Image Area: Updates dynamically based on activeColor -->
    <div class="relative w-full aspect-[4/3] bg-zinc-100/80 overflow-hidden flex items-center justify-center">
      <img 
        :src="displayImage" 
        :alt="`${product.name} - Màu ${activeColor}`"
        class="w-full h-full object-cover object-center transition-all duration-300 group-hover:scale-105"
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
      <!-- Department, Article ID & Rating -->
      <div class="flex items-center justify-between gap-2 text-xs text-zinc-500 mb-1">
        <div class="flex items-center gap-1.5 min-w-0">
          <span class="font-bold uppercase tracking-wider text-pink-600 text-[11px] truncate" :title="product.department">
            {{ product.department || product.brand }}
          </span>
          <span class="text-[10px] text-zinc-400 font-mono" title="Mã SKU màu CSDL">#{{ displayArticleId }}</span>
        </div>
        <div class="flex items-center gap-1 text-amber-500 font-semibold shrink-0">
          <Star class="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
          <span>{{ product.rating }}</span>
          <span class="text-zinc-400 font-normal">({{ product.reviewsCount }})</span>
        </div>
      </div>

      <!-- Product Name -->
      <h3 
        @click="handleViewDetails"
        class="font-bold text-zinc-900 text-base leading-snug line-clamp-1 group-hover:text-pink-600 transition-colors cursor-pointer"
        :title="product.name"
      >
        {{ product.name }}
      </h3>

      <!-- Product Type, Group & Match Reason -->
      <div class="flex items-center justify-between gap-1 mt-0.5 text-[11px]">
        <p class="text-zinc-500 font-medium line-clamp-1">
          Loại: <span class="text-zinc-700 font-semibold">{{ product.productType || product.category }}</span>
          <span v-if="product.pattern" class="text-zinc-400 text-[10px]"> • {{ product.pattern }}</span>
        </p>
        <span v-if="product.matchReason" class="text-[10px] font-bold text-pink-700 bg-pink-50 px-1.5 py-0.2 rounded border border-pink-200/70 shrink-0">
          🎯 {{ product.matchReason }}
        </span>
      </div>

      <!-- Interactive Color Swatches Row (Clicking changes photo immediately!) -->
      <div v-if="product.availableColors && product.availableColors.length > 0" class="mt-2.5 mb-1.5 p-1.5 bg-zinc-50/80 rounded-lg border border-zinc-100">
        <div class="flex items-center justify-between text-[11px] mb-1">
          <span class="text-zinc-600 font-medium flex items-center gap-1">
            <span>Màu:</span>
            <strong class="text-pink-600 font-bold">{{ activeColor }}</strong>
          </span>
          <span class="text-[10px] text-zinc-400 font-medium">
            {{ product.availableColors.length }} màu
          </span>
        </div>

        <div class="flex items-center gap-1.5 flex-wrap">
          <button
            v-for="c in product.availableColors"
            :key="c"
            @click.stop="activeColor = c"
            type="button"
            class="group/dot relative p-0.5 rounded-full transition-all cursor-pointer border flex items-center justify-center"
            :class="[
              activeColor === c
                ? 'ring-2 ring-pink-500 border-white shadow-xs scale-110'
                : 'border-zinc-300 hover:border-pink-400 opacity-75 hover:opacity-100'
            ]"
            :title="`Đổi sang màu: ${c}`"
          >
            <span 
              class="w-4 h-4 rounded-full border border-black/10 block shadow-2xs"
              :style="{ backgroundColor: getColorHex(c) }"
            ></span>
          </button>
        </div>
      </div>

      <!-- Database Variant Info: Size & Stock Status -->
      <div class="flex flex-wrap items-center gap-1.5 mt-1 mb-2">
        <span 
          v-if="product.size"
          class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold bg-zinc-100 text-zinc-700 border border-zinc-200/60"
        >
          📏 Size {{ product.size }}
        </span>
        <span 
          v-if="displayStock !== undefined"
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold"
          :class="displayStock > 0 ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/70' : 'bg-red-50 text-red-600 border border-red-200'"
        >
          <span class="w-1.5 h-1.5 rounded-full" :class="displayStock > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'"></span>
          {{ displayStock > 0 ? `Còn ${displayStock} sp` : 'Hết hàng' }}
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
        <span v-if="product.discountPercent > 0" class="text-[11px] font-bold text-pink-700 bg-pink-50 px-2 py-0.5 rounded border border-pink-200">
          Tiết kiệm {{ formattedSavings }}
        </span>
      </div>

      <!-- Action Buttons -->
      <div class="grid grid-cols-2 gap-2">
        <button 
          @click="handleViewDetails"
          class="w-full py-2 px-3 rounded-lg border border-zinc-200 text-xs font-bold text-zinc-700 bg-white hover:bg-zinc-50 hover:border-pink-300 hover:text-pink-600 transition-all flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <Eye class="w-3.5 h-3.5 text-zinc-400 group-hover:text-pink-600" />
          <span>Chi tiết</span>
        </button>

        <button 
          @click="handleAddToCart"
          class="w-full py-2 px-3 rounded-lg bg-zinc-950 hover:bg-gradient-to-r hover:from-pink-600 hover:to-rose-600 active:scale-98 text-xs font-bold text-white shadow-sm transition-all flex items-center justify-center gap-1.5 cursor-pointer hover:shadow-md hover:shadow-pink-500/20"
        >
          <ShoppingCart class="w-3.5 h-3.5" />
          <span>Thêm giỏ</span>
        </button>
      </div>
    </div>
  </div>
</template>
