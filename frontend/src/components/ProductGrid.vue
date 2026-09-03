<script setup>
import { ref, computed } from 'vue'
import ProductCard from './ProductCard.vue'
import { 
  Search, 
  ShoppingBag, 
  Sparkles, 
  RotateCcw,
  Layers,
  ArrowUpDown,
  RefreshCw,
  Database
} from 'lucide-vue-next'

const props = defineProps({
  products: {
    type: Array,
    required: true
  },
  highlightedIds: {
    type: Array,
    default: () => []
  },
  cartCount: {
    type: Number,
    default: 0
  },
  wishlistIds: {
    type: Array,
    default: () => []
  },
  isLoading: {
    type: Boolean,
    default: false
  },
  isDatabaseConnected: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'add-to-cart', 
  'view-details', 
  'toggle-wishlist', 
  'open-cart',
  'clear-ai-filter',
  'refresh-products'
])

const searchQuery = ref('')
const selectedCategory = ref('Tất cả')
const sortBy = ref('featured')
const showOnlyAiResults = ref(false)

// Trích xuất danh mục tự động từ dữ liệu thật trả về từ Web API
const categories = computed(() => {
  const cats = ['Tất cả']
  props.products.forEach(p => {
    if (p.category && !cats.includes(p.category)) {
      cats.push(p.category)
    }
  })
  return cats
})

const filteredProducts = computed(() => {
  let list = [...props.products]

  // Filter only AI results if toggled
  if (showOnlyAiResults.value && props.highlightedIds.length > 0) {
    list = list.filter(p => props.highlightedIds.includes(p.id))
  }

  // Filter by category
  if (selectedCategory.value !== 'Tất cả') {
    list = list.filter(p => (p.category || '').toLowerCase() === selectedCategory.value.toLowerCase())
  }

  // Filter by text search
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(p => 
      (p.name || '').toLowerCase().includes(q) || 
      (p.brand || '').toLowerCase().includes(q) || 
      (p.category || '').toLowerCase().includes(q) ||
      (p.tags || []).some(t => t.toLowerCase().includes(q))
    )
  }

  // Sorting
  if (sortBy.value === 'price-asc') {
    list.sort((a, b) => (a.finalPrice || a.originalPrice || 0) - (b.finalPrice || b.originalPrice || 0))
  } else if (sortBy.value === 'price-desc') {
    list.sort((a, b) => (b.finalPrice || b.originalPrice || 0) - (a.finalPrice || a.originalPrice || 0))
  } else if (sortBy.value === 'discount') {
    list.sort((a, b) => (b.discountPercent || 0) - (a.discountPercent || 0))
  } else if (sortBy.value === 'rating') {
    list.sort((a, b) => (b.rating || 0) - (a.rating || 0))
  }

  // Place AI-highlighted products first if any (and sort by matchScore descending)
  if (props.highlightedIds.length > 0 && !showOnlyAiResults.value) {
    list.sort((a, b) => {
      const aHigh = props.highlightedIds.includes(a.id)
      const bHigh = props.highlightedIds.includes(b.id)
      if (aHigh && !bHigh) return -1
      if (!aHigh && bHigh) return 1
      if (aHigh && bHigh) {
        return (b.matchScore || 0) - (a.matchScore || 0)
      }
      return 0
    })
  }

  return list
})

const resetFilters = () => {
  searchQuery.value = ''
  selectedCategory.value = 'Tất cả'
  sortBy.value = 'featured'
  showOnlyAiResults.value = false
  emit('clear-ai-filter')
}
</script>

<template>
  <div class="flex flex-col h-full bg-zinc-50/60 overflow-hidden">
    <!-- Top Header Bar -->
    <header class="bg-white border-b border-zinc-200 px-6 py-3.5 shrink-0 z-10">
      <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <!-- Search Controls -->
        <div class="flex items-center gap-3 flex-1 max-w-md">
          <div class="relative w-full">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
            <input 
              v-model="searchQuery"
              type="text"
              placeholder="Tìm kiếm sản phẩm theo tên, thương hiệu, tag..."
              class="w-full pl-9 pr-4 py-2 text-xs rounded-lg border border-zinc-200 bg-zinc-50 text-zinc-900 focus:outline-none focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 focus:bg-white transition-all"
            />
            <button 
              v-if="searchQuery" 
              @click="searchQuery = ''"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-pink-600 text-xs cursor-pointer"
            >
              ✕
            </button>
          </div>
        </div>

        <!-- Sort, Reload & Cart Action -->
        <div class="flex items-center gap-2.5 justify-end">
          <!-- Refresh Button -->
          <button 
            @click="emit('refresh-products')"
            :disabled="isLoading"
            class="p-2 rounded-lg border border-zinc-200 bg-white hover:bg-zinc-50 hover:text-pink-600 text-zinc-600 transition-colors cursor-pointer"
            title="Tải lại dữ liệu từ API"
          >
            <RefreshCw class="w-4 h-4" :class="{ 'animate-spin text-pink-600': isLoading }" />
          </button>

          <!-- Sort Dropdown -->
          <div class="flex items-center gap-1.5 text-xs text-zinc-600">
            <ArrowUpDown class="w-3.5 h-3.5 text-zinc-400 hidden sm:block" />
            <select 
              v-model="sortBy"
              class="px-2.5 py-2 text-xs rounded-lg border border-zinc-200 bg-white text-zinc-800 font-medium focus:outline-none focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 cursor-pointer"
            >
              <option value="featured">Sắp xếp: Nổi bật</option>
              <option value="price-asc">Giá: Thấp đến cao</option>
              <option value="price-desc">Giá: Cao đến thấp</option>
              <option value="discount">Giảm giá nhiều nhất</option>
              <option value="rating">Đánh giá cao nhất</option>
            </select>
          </div>

          <!-- Cart Button in Pink/Black style -->
          <button 
            @click="emit('open-cart')"
            class="relative px-4 py-2 rounded-lg bg-zinc-950 hover:bg-gradient-to-r hover:from-pink-600 hover:to-rose-600 active:scale-98 text-white font-bold text-xs shadow-sm flex items-center gap-2 transition-all cursor-pointer border border-zinc-800 hover:border-transparent hover:shadow-md hover:shadow-pink-500/25"
          >
            <ShoppingBag class="w-4 h-4 text-pink-400 group-hover:text-white" />
            <span class="hidden sm:inline">Giỏ hàng</span>
            <span 
              v-if="cartCount > 0" 
              class="px-1.5 py-0.2 bg-gradient-to-r from-pink-500 to-rose-500 text-white rounded-full text-[11px] font-black shadow-xs"
            >
              {{ cartCount }}
            </span>
          </button>
        </div>
      </div>

      <!-- Dynamic Category Filter Pills (Auto-extracted from API) -->
      <div v-if="categories.length > 1" class="flex items-center gap-1.5 overflow-x-auto no-scrollbar pt-3 mt-2 border-t border-zinc-100">
        <button 
          v-for="cat in categories" 
          :key="cat"
          @click="selectedCategory = cat"
          class="px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap transition-all cursor-pointer"
          :class="[
            selectedCategory === cat 
              ? 'bg-zinc-950 text-pink-400 ring-1 ring-pink-500/50 shadow-xs' 
              : 'bg-zinc-100 text-zinc-600 hover:bg-pink-50 hover:text-pink-600 hover:border-pink-200'
          ]"
        >
          {{ cat }}
        </button>
      </div>
    </header>

    <!-- Filter Notification Banner in Pink Theme -->
    <div 
      v-if="highlightedIds.length > 0" 
      class="px-6 py-2 bg-pink-50/90 border-b border-pink-200 flex flex-wrap items-center justify-between gap-2 text-xs text-pink-900 shrink-0"
    >
      <div class="flex items-center gap-1.5 font-medium">
        <Sparkles class="w-3.5 h-3.5 text-pink-600" />
        <span>Trợ lý AI đã tìm thấy <strong class="text-pink-700 font-bold">{{ highlightedIds.length }} sản phẩm phù hợp</strong> qua Vector Search.</span>
      </div>
      <div class="flex items-center gap-3">
        <button 
          @click="showOnlyAiResults = !showOnlyAiResults"
          class="px-2.5 py-0.5 rounded-full font-bold text-[11px] transition-all cursor-pointer border"
          :class="showOnlyAiResults ? 'bg-pink-600 text-white border-pink-600 shadow-xs' : 'bg-white text-pink-700 border-pink-300 hover:bg-pink-100'"
        >
          {{ showOnlyAiResults ? '✓ Đang lọc: Chỉ kết quả AI' : 'Chỉ xem kết quả AI' }}
        </button>
        <button 
          @click="emit('clear-ai-filter')"
          class="text-pink-600 hover:text-pink-800 font-bold hover:underline flex items-center gap-1 text-[11px] cursor-pointer"
        >
          <RotateCcw class="w-3 h-3" />
          <span>Bỏ đánh dấu</span>
        </button>
      </div>
    </div>

    <!-- Product Grid Display Section -->
    <main class="flex-1 overflow-y-auto p-6">
      <!-- Loading Skeleton State -->
      <div v-if="isLoading" class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
        <div 
          v-for="i in 6" 
          :key="i"
          class="bg-white rounded-xl border border-zinc-200 p-4 space-y-3 animate-pulse"
        >
          <div class="w-full aspect-[4/3] bg-zinc-200 rounded-lg"></div>
          <div class="h-4 bg-zinc-200 rounded w-3/4"></div>
          <div class="h-3 bg-zinc-200 rounded w-1/2"></div>
          <div class="h-8 bg-zinc-200 rounded mt-4"></div>
        </div>
      </div>

      <!-- Empty State: Waiting for Backend API / No products -->
      <div 
        v-else-if="filteredProducts.length === 0" 
        class="h-full flex flex-col items-center justify-center text-center py-16"
      >
        <div class="w-16 h-16 bg-pink-50 border border-pink-200 rounded-2xl flex items-center justify-center text-pink-500 mb-4 shadow-sm">
          <Database class="w-8 h-8" />
        </div>
        <h3 class="font-bold text-zinc-900 text-lg mb-1">
          {{ products.length === 0 ? 'Đang chờ dữ liệu từ API Backend...' : 'Không tìm thấy sản phẩm' }}
        </h3>
        <p class="text-xs text-zinc-500 max-w-sm mb-4 leading-relaxed">
          {{ products.length === 0 
            ? 'Giao diện đã sẵn sàng kết nối API `http://localhost:8000/api/products`. Hãy khởi chạy FastAPI backend để hiển thị dữ liệu sản phẩm thật từ CSDL.' 
            : 'Không có sản phẩm nào khớp với bộ lọc hiện tại. Thử tìm kiếm từ khóa khác nhé!' 
          }}
        </p>
        <div class="flex items-center gap-2">
          <button 
            v-if="products.length === 0"
            @click="emit('refresh-products')"
            class="px-4 py-2 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 text-white rounded-lg text-xs font-bold transition-all shadow-md shadow-pink-500/25 flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw class="w-3.5 h-3.5" />
            <span>Tải lại từ API</span>
          </button>
          <button 
            v-else
            @click="resetFilters"
            class="px-4 py-2 bg-zinc-950 hover:bg-pink-600 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer"
          >
            Đặt lại tất cả bộ lọc
          </button>
        </div>
      </div>

      <!-- Responsive Product Cards Grid (grid-cols-2 or grid-cols-3) -->
      <div 
        v-else 
        class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5"
      >
        <ProductCard 
          v-for="product in filteredProducts" 
          :key="product.id"
          :product="product"
          :is-highlighted="highlightedIds.includes(product.id)"
          :is-wishlisted="wishlistIds.includes(product.id)"
          @add-to-cart="(p) => emit('add-to-cart', p)"
          @view-details="(p) => emit('view-details', p)"
          @toggle-wishlist="(p) => emit('toggle-wishlist', p)"
        />
      </div>
    </main>
  </div>
</template>
