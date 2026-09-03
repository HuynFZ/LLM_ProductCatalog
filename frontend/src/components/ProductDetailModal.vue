<script setup>
import { ref } from 'vue'
import { 
  X, 
  ShoppingCart, 
  Star, 
  ShieldCheck, 
  Truck, 
  RotateCcw,
  Heart
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

const formatCurrency = (val) => {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val)
}

const incrementQuantity = () => {
  if (quantity.value < 10) quantity.value++
}

const decrementQuantity = () => {
  if (quantity.value > 1) quantity.value--
}

const handleAddToCart = () => {
  if (props.product) {
    emit('add-to-cart', props.product, quantity.value)
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
      class="fixed inset-0 bg-black/70 backdrop-blur-xs transition-opacity animate-in fade-in"
    ></div>

    <!-- Modal Container -->
    <div 
      class="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-zinc-200 overflow-hidden z-10 animate-in zoom-in-95 duration-200"
    >
      <!-- Close Button -->
      <button 
        @click="emit('close')"
        class="absolute top-4 right-4 z-20 p-2 rounded-full bg-zinc-100/90 hover:bg-zinc-200 text-zinc-500 hover:text-zinc-900 transition-colors cursor-pointer"
      >
        <X class="w-5 h-5" />
      </button>

      <div class="grid grid-cols-1 md:grid-cols-2">
        <!-- Left: Image Section -->
        <div class="relative bg-zinc-100 flex items-center justify-center p-6 border-b md:border-b-0 md:border-r border-zinc-200">
          <img 
            :src="product.image" 
            :alt="product.name"
            class="w-full h-auto max-h-72 object-contain rounded-xl shadow-xs"
            @error="(e) => e.target.src = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80'"
          />

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
        </div>

        <!-- Right: Details Section -->
        <div class="p-6 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between text-xs text-zinc-500 mb-1">
              <span class="font-bold uppercase tracking-wider text-pink-600">{{ product.brand }}</span>
              <div class="flex items-center gap-1 text-amber-500 font-semibold">
                <Star class="w-4 h-4 fill-amber-400 text-amber-400" />
                <span>{{ product.rating }}</span>
                <span class="text-zinc-400 font-normal">({{ product.reviewsCount }} đánh giá)</span>
              </div>
            </div>

            <h2 class="text-xl font-black text-zinc-900 mb-2">
              {{ product.name }}
            </h2>

            <p class="text-xs text-zinc-600 mb-4 leading-relaxed">
              {{ product.description }}
            </p>

            <!-- Pricing Area -->
            <div class="flex items-baseline gap-3 mb-4 p-3 bg-pink-50/50 rounded-xl border border-pink-100">
              <span class="text-xl font-black text-pink-600">
                {{ formatCurrency(product.finalPrice) }}
              </span>
              <span class="text-xs text-zinc-400 line-through">
                {{ formatCurrency(product.originalPrice) }}
              </span>
              <span class="ml-auto text-xs font-bold text-pink-700 bg-pink-100/80 px-2 py-0.5 rounded">
                Tiết kiệm {{ formatCurrency(product.originalPrice - product.finalPrice) }}
              </span>
            </div>

            <!-- Key Specs Table -->
            <div v-if="product.specs" class="space-y-1.5 mb-5">
              <div class="text-xs font-bold text-zinc-700 uppercase tracking-wider">Thông số kỹ thuật</div>
              <div class="grid grid-cols-2 gap-2 text-xs">
                <div 
                  v-for="(val, key) in product.specs" 
                  :key="key"
                  class="bg-zinc-50 p-2 rounded-lg border border-zinc-100"
                >
                  <div class="text-[10px] text-zinc-400 uppercase font-bold">{{ key }}</div>
                  <div class="text-zinc-800 font-semibold truncate">{{ val }}</div>
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
                class="flex-1 py-2.5 px-4 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 active:scale-98 text-white rounded-lg font-bold text-xs shadow-md shadow-pink-500/25 flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                <ShoppingCart class="w-4 h-4" />
                <span>Thêm vào giỏ ({{ formatCurrency(product.finalPrice * quantity) }})</span>
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
