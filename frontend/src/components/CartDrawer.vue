<script setup>
import { computed } from 'vue'
import { 
  X, 
  Trash2, 
  Plus, 
  Minus, 
  ShoppingBag, 
  ArrowRight,
  ShieldCheck,
  Truck
} from 'lucide-vue-next'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  },
  cartItems: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close', 'update-quantity', 'remove-item', 'checkout'])

const formatCurrency = (val) => {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val)
}

const subtotal = computed(() => {
  return props.cartItems.reduce((sum, item) => sum + (item.product.finalPrice * item.quantity), 0)
})

const totalSavings = computed(() => {
  return props.cartItems.reduce((sum, item) => {
    const diff = item.product.originalPrice - item.product.finalPrice
    return sum + (diff * item.quantity)
  }, 0)
})

const freeShippingThreshold = 5000000 // 5 triệu VND
const freeShippingProgress = computed(() => {
  if (subtotal.value >= freeShippingThreshold) return 100
  return Math.min(100, Math.round((subtotal.value / freeShippingThreshold) * 100))
})
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 overflow-hidden">
    <!-- Backdrop -->
    <div 
      @click="emit('close')"
      class="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity duration-300"
    ></div>

    <div class="fixed inset-y-0 right-0 max-w-full flex pl-10">
      <div class="w-screen max-w-md bg-white shadow-2xl flex flex-col">
        <!-- Header in Black & Pink -->
        <div class="p-4 border-b border-zinc-800 flex items-center justify-between bg-zinc-950 text-white">
          <div class="flex items-center gap-2">
            <ShoppingBag class="w-5 h-5 text-pink-400" />
            <h2 class="font-bold text-white text-lg">Giỏ Hàng Của Bạn</h2>
            <span class="bg-gradient-to-r from-pink-600 to-rose-600 text-white text-xs font-bold px-2 py-0.5 rounded-full shadow-xs">
              {{ cartItems.reduce((acc, item) => acc + item.quantity, 0) }} món
            </span>
          </div>
          <button 
            @click="emit('close')"
            class="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors cursor-pointer"
          >
            <X class="w-5 h-5" />
          </button>
        </div>

        <!-- Free Shipping Progress Bar in Pink -->
        <div class="px-4 py-2.5 bg-pink-50 border-b border-pink-100">
          <div class="flex justify-between items-center text-xs font-medium text-pink-950 mb-1.5">
            <span v-if="subtotal >= freeShippingThreshold" class="flex items-center gap-1 font-bold text-pink-700">
              <Truck class="w-3.5 h-3.5 text-pink-600" />
              Bạn đã đủ điều kiện Miễn Phí Vận Chuyển!
            </span>
            <span v-else>
              Mua thêm <strong class="text-pink-700 font-bold">{{ formatCurrency(freeShippingThreshold - subtotal) }}</strong> để Miễn Phí Ship
            </span>
            <span class="text-pink-600 font-bold">{{ freeShippingProgress }}%</span>
          </div>
          <div class="w-full bg-pink-200/80 h-1.5 rounded-full overflow-hidden">
            <div 
              class="h-full rounded-full bg-gradient-to-r from-pink-600 to-rose-500 transition-all duration-500"
              :style="{ width: `${freeShippingProgress}%` }"
            ></div>
          </div>
        </div>

        <!-- Cart Items List -->
        <div class="flex-1 overflow-y-auto p-4 space-y-3">
          <div v-if="cartItems.length === 0" class="py-16 text-center">
            <div class="w-16 h-16 mx-auto mb-3 bg-pink-50 rounded-full flex items-center justify-center text-pink-400">
              <ShoppingBag class="w-8 h-8" />
            </div>
            <h3 class="font-bold text-zinc-800 mb-1">Giỏ hàng của bạn đang trống</h3>
            <p class="text-xs text-zinc-500 mb-4 max-w-xs mx-auto">
              Hãy hỏi Trợ lý AI để nhận các gợi ý ưu đãi hấp dẫn hoặc duyệt qua danh mục sản phẩm nhé!
            </p>
          </div>

          <div 
            v-for="item in cartItems" 
            :key="item.product.id"
            class="flex gap-3 p-3 bg-zinc-50 rounded-xl border border-zinc-200/80 hover:border-pink-300 transition-colors"
          >
            <div class="w-16 h-16 rounded-lg bg-white border border-zinc-200 overflow-hidden shrink-0 flex items-center justify-center p-1">
              <img :src="item.product.image" :alt="item.product.name" class="w-full h-full object-contain" />
            </div>

            <div class="flex-1 min-w-0 flex flex-col justify-between">
              <div class="flex items-start justify-between gap-1">
                <h4 class="text-xs font-bold text-zinc-900 line-clamp-1">
                  {{ item.product.name }}
                </h4>
                <button 
                  @click="emit('remove-item', item.product.id)"
                  class="text-zinc-400 hover:text-pink-600 transition-colors p-0.5 cursor-pointer"
                  title="Xóa món này"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </button>
              </div>

              <div class="flex items-center justify-between mt-2">
                <div class="flex items-baseline gap-1.5">
                  <span class="text-xs font-black text-pink-600">{{ formatCurrency(item.product.finalPrice * item.quantity) }}</span>
                </div>

                <!-- Quantity changer -->
                <div class="flex items-center border border-zinc-300 rounded-lg bg-white">
                  <button 
                    @click="emit('update-quantity', item.product.id, item.quantity - 1)"
                    class="p-1 hover:bg-pink-50 text-zinc-600 hover:text-pink-600 rounded-l-lg transition-colors cursor-pointer"
                  >
                    <Minus class="w-3 h-3" />
                  </button>
                  <span class="px-2 text-xs font-bold text-zinc-800">{{ item.quantity }}</span>
                  <button 
                    @click="emit('update-quantity', item.product.id, item.quantity + 1)"
                    class="p-1 hover:bg-pink-50 text-zinc-600 hover:text-pink-600 rounded-r-lg transition-colors cursor-pointer"
                  >
                    <Plus class="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer in Pink & Black -->
        <div v-if="cartItems.length > 0" class="p-4 border-t border-zinc-200 bg-zinc-50 space-y-3">
          <div class="space-y-1.5 text-xs">
            <div class="flex justify-between text-zinc-500">
              <span>Tạm tính</span>
              <span class="font-medium text-zinc-800">{{ formatCurrency(subtotal) }}</span>
            </div>
            <div v-if="totalSavings > 0" class="flex justify-between text-pink-600 font-bold">
              <span>Tổng tiết kiệm</span>
              <span>-{{ formatCurrency(totalSavings) }}</span>
            </div>
            <div class="flex justify-between text-zinc-500">
              <span>Phí vận chuyển</span>
              <span class="font-medium">{{ subtotal >= freeShippingThreshold ? 'MIỄN PHÍ' : '30.000 ₫' }}</span>
            </div>
            <div class="pt-2 border-t border-zinc-200 flex justify-between text-sm font-bold text-zinc-900">
              <span>Tổng thanh toán</span>
              <span class="text-base font-black text-pink-600">
                {{ formatCurrency(subtotal + (subtotal >= freeShippingThreshold ? 0 : 30000)) }}
              </span>
            </div>
          </div>

          <button 
            @click="emit('checkout')"
            class="w-full py-3 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 text-white rounded-xl font-black text-sm shadow-lg shadow-pink-500/25 flex items-center justify-center gap-2 transition-all cursor-pointer hover:shadow-xl hover:shadow-pink-500/35 active:scale-98"
          >
            <span>Tiến Hành Thanh Toán</span>
            <ArrowRight class="w-4 h-4" />
          </button>

          <div class="flex items-center justify-center gap-1.5 text-[11px] text-zinc-400 text-center">
            <ShieldCheck class="w-3.5 h-3.5 text-pink-500" />
            <span>Thanh toán an toàn, bảo mật chuẩn 256-bit</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
