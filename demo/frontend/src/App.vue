<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import BrandLogo from './components/BrandLogo.vue'
import ChatInterface from './components/ChatInterface.vue'
import ProductGrid from './components/ProductGrid.vue'
import ProductDetailModal from './components/ProductDetailModal.vue'
import CartDrawer from './components/CartDrawer.vue'
import ToastNotification from './components/ToastNotification.vue'
import { availableModels, sampleSuggestions } from './data/products'
import { sendChatMessage } from './services/aiService'

// Products Catalog State (Khởi tạo mảng rỗng - lấy 100% dữ liệu từ Web/API Backend)
const products = ref([])
const highlightedProductIds = ref([])
const wishlistIds = ref([])
const isDatabaseConnected = ref(false)
const isLoadingProducts = ref(false)

// AI Models State
const models = ref([...availableModels])
const selectedModelId = ref('auto-cot')

// Chat Interface State
const isGenerating = ref(false)
const messages = ref([
  {
    sender: 'ai',
    text: "Xin chào! Tôi là **Trợ Lý Mua Sắm AI**. Bạn đang tìm kiếm sản phẩm hoặc phong cách thời trang nào hôm nay? Hãy nhập nhu cầu hoặc sở thích của bạn để tôi gợi ý những sản phẩm phù hợp nhất nhé!",
    timestamp: '10:00'
  }
])

// Cart State
const isCartOpen = ref(false)
const cartItems = ref([])

// Modal State
const isDetailModalOpen = ref(false)
const selectedProduct = ref(null)

// Toast Notifications State
const toasts = ref([])
let toastIdCounter = 0

const addToast = (message, type = 'success') => {
  const id = ++toastIdCounter
  toasts.value.push({ id, message, type })
  setTimeout(() => {
    removeToast(id)
  }, 3500)
}

const removeToast = (id) => {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

// Hàm chuẩn hóa dữ liệu nhận từ Web API / CSDL MySQL
const normalizeProduct = (p, index) => {
  const originalPrice = Number(p.original_price ?? p.originalPrice ?? 29.99)
  const discountPercent = Number(p.discount_percent ?? p.discountPercent ?? 0)
  const finalPrice = p.final_price ?? p.finalPrice ?? (discountPercent > 0 ? (originalPrice * (1 - discountPercent / 100)) : originalPrice)

  const productType = p.product_type || p.category || "Thời trang"
  const productGroup = p.product_group || p.productGroup || "Thời trang H&M"
  const department = p.department || p.brand || "H&M Collection"
  const genderGroup = p.gender_group || p.genderGroup || "H&M Collection"
  const pattern = p.pattern || "Solid"
  const detailDesc = p.detail_desc || p.description || `Sản phẩm ${p.name || ''} chính hãng H&M.`
  const color = p.color || "Tiêu chuẩn"
  const size = p.size || "M"
  const stockQuantity = p.stock_quantity !== undefined ? Number(p.stock_quantity) : 25
  const variantId = p.variant_id || `${p.id || index}-${color}-${size}`
  const articleId = p.article_id || p.articleId || String(p.id)
  
  const availableColors = p.available_colors && p.available_colors.length > 0 ? p.available_colors : [color]
  const availableSizes = p.available_sizes && p.available_sizes.length > 0 ? p.available_sizes : [size]
  const colorImages = p.color_images || p.colorImages || {}
  const colorDetails = p.color_details || p.colorDetails || {}

  const placeholderImages = [
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=600&auto=format&fit=crop&q=80"
  ]

  return {
    id: String(p.id),
    name: p.name || `Sản phẩm #${p.id}`,
    brand: department,
    category: productType,
    productType: productType,
    productGroup: productGroup,
    department: department,
    genderGroup: genderGroup,
    pattern: pattern,
    detailDesc: detailDesc,
    description: detailDesc,
    color: color,
    size: size,
    stockQuantity: stockQuantity,
    variantId: variantId,
    articleId: String(articleId),
    availableColors: availableColors,
    availableSizes: availableSizes,
    colorImages: colorImages,
    colorDetails: colorDetails,
    originalPrice: originalPrice,
    discountPercent: discountPercent,
    finalPrice: finalPrice,
    rating: p.rating ? Number(p.rating) : 4.8,
    reviewsCount: p.reviews_count ? Number(p.reviews_count) : 89,
    image: p.image || p.image_url || (colorImages[color] || placeholderImages[index % placeholderImages.length]),
    inStock: stockQuantity > 0,
    tags: [department, productType, color, `Size ${size}`],
    specs: {
      "Mã SP (Product ID)": String(p.id),
      "Mã SKU màu (Article ID)": String(articleId),
      "Loại sản phẩm (Product Type)": productType,
      "Nhóm ngành hàng (Group)": productGroup,
      "Phân khúc (Gender)": genderGroup,
      "Phong cách (Department)": department,
      "Họa tiết (Pattern)": pattern,
      "Màu sắc ban đầu": color,
      "Kích cỡ": size,
      "Tồn kho CSDL": `${stockQuantity} sản phẩm`
    }
  }
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080'

// Gọi API lấy dữ liệu sản phẩm thật từ Backend ngay khi mở trang
const fetchProductsFromDatabase = async () => {
  isLoadingProducts.value = true
  try {
    const response = await axios.get(`${API_BASE_URL}/api/products`, { timeout: 10000 })
    if (Array.isArray(response.data) && response.data.length > 0) {
      products.value = response.data.map((p, idx) => normalizeProduct(p, idx))
      isDatabaseConnected.value = true
      addToast(`Đã tải thành công ${response.data.length} sản phẩm từ Web API!`, 'success')
    } else {
      products.value = []
      isDatabaseConnected.value = true
      addToast("API hoạt động nhưng CSDL chưa có bản ghi sản phẩm nào.", "info")
    }
  } catch (error) {
    products.value = []
    isDatabaseConnected.value = false
    console.warn(`Chưa kết nối được tới ${API_BASE_URL}/api/products:`, error.message)
  } finally {
    isLoadingProducts.value = false
  }
}

// Gọi API lấy danh sách mô hình AI đã kết nối
const fetchModelsFromApi = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/models`, { timeout: 5000 })
    if (Array.isArray(response.data) && response.data.length > 0) {
      // Hợp nhất dữ liệu API với availableModels để luôn đảm bảo có cả 2 mô hình
      const merged = [...availableModels]
      response.data.forEach(apiModel => {
        const idx = merged.findIndex(m => m.id === apiModel.id)
        if (idx >= 0) {
          merged[idx] = { ...merged[idx], ...apiModel }
        } else {
          merged.push(apiModel)
        }
      })
      models.value = merged
    }
  } catch (e) {
    console.warn("Dùng danh sách models mặc định:", e.message)
    models.value = [...availableModels]
  }
}

onMounted(() => {
  fetchProductsFromDatabase()
  fetchModelsFromApi()
})

// Handlers for Chat
const handleSendMessage = async (queryText) => {
  if (!queryText.trim() || isGenerating.value) return

  const now = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })

  // 1. Thêm tin nhắn người dùng
  messages.value.push({
    sender: 'user',
    text: queryText,
    timestamp: now
  })

  isGenerating.value = true

  try {
    const result = await sendChatMessage(queryText, selectedModelId.value, products.value, true)
    
    // 2. Thêm phản hồi của AI kèm dữ liệu sản phẩm gợi ý
    messages.value.push({
      sender: 'ai',
      text: result.aiResponse,
      sqlGenerated: result.sqlGenerated,
      searchMethod: result.searchMethod,
      products: result.productsData || [],
      timestamp: result.timestamp
    })

    // 3. Đổ dữ liệu từ mảng products_data ra giao diện lưới sản phẩm (Product Grid)
    if (result.productsData && result.productsData.length > 0) {
      const matchedIds = result.productsData.map(p => p.id)
      highlightedProductIds.value = matchedIds

      // Đưa toàn bộ sản phẩm do AI gợi ý lên đầu danh sách theo đúng thứ tự điểm tương quan
      const matchedMap = new Map(result.productsData.map(p => [String(p.id), p]))
      const nonMatched = products.value.filter(p => !matchedMap.has(String(p.id)))
      
      // Hợp nhất: Toàn bộ danh sách do AI tìm thấy (theo đúng thứ tự điểm tương quan) đặt ở đầu
      products.value = [...result.productsData, ...nonMatched]
      isDatabaseConnected.value = true
      addToast(`🎯 AI Auto-CoT đã tìm thấy ${result.productsData.length} sản phẩm phù hợp & liên quan!`, 'success')
    } else if (result.matchedProductIds && result.matchedProductIds.length > 0) {
      highlightedProductIds.value = result.matchedProductIds
      addToast(`Đã tìm thấy ${result.matchedProductIds.length} sản phẩm phù hợp!`, 'info')
    }
  } catch (error) {
    messages.value.push({
      sender: 'ai',
      text: "Đã xảy ra sự cố khi kết nối tới máy chủ AI. Xin vui lòng thử lại sau giây lát!",
      timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    })
  } finally {
    isGenerating.value = false
  }
}

const handleClearChat = () => {
  messages.value = [
    {
      sender: 'ai',
      text: "Cuộc trò chuyện đã được làm mới. Tôi có thể giúp gì cho bạn trong việc tìm kiếm sản phẩm hôm nay?",
      timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    }
  ]
  highlightedProductIds.value = []
  addToast("Đã đặt lại cuộc trò chuyện", "info")
}

const handleApplyPrompt = (prompt) => {
  handleSendMessage(prompt)
}

// Handlers for Products & Cart
const handleAddToCart = (product, quantity = 1) => {
  const existingIndex = cartItems.value.findIndex(item => item.product.id === product.id)
  if (existingIndex > -1) {
    cartItems.value[existingIndex].quantity += quantity
  } else {
    cartItems.value.push({
      product: product,
      quantity: quantity
    })
  }
  addToast(`Đã thêm "${product.name}" vào giỏ hàng!`)
}

const handleUpdateQuantity = (productId, newQuantity) => {
  if (newQuantity <= 0) {
    handleRemoveFromCart(productId)
    return
  }
  const item = cartItems.value.find(item => item.product.id === productId)
  if (item) {
    item.quantity = newQuantity
  }
}

const handleRemoveFromCart = (productId) => {
  cartItems.value = cartItems.value.filter(item => item.product.id !== productId)
  addToast("Đã xóa sản phẩm khỏi giỏ hàng", "info")
}

const handleViewDetails = (product) => {
  selectedProduct.value = product
  isDetailModalOpen.value = true
}

const handleToggleWishlist = (product) => {
  const idx = wishlistIds.value.indexOf(product.id)
  if (idx > -1) {
    wishlistIds.value.splice(idx, 1)
    addToast(`Đã bỏ "${product.name}" khỏi danh sách yêu thích`, "info")
  } else {
    wishlistIds.value.push(product.id)
    addToast(`Đã lưu "${product.name}" vào danh sách yêu thích!`)
  }
}

const handleCheckout = () => {
  isCartOpen.value = false
  addToast("Mô phỏng đặt hàng và thanh toán thành công! 🎉", "success")
  cartItems.value = []
}

const handleClearAiFilter = () => {
  highlightedProductIds.value = []
}
</script>

<template>
  <div class="h-screen w-screen overflow-hidden flex flex-col bg-zinc-950 antialiased font-sans">
    <!-- Top Global App Bar in Pink & Black Brand Style -->
    <div class="h-14 bg-zinc-950 text-white px-4 sm:px-6 flex items-center justify-between shrink-0 border-b border-zinc-800/90 z-20">
      <div class="flex items-center gap-3">
        <!-- Logo with white badge container -->
        <BrandLogo size="w-9 h-9" :show-badge="true" />
        <div class="flex items-baseline gap-1.5">
          <span class="font-black text-lg tracking-tight text-white">Smart<span class="text-pink-500">Store</span></span>
          <span class="hidden sm:inline text-xs text-pink-400 font-medium">| AI Shopping Assistant</span>
        </div>
      </div>

      <div class="flex items-center gap-4 text-xs text-zinc-300">
        <!-- Live API Status Indicator -->
        <div class="hidden md:flex items-center gap-2">
          <span 
            class="inline-block w-2 h-2 rounded-full shadow-xs"
            :class="isDatabaseConnected ? 'bg-emerald-500 shadow-emerald-500 animate-pulse' : 'bg-amber-500'"
          ></span>
          <span>
            {{ isDatabaseConnected ? 'API Web/MySQL Connected' : 'Đang kết nối API Backend' }} ({{ products.length }} sản phẩm)
          </span>
        </div>

        <span class="text-zinc-700 hidden md:inline">•</span>

        <!-- AI status pill -->
        <div class="flex items-center gap-1.5 text-pink-400 font-bold bg-pink-500/10 px-2.5 py-1 rounded-full border border-pink-500/20">
          <span>⚡ Gợi ý AI Trực Tiếp</span>
        </div>
      </div>
    </div>

    <!-- Main Two-Column Layout Container -->
    <!-- Desktop: Left 35%, Right 65%. Mobile: Stacked column -->
    <div class="flex-1 flex flex-col lg:flex-row overflow-hidden w-full bg-zinc-100">
      <!-- LEFT COLUMN: 35% Width (Chat Interface với Model Selector) -->
      <section class="w-full lg:w-[35%] xl:w-[35%] h-1/2 lg:h-full flex flex-col shrink-0">
        <ChatInterface 
          :messages="messages"
          :is-generating="isGenerating"
          :suggestions="sampleSuggestions"
          :models="models"
          v-model:selected-model-id="selectedModelId"
          @send-message="handleSendMessage"
          @clear-chat="handleClearChat"
          @apply-prompt="handleApplyPrompt"
          @view-details="handleViewDetails"
          @add-to-cart="handleAddToCart"
        />
      </section>

      <!-- RIGHT COLUMN: 65% Width (Product Grid Display Lấy dữ liệu động từ API) -->
      <section class="w-full lg:w-[65%] xl:w-[65%] h-1/2 lg:h-full flex flex-col flex-1 overflow-hidden">
        <ProductGrid 
          :products="products"
          :highlighted-ids="highlightedProductIds"
          :cart-count="cartItems.reduce((acc, item) => acc + item.quantity, 0)"
          :wishlist-ids="wishlistIds"
          :is-loading="isLoadingProducts"
          :is-database-connected="isDatabaseConnected"
          @add-to-cart="handleAddToCart"
          @view-details="handleViewDetails"
          @toggle-wishlist="handleToggleWishlist"
          @open-cart="isCartOpen = true"
          @clear-ai-filter="handleClearAiFilter"
          @refresh-products="fetchProductsFromDatabase"
        />
      </section>
    </div>

    <!-- Product Detail Modal -->
    <ProductDetailModal 
      :is-open="isDetailModalOpen"
      :product="selectedProduct"
      :is-wishlisted="selectedProduct ? wishlistIds.includes(selectedProduct.id) : false"
      @close="isDetailModalOpen = false"
      @add-to-cart="handleAddToCart"
      @toggle-wishlist="handleToggleWishlist"
    />

    <!-- Shopping Cart Slide-over Drawer -->
    <CartDrawer 
      :is-open="isCartOpen"
      :cart-items="cartItems"
      @close="isCartOpen = false"
      @update-quantity="handleUpdateQuantity"
      @remove-item="handleRemoveFromCart"
      @checkout="handleCheckout"
    />

    <!-- Toast Notifications -->
    <ToastNotification 
      :toasts="toasts" 
      @close="removeToast" 
    />
  </div>
</template>
