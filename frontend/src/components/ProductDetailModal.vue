<script setup>
import { ref, computed, watch } from 'vue'
import { 
  X, 
  ShoppingCart, 
  Star, 
  ShieldCheck, 
  Truck, 
  RotateCcw,
  Heart,
  Check,
  Database
} from 'lucide-vue-next'

const props = defineProps({
  product: {
    type: Object,
    default: null
  },
  isOpen: {
    type: Boolean,
    default: false
  },
  isWishlisted: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'add-to-cart', 'toggle-wishlist'])

const quantity = ref(1)
const selectedColor = ref(props.product?.color || 'Tiêu chuẩn')
const selectedSize = ref(props.product?.size || 'M')

// Đồng bộ khi mở modal với sản phẩm mới hoặc khi product thay đổi
watch(() => props.product, (newProd) => {
  if (newProd) {
    selectedColor.value = newProd.color || 'Tiêu chuẩn'
    selectedSize.value = newProd.size || 'M'
    quantity.value = 1
  }
}, { immediate: true })

// Chi tiết màu sắc được chọn lấy từ CSDL H&M
const activeColorDetail = computed(() => {
  if (props.product?.colorDetails && props.product.colorDetails[selectedColor.value]) {
    return props.product.colorDetails[selectedColor.value]
  }
  return null
})

// Ảnh thay đổi ngay lập tức theo màu đang chọn
const displayImage = computed(() => {
  if (activeColorDetail.value && activeColorDetail.value.image_url) {
    return activeColorDetail.value.image_url
  }
  if (props.product?.colorImages && props.product.colorImages[selectedColor.value]) {
    return props.product.colorImages[selectedColor.value]
  }
  return props.product?.image
})

// Mã SKU (Article ID) theo màu sắc đang chọn
const displayArticleId = computed(() => {
  if (activeColorDetail.value && activeColorDetail.value.article_id) {
    return activeColorDetail.value.article_id
  }
  return props.product?.articleId || props.product?.id
})

// Giá theo màu
const displayOriginalPrice = computed(() => {
  if (activeColorDetail.value && activeColorDetail.value.price) {
    return activeColorDetail.value.price
  }
  return props.product?.originalPrice || 29.99
})

const displayFinalPrice = computed(() => {
  const orig = displayOriginalPrice.value
  const disc = props.product?.discountPercent || 0
  return disc > 0 ? (orig * (1 - disc / 100)) : orig
})

// Danh sách kích cỡ theo màu
const availableSizesForColor = computed(() => {
  if (activeColorDetail.value && activeColorDetail.value.sizes && activeColorDetail.value.sizes.length > 0) {
    return activeColorDetail.value.sizes
  }
  return props.product?.availableSizes || [selectedSize.value]
})

// Tồn kho theo màu & kích cỡ đang chọn
const displayStock = computed(() => {
  if (activeColorDetail.value) {
    if (activeColorDetail.value.size_stocks && activeColorDetail.value.size_stocks[selectedSize.value] !== undefined) {
      return activeColorDetail.value.size_stocks[selectedSize.value]
    }
    return activeColorDetail.value.stock_quantity
  }
  return props.product?.stockQuantity ?? 15
})

const formatCurrency = (val) => {
  const num = Number(val || 0)
  if (num > 0 && num < 1000) {
    return `$${num.toFixed(2)}`
  }
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(num)
}

const incrementQuantity = () => {
  if (quantity.value < (displayStock.value || 10)) quantity.value++
}

const decrementQuantity = () => {
  if (quantity.value > 1) quantity.value--
}

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

// Bảng thông số kỹ thuật CSDL cập nhật theo thời gian thực
const dynamicSpecs = computed(() => {
  if (!props.product) return {}
  return {
    "Mã SP (Product ID)": String(props.product.id),
    "Mã SKU màu (Article ID)": String(displayArticleId.value),
    "Loại sản phẩm (Type)": props.product.productType || props.product.category || 'N/A',
    "Nhóm hàng (Product Group)": props.product.productGroup || 'Thời trang H&M',
    "Phân khúc (Gender)": props.product.genderGroup || 'H&M Collection',
    "Phong cách (Department)": props.product.department || 'Jersey Basic',
    "Họa tiết (Pattern)": props.product.pattern || 'Solid',
    "Màu sắc đang chọn": selectedColor.value,
    "Kích cỡ đang chọn": selectedSize.value,
    "Tồn kho phiên bản": `${displayStock.value} sản phẩm`
  }
})

const handleAddToCart = () => {
  if (props.product) {
    emit('add-to-cart', {
      ...props.product,
      color: selectedColor.value,
      size: selectedSize.value,
      image: displayImage.value,
      originalPrice: displayOriginalPrice.value,
      finalPrice: displayFinalPrice.value,
      stockQuantity: displayStock.value,
      articleId: displayArticleId.value,
      variantId: `${props.product.id}-${selectedColor.value}-${selectedSize.value}`
    }, quantity.value)
    quantity.value = 1
    emit('close')
  }
}
</script>

<template>
  <div 
    v-if="isOpen && product" 
    class="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4 sm:p-6"
  >
    <!-- Backdrop -->
    <div 
      @click="emit('close')"
      class="fixed inset-0 bg-black/70 backdrop-blur-xs transition-opacity animate-in fade-in cursor-pointer"
    ></div>

    <!-- Modal Container -->
    <div 
      class="relative w-full max-w-4xl bg-white rounded-2xl shadow-2xl border border-zinc-200 overflow-hidden z-10 animate-in zoom-in-95 duration-200"
    >
      <!-- Close Button -->
      <button 
        @click="emit('close')"
        class="absolute top-4 right-4 z-20 p-2 rounded-full bg-zinc-100/90 hover:bg-zinc-200 text-zinc-500 hover:text-zinc-900 transition-colors cursor-pointer"
      >
        <X class="w-5 h-5" />
      </button>

      <div class="grid grid-cols-1 md:grid-cols-2">
        <!-- Left: Image Section (Reactive based on selectedColor) -->
        <div class="relative bg-zinc-100 flex flex-col items-center justify-center p-6 border-b md:border-b-0 md:border-r border-zinc-200">
          <div class="relative w-full flex items-center justify-center overflow-hidden rounded-xl bg-white/60 p-2 shadow-2xs">
            <img 
              :src="displayImage" 
              :alt="`${product.name} - ${selectedColor}`"
              class="w-full h-auto max-h-80 object-contain rounded-lg transition-all duration-300"
              @error="(e) => e.target.src = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80'"
            />
          </div>

          <!-- AI Match Score Badge -->
          <div 
            v-if="product.matchScore"
            class="absolute top-4 left-4 px-2.5 py-1 rounded-full bg-gradient-to-r from-pink-600 to-rose-600 text-white text-xs font-black shadow-md shadow-pink-500/25"
          >
            🎯 {{ Math.round(product.matchScore * 100) }}% Khớp AI
          </div>

          <!-- Discount badge in Pink -->
          <div 
            v-else-if="product.discountPercent > 0"
            class="absolute top-4 left-4 px-2.5 py-1 rounded-full bg-pink-50 border border-pink-200 text-pink-600 text-xs font-black shadow-xs"
          >
            GIẢM {{ product.discountPercent }}%
          </div>

          <!-- Active Color Tag on Photo -->
          <div class="absolute bottom-20 left-6 px-2.5 py-1 rounded-full bg-zinc-950/80 backdrop-blur-xs text-white text-[11px] font-bold shadow-md flex items-center gap-1.5">
            <span 
              class="w-2.5 h-2.5 rounded-full border border-white/40"
              :style="{ backgroundColor: getColorHex(selectedColor) }"
            ></span>
            <span>Màu đang xem: {{ selectedColor }}</span>
          </div>

          <!-- Stock & SKU Bar -->
          <div class="w-full mt-4 p-3 bg-white rounded-xl border border-zinc-200/80 shadow-2xs space-y-1.5">
            <div class="flex items-center justify-between text-xs font-medium">
              <span class="text-zinc-500">Tình trạng phiên bản:</span>
              <span 
                class="font-bold inline-flex items-center gap-1.5"
                :class="displayStock > 0 ? 'text-emerald-600' : 'text-rose-600'"
              >
                <span class="w-2 h-2 rounded-full" :class="displayStock > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'"></span>
                {{ displayStock > 0 ? `Còn ${displayStock} sản phẩm` : 'Tạm hết hàng' }}
              </span>
            </div>
            <div class="flex items-center justify-between text-[11px] font-mono text-zinc-500 truncate">
              <span>Mã SKU CSDL:</span>
              <span class="text-pink-600 font-bold truncate">#{{ displayArticleId }}</span>
            </div>
          </div>
        </div>

        <!-- Right: Details Section -->
        <div class="p-6 flex flex-col justify-between max-h-[85vh] overflow-y-auto">
          <div>
            <!-- Header Badges -->
            <div class="flex items-center justify-between text-xs text-zinc-500 mb-1.5">
              <div class="flex items-center gap-1.5">
                <span class="font-bold uppercase tracking-wider text-pink-600 bg-pink-50 px-2 py-0.5 rounded border border-pink-200">
                  {{ product.department || product.brand }}
                </span>
                <span class="font-mono text-zinc-400 text-xs">#{{ product.id }}</span>
              </div>
              <div class="flex items-center gap-1 text-amber-500 font-semibold">
                <Star class="w-4 h-4 fill-amber-400 text-amber-400" />
                <span>{{ product.rating }}</span>
                <span class="text-zinc-400 font-normal">({{ product.reviewsCount }})</span>
              </div>
            </div>

            <h2 class="text-xl font-black text-zinc-900 mb-1">
              {{ product.name }}
            </h2>

            <div class="text-xs text-zinc-500 font-medium mb-3 flex items-center gap-2">
              <span>Loại: <strong class="text-zinc-800">{{ product.productType || product.category }}</strong></span>
              <span>•</span>
              <span>Họa tiết: <strong class="text-zinc-800">{{ product.pattern || 'Solid' }}</strong></span>
            </div>

            <!-- Description from DB -->
            <div class="mb-4">
              <div class="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-1">Mô tả sản phẩm (CSDL)</div>
              <p class="text-xs text-zinc-600 leading-relaxed bg-zinc-50 p-2.5 rounded-lg border border-zinc-100">
                {{ product.detailDesc || product.description }}
              </p>
            </div>

            <!-- Pricing Area (Updates with selected color) -->
            <div class="flex items-baseline gap-3 mb-4 p-3 bg-pink-50/60 rounded-xl border border-pink-100">
              <span class="text-2xl font-black text-pink-600">
                {{ formatCurrency(displayFinalPrice) }}
              </span>
              <span class="text-xs text-zinc-400 line-through">
                {{ formatCurrency(displayOriginalPrice) }}
              </span>
              <span v-if="product.discountPercent > 0" class="ml-auto text-xs font-bold text-pink-700 bg-pink-100 px-2 py-0.5 rounded">
                Tiết kiệm {{ formatCurrency(displayOriginalPrice - displayFinalPrice) }}
              </span>
            </div>

            <!-- Color Options (Clicking changes image, SKU, stock & price immediately!) -->
            <div v-if="product.availableColors && product.availableColors.length > 0" class="mb-4">
              <div class="text-[11px] font-bold text-zinc-700 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                <span>Chọn màu sắc ({{ product.availableColors.length }} màu có ảnh riêng)</span>
                <span class="text-pink-600 font-bold capitalize">{{ selectedColor }}</span>
              </div>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="c in product.availableColors"
                  :key="c"
                  @click="selectedColor = c"
                  type="button"
                  class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer border flex items-center gap-2"
                  :class="[
                    selectedColor === c 
                      ? 'bg-zinc-950 text-pink-400 border-zinc-950 shadow-sm ring-2 ring-pink-500/40 font-bold' 
                      : 'bg-white text-zinc-700 border-zinc-200 hover:border-pink-300 hover:bg-pink-50/50'
                  ]"
                >
                  <span 
                    class="w-3.5 h-3.5 rounded-full border border-black/20 shrink-0"
                    :style="{ backgroundColor: getColorHex(c) }"
                  ></span>
                  <span>{{ c }}</span>
                  <Check v-if="selectedColor === c" class="w-3.5 h-3.5 text-pink-400" />
                </button>
              </div>
            </div>

            <!-- Size Options -->
            <div v-if="availableSizesForColor && availableSizesForColor.length > 0" class="mb-4">
              <div class="text-[11px] font-bold text-zinc-700 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                <span>Kích cỡ có sẵn</span>
                <span class="text-pink-600 font-bold">{{ selectedSize }}</span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="s in availableSizesForColor"
                  :key="s"
                  @click="selectedSize = s"
                  type="button"
                  class="min-w-9 px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer border text-center"
                  :class="selectedSize === s ? 'bg-pink-600 text-white border-pink-600 shadow-xs' : 'bg-white text-zinc-700 border-zinc-200 hover:border-pink-300'"
                >
                  {{ s }}
                </button>
              </div>
            </div>

            <!-- Key Specs Table (Full DB fields synced in real-time) -->
            <div class="space-y-1.5 mb-5">
              <div class="text-[11px] font-bold text-zinc-700 uppercase tracking-wider flex items-center gap-1.5">
                <Database class="w-3.5 h-3.5 text-pink-600" />
                <span>Thông số CSDL (Database Schema & Specifications)</span>
              </div>
              <div class="grid grid-cols-2 gap-2 text-xs">
                <div 
                  v-for="(val, key) in dynamicSpecs" 
                  :key="key"
                  class="bg-zinc-50 p-2 rounded-lg border border-zinc-100"
                >
                  <div class="text-[10px] text-zinc-400 uppercase font-bold">{{ key }}</div>
                  <div class="text-zinc-800 font-semibold truncate" :title="val">{{ val }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- Add to Cart & Controls in Pink & Black -->
          <div class="space-y-3 pt-3 border-t border-zinc-100">
            <div class="flex items-center gap-3">
              <!-- Quantity Selector -->
              <div class="flex items-center border border-zinc-200 rounded-lg bg-white">
                <button 
                  @click="decrementQuantity"
                  class="px-3 py-2 text-zinc-600 hover:bg-zinc-100 rounded-l-lg transition-colors font-bold text-sm cursor-pointer"
                >
                  -
                </button>
                <span class="px-3 py-2 text-xs font-bold text-zinc-900 min-w-8 text-center">
                  {{ quantity }}
                </span>
                <button 
                  @click="incrementQuantity"
                  class="px-3 py-2 text-zinc-600 hover:bg-zinc-100 rounded-r-lg transition-colors font-bold text-sm cursor-pointer"
                >
                  +
                </button>
              </div>

              <!-- Primary Add to Cart in Hot Pink -->
              <button 
                @click="handleAddToCart"
                :disabled="displayStock <= 0"
                class="flex-1 py-2.5 px-4 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 active:scale-98 disabled:opacity-50 disabled:pointer-events-none text-white rounded-lg font-bold text-xs shadow-md shadow-pink-500/25 flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                <ShoppingCart class="w-4 h-4" />
                <span>
                  {{ displayStock > 0 ? `Thêm vào giỏ (${formatCurrency(displayFinalPrice * quantity)})` : 'Hết hàng' }}
                </span>
              </button>

              <!-- Wishlist -->
              <button 
                @click="emit('toggle-wishlist', product)"
                class="p-2.5 rounded-lg border border-zinc-200 text-zinc-600 hover:text-pink-600 hover:border-pink-300 transition-colors cursor-pointer"
                :class="{ 'border-pink-300 text-pink-600 bg-pink-50': isWishlisted }"
                title="Yêu thích"
              >
                <Heart class="w-4 h-4" :class="{ 'fill-pink-600 text-pink-600': isWishlisted }" />
              </button>
            </div>

            <!-- Trust badges -->
            <div class="flex items-center justify-between text-[10px] text-zinc-500 pt-2">
              <div class="flex items-center gap-1">
                <Truck class="w-3.5 h-3.5 text-pink-600" />
                <span>Giao hàng 2H</span>
              </div>
              <div class="flex items-center gap-1">
                <ShieldCheck class="w-3.5 h-3.5 text-pink-600" />
                <span>Bảo hành 2 năm</span>
              </div>
              <div class="flex items-center gap-1">
                <RotateCcw class="w-3.5 h-3.5 text-pink-600" />
                <span>Đổi trả 30 ngày</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
