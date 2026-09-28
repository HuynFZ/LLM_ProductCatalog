<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import ProductCard from './ProductCard.vue'
import { 
  Search, 
  ShoppingBag, 
  Sparkles, 
  RotateCcw,
  Layers,
  ArrowUpDown,
  RefreshCw,
  Database,
  ChevronLeft,
  ChevronRight,
  Menu,
  SlidersHorizontal,
  ChevronDown,
  X,
  Check,
  Grid,
  Tag
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
const currentPage = ref(1)
const pageSize = ref(56)

const highlightedSet = computed(() => new Set(props.highlightedIds))
const wishlistSet = computed(() => new Set(props.wishlistIds))

const exactMatchCount = computed(() => {
  return props.products.filter(p => highlightedSet.value.has(p.id) && (p.matchScore >= 95 || (p.matchScore > 0 && p.matchScore <= 1 && p.matchScore >= 0.95))).length
})

const relatedMatchCount = computed(() => {
  return Math.max(0, props.highlightedIds.length - exactMatchCount.value)
})

// Tự động bật chế độ xem sản phẩm AI tìm thấy và reset danh mục về 'Tất cả'
watch(() => props.highlightedIds, (newVal) => {
  if (newVal && newVal.length > 0) {
    showOnlyAiResults.value = true
    selectedCategory.value = 'Tất cả'
    currentPage.value = 1
  } else {
    showOnlyAiResults.value = false
  }
})

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

// Trạng thái mở/đóng Drawer danh mục kiểu Hamburger & tìm kiếm danh mục
const isCategoryDrawerOpen = ref(false)
const categorySearchQuery = ref('')

const openCategoryDrawer = () => {
  categorySearchQuery.value = ''
  isCategoryDrawerOpen.value = true
}

const closeCategoryDrawer = () => {
  isCategoryDrawerOpen.value = false
}

const selectCategoryAndClose = (cat) => {
  selectedCategory.value = cat
  isCategoryDrawerOpen.value = false
}

const handleKeyDown = (e) => {
  if (e.key === 'Escape' && isCategoryDrawerOpen.value) {
    closeCategoryDrawer()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

// Đếm số lượng sản phẩm chính xác theo từng danh mục
const categoryCounts = computed(() => {
  const counts = {}
  props.products.forEach(p => {
    if (p.category) {
      counts[p.category] = (counts[p.category] || 0) + 1
    }
  })
  return counts
})

// Danh sách toàn bộ danh mục sắp xếp theo số lượng sản phẩm nhiều nhất -> ít nhất
const sortedCategories = computed(() => {
  const counts = categoryCounts.value
  const list = Object.keys(counts).map(name => ({
    name,
    count: counts[name]
  }))
  list.sort((a, b) => b.count - a.count)
  return list
})

// Top 8 danh mục phổ biến nhất để hiển thị nhanh trên thanh pill
const quickCategories = computed(() => {
  return sortedCategories.value.slice(0, 8)
})

// Lọc danh mục trong Drawer khi người dùng gõ tìm kiếm danh mục
const filteredDrawerCategories = computed(() => {
  const q = categorySearchQuery.value.trim().toLowerCase()
  if (!q) return sortedCategories.value
  return sortedCategories.value.filter(c => c.name.toLowerCase().includes(q))
})

const filteredProducts = computed(() => {
  let list = [...props.products]
  const highSet = highlightedSet.value

  // Filter only AI results if toggled
  if (showOnlyAiResults.value && props.highlightedIds.length > 0) {
    list = list.filter(p => highSet.has(p.id))
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
      const aHigh = highSet.has(a.id)
      const bHigh = highSet.has(b.id)
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

// Tự động reset về trang 1 khi lọc hoặc tìm kiếm
watch([selectedCategory, searchQuery, sortBy, showOnlyAiResults, () => props.highlightedIds], () => {
  currentPage.value = 1
})

const totalPages = computed(() => Math.ceil(filteredProducts.value.length / pageSize.value) || 1)

const paginatedProducts = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredProducts.value.slice(start, start + pageSize.value)
})

const resetFilters = () => {
  searchQuery.value = ''
  selectedCategory.value = 'Tất cả'
  sortBy.value = 'featured'
  showOnlyAiResults.value = false
  currentPage.value = 1
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

      <!-- Modern Ergonomic Category Filter Bar with Hamburger Menu & Quick Pills -->
      <div v-if="sortedCategories.length > 0" class="flex items-center gap-2 pt-2.5 mt-2 border-t border-zinc-100">
        <!-- Hamburger / All Categories Drawer Trigger -->
        <button 
          @click="openCategoryDrawer"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer shrink-0 border shadow-2xs hover:shadow-xs group"
          :class="[
            selectedCategory !== 'Tất cả'
              ? 'bg-pink-50 border-pink-300 text-pink-700 hover:bg-pink-100'
              : 'bg-zinc-950 border-zinc-900 text-white hover:bg-zinc-800'
          ]"
          title="Mở toàn bộ danh mục sản phẩm (Menu Hamburger)"
        >
          <Menu class="w-3.5 h-3.5 text-pink-400 group-hover:rotate-90 transition-transform duration-200" />
          <span>Danh mục</span>
          <span 
            class="px-1.5 py-0.2 rounded-full text-[10px] font-black" 
            :class="selectedCategory !== 'Tất cả' ? 'bg-pink-200 text-pink-800' : 'bg-zinc-800 text-pink-300'"
          >
            {{ sortedCategories.length }}
          </span>
          <ChevronDown class="w-3 h-3 opacity-60 group-hover:translate-y-0.5 transition-transform" />
        </button>

        <!-- Divider -->
        <div class="h-4 w-px bg-zinc-200 shrink-0"></div>

        <!-- Scrollable Quick Pills Row -->
        <div class="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5 flex-1">
          <!-- 'Tất cả' Pill -->
          <button 
            @click="selectedCategory = 'Tất cả'"
            class="px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap transition-all cursor-pointer shrink-0"
            :class="[
              selectedCategory === 'Tất cả' 
                ? 'bg-zinc-950 text-pink-400 ring-1 ring-pink-500/50 shadow-xs' 
                : 'bg-zinc-100 text-zinc-600 hover:bg-pink-50 hover:text-pink-600'
            ]"
          >
            Tất cả ({{ products.length }})
          </button>

          <!-- Active Category pill if not in top quick list -->
          <div
            v-if="selectedCategory !== 'Tất cả' && !quickCategories.some(c => c.name === selectedCategory)"
            class="px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap transition-all shrink-0 bg-pink-600 text-white shadow-xs flex items-center gap-1.5 ring-2 ring-pink-300"
          >
            <span>🏷️ {{ selectedCategory }}</span>
            <span class="opacity-80 text-[10px]">({{ categoryCounts[selectedCategory] || 0 }})</span>
            <button 
              @click.stop="selectedCategory = 'Tất cả'"
              class="w-3.5 h-3.5 rounded-full bg-white/20 hover:bg-white/40 flex items-center justify-center text-[10px] ml-0.5 cursor-pointer"
              title="Bỏ lọc danh mục"
            >✕</button>
          </div>

          <!-- Top Quick Popular Categories -->
          <button 
            v-for="cat in quickCategories" 
            :key="cat.name"
            @click="selectedCategory = (selectedCategory === cat.name ? 'Tất cả' : cat.name)"
            class="px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition-all cursor-pointer shrink-0 flex items-center gap-1.5"
            :class="[
              selectedCategory === cat.name 
                ? 'bg-zinc-950 text-pink-400 font-bold ring-1 ring-pink-500/50 shadow-xs' 
                : 'bg-zinc-100 text-zinc-600 hover:bg-pink-50 hover:text-pink-600'
            ]"
          >
            <span>{{ cat.name }}</span>
            <span class="text-[10px] opacity-60">({{ cat.count }})</span>
            <span 
              v-if="selectedCategory === cat.name" 
              @click.stop="selectedCategory = 'Tất cả'"
              class="w-3 h-3 rounded-full bg-zinc-800 text-pink-400 hover:bg-zinc-700 flex items-center justify-center text-[9px]"
              title="Bỏ lọc"
            >✕</span>
          </button>

          <!-- "Xem thêm..." button opening drawer -->
          <button 
            @click="openCategoryDrawer"
            class="px-2.5 py-1 rounded-full text-xs font-semibold text-pink-600 bg-pink-50 hover:bg-pink-100 border border-pink-200 whitespace-nowrap transition-colors cursor-pointer shrink-0 flex items-center gap-1"
          >
            <span>+{{ Math.max(0, sortedCategories.length - quickCategories.length) }} khác...</span>
            <ChevronRight class="w-3 h-3" />
          </button>
        </div>
      </div>
    </header>

    <!-- AI Recommendations Showcase & Filter Control Bar -->
    <div 
      v-if="highlightedIds.length > 0" 
      class="px-6 py-3 bg-gradient-to-r from-pink-50 via-rose-50/70 to-purple-50/50 border-b border-pink-200/80 shrink-0"
    >
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <!-- Title & Breakdown -->
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-pink-600 to-rose-500 text-white flex items-center justify-center shadow-md shadow-pink-500/25 shrink-0">
            <Sparkles class="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="font-black text-zinc-900 text-xs sm:text-sm tracking-tight flex items-center gap-1.5">
                Đề xuất thông minh từ Trợ lý AI
              </h3>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-pink-600 text-white shadow-xs">
                {{ highlightedIds.length }} sản phẩm
              </span>
            </div>
            <div class="flex items-center gap-2 mt-0.5 text-[11px] text-zinc-600">
              <span v-if="exactMatchCount > 0" class="font-bold text-pink-700 flex items-center gap-1">
                🔥 {{ exactMatchCount }} mẫu khớp chuẩn 100%
              </span>
              <span v-if="exactMatchCount > 0 && relatedMatchCount > 0" class="text-zinc-300">•</span>
              <span v-if="relatedMatchCount > 0" class="font-semibold text-purple-700 flex items-center gap-1">
                ✨ {{ relatedMatchCount }} mẫu liên quan cùng loại
              </span>
            </div>
          </div>
        </div>

        <!-- Mode Switch: Chỉ xem kết quả AI vs Xem toàn bộ kho -->
        <div class="flex items-center gap-2 self-start sm:self-center">
          <div class="inline-flex rounded-lg bg-white/90 p-0.5 border border-pink-200 shadow-2xs">
            <button 
              @click="showOnlyAiResults = true"
              class="px-3 py-1.5 rounded-md font-bold text-xs transition-all cursor-pointer flex items-center gap-1.5"
              :class="showOnlyAiResults ? 'bg-zinc-950 text-pink-400 shadow-xs' : 'text-zinc-600 hover:text-pink-600'"
            >
              <span>🎯 Chỉ xem gợi ý AI ({{ highlightedIds.length }})</span>
            </button>
            <button 
              @click="showOnlyAiResults = false"
              class="px-3 py-1.5 rounded-md font-bold text-xs transition-all cursor-pointer flex items-center gap-1.5"
              :class="!showOnlyAiResults ? 'bg-zinc-950 text-pink-400 shadow-xs' : 'text-zinc-600 hover:text-pink-600'"
            >
              <span>🛍️ Xem cùng toàn bộ kho</span>
            </button>
          </div>

          <button 
            @click="emit('clear-ai-filter')"
            class="p-2 text-zinc-400 hover:text-pink-600 hover:bg-white rounded-lg transition-colors cursor-pointer border border-transparent hover:border-pink-200"
            title="Bỏ lọc AI và trở lại danh mục gốc"
          >
            <RotateCcw class="w-4 h-4" />
          </button>
        </div>
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
            ? 'Giao diện đã sẵn sàng kết nối API `http://localhost:8080/api/products`. Hãy khởi chạy FastAPI backend để hiển thị dữ liệu sản phẩm thật từ CSDL.' 
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
      <div v-else class="space-y-6">
        <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
          <ProductCard 
            v-for="product in paginatedProducts" 
            :key="product.id"
            :product="product"
            :is-highlighted="highlightedSet.has(product.id)"
            :is-wishlisted="wishlistSet.has(product.id)"
            @add-to-cart="(p) => emit('add-to-cart', p)"
            @view-details="(p) => emit('view-details', p)"
            @toggle-wishlist="(p) => emit('toggle-wishlist', p)"
          />
        </div>

        <!-- Pagination Controls Bar -->
        <div 
          v-if="totalPages > 1" 
          class="pt-4 pb-2 border-t border-zinc-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-zinc-600"
        >
          <div class="font-medium text-zinc-500">
            Hiển thị <strong class="text-zinc-900 font-bold">{{ (currentPage - 1) * pageSize + 1 }}-{{ Math.min(currentPage * pageSize, filteredProducts.length) }}</strong> trên <strong class="text-zinc-900 font-bold">{{ filteredProducts.length }}</strong> sản phẩm
          </div>

          <div class="flex items-center gap-1.5">
            <button 
              @click="currentPage--"
              :disabled="currentPage <= 1"
              class="px-3 py-1.5 rounded-lg border border-zinc-200 bg-white hover:bg-pink-50 hover:text-pink-600 hover:border-pink-300 disabled:opacity-40 disabled:pointer-events-none font-medium transition-all cursor-pointer flex items-center gap-1"
            >
              <ChevronLeft class="w-3.5 h-3.5" />
              <span>Trước</span>
            </button>

            <span class="px-3 py-1.5 font-bold text-pink-600 bg-pink-50 border border-pink-200 rounded-lg shadow-xs">
              Trang {{ currentPage }} / {{ totalPages }}
            </span>

            <button 
              @click="currentPage++"
              :disabled="currentPage >= totalPages"
              class="px-3 py-1.5 rounded-lg border border-zinc-200 bg-white hover:bg-pink-50 hover:text-pink-600 hover:border-pink-300 disabled:opacity-40 disabled:pointer-events-none font-medium transition-all cursor-pointer flex items-center gap-1"
            >
              <span>Sau</span>
              <ChevronRight class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- Slide-over Category Drawer (Hamburger Menu Modal) -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-250 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div 
          v-if="isCategoryDrawerOpen"
          class="fixed inset-0 z-50 overflow-hidden flex"
          role="dialog"
          aria-modal="true"
        >
          <!-- Backdrop overlay with blur -->
          <div 
            @click="closeCategoryDrawer"
            class="fixed inset-0 bg-zinc-950/60 backdrop-blur-xs transition-opacity cursor-pointer"
          ></div>

          <!-- Drawer panel slide from left -->
          <div class="relative w-full max-w-md bg-white shadow-2xl flex flex-col z-10 border-r border-zinc-200 h-full">
            <!-- Header -->
            <div class="p-4 sm:p-5 border-b border-zinc-200 flex items-center justify-between bg-zinc-950 text-white shrink-0">
              <div class="flex items-center gap-2.5">
                <div class="w-8 h-8 rounded-lg bg-pink-600 flex items-center justify-center text-white shadow-sm shadow-pink-500/50">
                  <Grid class="w-4 h-4" />
                </div>
                <div>
                  <h2 class="text-sm font-bold text-white flex items-center gap-2">
                    Danh mục thời trang
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-pink-500/20 text-pink-300 border border-pink-500/30">
                      {{ sortedCategories.length }} loại
                    </span>
                  </h2>
                  <p class="text-[11px] text-zinc-400">Chọn danh mục để lọc sản phẩm ngay</p>
                </div>
              </div>
              <button 
                @click="closeCategoryDrawer"
                class="w-8 h-8 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer"
                title="Đóng (ESC)"
              >
                <X class="w-4 h-4" />
              </button>
            </div>

            <!-- Search Category Input -->
            <div class="p-3.5 border-b border-zinc-100 bg-zinc-50 shrink-0">
              <div class="relative">
                <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                <input 
                  v-model="categorySearchQuery"
                  type="text"
                  placeholder="Tìm nhanh danh mục (ví dụ: dress, sweater, shirt...)"
                  class="w-full pl-9 pr-8 py-2 text-xs rounded-lg border border-zinc-200 bg-white text-zinc-900 focus:outline-none focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 transition-all placeholder:text-zinc-400"
                  autofocus
                />
                <button 
                  v-if="categorySearchQuery"
                  @click="categorySearchQuery = ''"
                  class="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 text-xs cursor-pointer"
                >
                  ✕
                </button>
              </div>
            </div>

            <!-- All Categories Quick Option -->
            <div class="px-4 pt-3 pb-1 shrink-0">
              <button
                @click="selectCategoryAndClose('Tất cả')"
                class="w-full p-2.5 rounded-xl border flex items-center justify-between text-xs font-bold transition-all cursor-pointer"
                :class="[
                  selectedCategory === 'Tất cả'
                    ? 'bg-zinc-950 text-pink-400 border-zinc-950 shadow-sm'
                    : 'bg-zinc-100 hover:bg-pink-50 text-zinc-700 hover:text-pink-600 border-zinc-200 hover:border-pink-200'
                ]"
              >
                <span class="flex items-center gap-2">
                  <span>🌟 Tất cả sản phẩm</span>
                </span>
                <span class="px-2 py-0.5 rounded-full text-[11px] font-bold" :class="selectedCategory === 'Tất cả' ? 'bg-zinc-800 text-pink-300' : 'bg-white text-zinc-600'">
                  {{ products.length }}
                </span>
              </button>
            </div>

            <!-- Category List Scrollable -->
            <div class="flex-1 overflow-y-auto p-4 space-y-1">
              <div class="text-[11px] font-bold uppercase tracking-wider text-zinc-400 px-1 mb-2">
                Tất cả danh mục ({{ filteredDrawerCategories.length }})
              </div>

              <div 
                v-if="filteredDrawerCategories.length === 0" 
                class="py-12 text-center text-zinc-400 text-xs"
              >
                Không có danh mục nào khớp với "{{ categorySearchQuery }}"
              </div>

              <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <button
                  v-for="cat in filteredDrawerCategories"
                  :key="cat.name"
                  @click="selectCategoryAndClose(cat.name)"
                  class="p-2.5 rounded-xl border text-left text-xs font-medium transition-all cursor-pointer flex items-center justify-between group"
                  :class="[
                    selectedCategory === cat.name
                      ? 'bg-pink-600 text-white border-pink-600 shadow-sm shadow-pink-500/25 font-bold'
                      : 'bg-white hover:bg-pink-50 text-zinc-700 hover:text-pink-700 border-zinc-200 hover:border-pink-300'
                  ]"
                >
                  <div class="flex items-center gap-1.5 truncate">
                    <Check v-if="selectedCategory === cat.name" class="w-3.5 h-3.5 shrink-0 text-white" />
                    <span class="truncate">{{ cat.name }}</span>
                  </div>
                  <span 
                    class="px-1.5 py-0.5 rounded-md text-[10px] font-bold shrink-0 ml-1 transition-colors"
                    :class="[
                      selectedCategory === cat.name
                        ? 'bg-white/20 text-white'
                        : 'bg-zinc-100 text-zinc-500 group-hover:bg-pink-100 group-hover:text-pink-600'
                    ]"
                  >
                    {{ cat.count }}
                  </span>
                </button>
              </div>
            </div>

            <!-- Footer with current active category and reset -->
            <div class="p-3.5 border-t border-zinc-200 bg-zinc-50 flex items-center justify-between text-xs shrink-0">
              <div class="text-zinc-500 text-[11px] truncate max-w-[240px]">
                Đang lọc: <strong class="text-zinc-900 font-bold">{{ selectedCategory }}</strong>
              </div>
              <button
                v-if="selectedCategory !== 'Tất cả'"
                @click="selectCategoryAndClose('Tất cả')"
                class="text-pink-600 hover:text-pink-700 font-bold text-xs cursor-pointer flex items-center gap-1"
              >
                <RotateCcw class="w-3.5 h-3.5" />
                <span>Bỏ lọc danh mục</span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
