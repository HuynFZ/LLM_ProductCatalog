<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import BrandLogo from './BrandLogo.vue'
import { 
  Bot, 
  Send, 
  Sparkles, 
  Trash2, 
  Mic, 
  MicOff, 
  RotateCcw, 
  Code2,
  ChevronUp,
  Cpu,
  ShoppingCart,
  Eye,
  ArrowRight
} from 'lucide-vue-next'

const props = defineProps({
  messages: {
    type: Array,
    required: true
  },
  isGenerating: {
    type: Boolean,
    default: false
  },
  suggestions: {
    type: Array,
    default: () => []
  },
  models: {
    type: Array,
    required: true
  },
  selectedModelId: {
    type: String,
    required: true
  }
})

const emit = defineEmits([
  'send-message', 
  'clear-chat', 
  'apply-prompt',
  'update:selectedModelId',
  'view-details',
  'add-to-cart'
])

const inputQuery = ref('')
const messagesContainer = ref(null)
const isListening = ref(false)
const showSql = ref({})

const activeModel = () => {
  return props.models.find(m => m.id === props.selectedModelId) || props.models[0] || { name: 'Que2Search + Qdrant', badge: 'Vector Search ⚡' }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

watch(() => props.messages.length, () => {
  scrollToBottom()
})

watch(() => props.isGenerating, () => {
  scrollToBottom()
})

onMounted(() => {
  scrollToBottom()
})

const handleSend = () => {
  if (!inputQuery.value.trim() || props.isGenerating) return
  emit('send-message', inputQuery.value.trim())
  inputQuery.value = ''
}

const handleKeyDown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

const handleSuggestionClick = (prompt) => {
  emit('apply-prompt', prompt)
}

const toggleVoiceSimulation = () => {
  if (isListening.value) {
    isListening.value = false
  } else {
    isListening.value = true
    setTimeout(() => {
      inputQuery.value = "Tìm giúp tôi tai nghe chống ồn dưới 8 triệu có pin lâu"
      isListening.value = false
    }, 1200)
  }
}

const formatMessageText = (text) => {
  if (!text) return ''
  let formatted = text
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-zinc-900">$1</strong>')
    .replace(/\*(.*?)\*/g, '<span class="text-xs text-pink-600 font-semibold">$1</span>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')
  return formatted
}

const formatCurrency = (val) => {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val || 0)
}

const toggleSqlView = (index) => {
  showSql.value[index] = !showSql.value[index]
}
</script>

<template>
  <div class="flex flex-col h-full bg-white border-r border-zinc-200 relative">
    <!-- 1. Fixed Header: "AI Shopping Assistant" (Tiếng Việt) -->
    <header class="px-4 py-3 border-b border-zinc-200 bg-white flex items-center justify-between shrink-0 z-20">
      <div class="flex items-center gap-3">
        <BrandLogo size="w-9 h-9" :show-badge="true" />
        <div>
          <h1 class="font-bold text-zinc-900 text-base leading-tight flex items-center gap-1.5">
            Trợ Lý Mua Sắm AI
            <span class="inline-flex items-center px-1.5 py-0.2 text-[10px] font-bold bg-pink-50 text-pink-600 rounded-full border border-pink-200">
              AI Copilot
            </span>
          </h1>
          <p class="text-[11px] text-pink-600 font-medium flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-pink-500 animate-pulse"></span>
            Hồng Đen Edition • Trực tuyến
          </p>
        </div>
      </div>

      <div class="flex items-center gap-1">
        <button 
          @click="emit('clear-chat')"
          class="p-2 text-zinc-400 hover:text-pink-600 hover:bg-pink-50 rounded-lg transition-colors cursor-pointer"
          title="Làm mới cuộc trò chuyện"
        >
          <RotateCcw class="w-4 h-4" />
        </button>
      </div>
    </header>

    <!-- 2. AI Model Status Bar (Static - Que2Search + Qdrant) -->
    <div class="px-4 py-2 bg-zinc-50 border-b border-zinc-200 shrink-0 z-10">
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-1.5 text-xs text-zinc-600 font-medium">
          <Cpu class="w-3.5 h-3.5 text-pink-600" />
          <span>Mô hình AI:</span>
        </div>

        <!-- Static Model Badge (No Dropdown) -->
        <div class="flex items-center gap-2 px-3 py-1 rounded-lg border border-pink-200/80 bg-white text-xs font-semibold text-zinc-800 shadow-2xs">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>Que2Search + Qdrant</span>
          <span class="text-[10px] text-pink-700 bg-pink-50 px-1.5 py-0.2 rounded font-bold border border-pink-200">
            Vector Search ⚡
          </span>
        </div>
      </div>
    </div>

    <!-- Quick Suggestion Chips Carousel -->
    <div class="px-4 py-2 bg-zinc-50/70 border-b border-zinc-100 flex items-center gap-1.5 overflow-x-auto no-scrollbar shrink-0">
      <Sparkles class="w-3.5 h-3.5 text-pink-600 shrink-0 mr-1" />
      <button 
        v-for="(suggestion, idx) in suggestions" 
        :key="idx"
        @click="handleSuggestionClick(suggestion)"
        class="whitespace-nowrap px-2.5 py-1 rounded-full text-xs font-medium bg-white text-zinc-700 hover:text-pink-600 border border-zinc-200 hover:border-pink-300 hover:bg-pink-50/50 shadow-2xs transition-all cursor-pointer"
      >
        {{ suggestion }}
      </button>
    </div>

    <!-- 3. Scrollable Chat History Section -->
    <div 
      ref="messagesContainer"
      class="flex-1 overflow-y-auto p-4 space-y-4 bg-zinc-50/40"
    >
      <div 
        v-for="(msg, index) in messages" 
        :key="index"
        class="flex flex-col"
      >
        <!-- USER MESSAGE: Aligned right, Pink/Rose gradient background, white text -->
        <div 
          v-if="msg.sender === 'user'" 
          class="flex justify-end items-end gap-2 group"
        >
          <div class="flex flex-col items-end max-w-[85%]">
            <div class="px-4 py-2.5 rounded-2xl rounded-tr-xs bg-gradient-to-r from-pink-600 to-rose-600 text-white shadow-sm shadow-pink-500/20 text-sm leading-relaxed font-medium">
              {{ msg.text }}
            </div>
            <span class="text-[10px] text-zinc-400 mt-1 px-1 font-medium">
              {{ msg.timestamp || 'Vừa xong' }}
            </span>
          </div>
        </div>

        <!-- AI MESSAGE: Aligned left, gray/black tech style, dark text -->
        <div 
          v-else 
          class="flex items-start gap-2.5 max-w-[90%] group"
        >
          <!-- Bot Avatar in Black with Pink Border -->
          <div class="w-7 h-7 rounded-lg bg-zinc-950 border border-pink-500/40 text-pink-400 flex items-center justify-center shrink-0 shadow-xs shadow-pink-500/10 mt-0.5">
            <Bot class="w-4 h-4" />
          </div>

          <div class="flex flex-col items-start w-full">
            <div class="px-4 py-3 rounded-2xl rounded-tl-xs bg-white border border-zinc-200/90 text-zinc-800 shadow-2xs text-sm leading-relaxed">
              <!-- Render formatted HTML content with Pink accents -->
              <div v-html="formatMessageText(msg.text)" class="space-y-1 text-zinc-800"></div>

              <!-- Product Cards Preview inside Chat Bubble -->
              <div v-if="msg.products && msg.products.length > 0" class="mt-3 pt-3 border-t border-zinc-100 space-y-2">
                <div class="flex items-center justify-between text-[11px] font-bold text-zinc-500">
                  <span class="flex items-center gap-1 text-pink-600">
                    <Sparkles class="w-3 h-3" />
                    <span>Gợi ý trực tiếp ({{ msg.products.length }})</span>
                  </span>
                  <span v-if="msg.searchMethod" class="text-[10px] text-zinc-400 font-normal">
                    {{ msg.searchMethod.includes('Vector') ? '⚡ Qdrant Vector Search' : '🔍 Tìm kiếm từ khóa' }}
                  </span>
                </div>

                <div class="space-y-2 max-h-64 overflow-y-auto pr-1">
                  <div 
                    v-for="prod in msg.products.slice(0, 4)" 
                    :key="prod.id"
                    class="p-2 rounded-xl bg-zinc-50 hover:bg-pink-50/50 border border-zinc-200/80 hover:border-pink-300 transition-all flex items-center gap-2.5 group/item"
                  >
                    <img 
                      :src="prod.image" 
                      :alt="prod.name"
                      class="w-12 h-12 rounded-lg object-cover bg-white shrink-0 border border-zinc-100"
                      @error="(e) => e.target.src = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80'"
                    />
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-1 mb-0.5">
                        <span v-if="prod.matchScore" class="text-[10px] font-black text-pink-600 bg-pink-100 px-1.5 py-0.2 rounded shrink-0">
                          🎯 {{ Math.round(prod.matchScore * 100) }}%
                        </span>
                        <h4 
                          @click="emit('view-details', prod)"
                          class="text-xs font-bold text-zinc-900 truncate group-hover/item:text-pink-600 cursor-pointer"
                        >
                          {{ prod.name }}
                        </h4>
                      </div>
                      <div class="flex items-center justify-between gap-1">
                        <span class="text-xs font-black text-pink-600">
                          {{ formatCurrency(prod.finalPrice || prod.originalPrice) }}
                        </span>
                        <div class="flex items-center gap-1">
                          <button 
                            @click="emit('view-details', prod)"
                            class="p-1 text-zinc-400 hover:text-pink-600 hover:bg-white rounded transition-colors cursor-pointer"
                            title="Xem chi tiết"
                          >
                            <Eye class="w-3.5 h-3.5" />
                          </button>
                          <button 
                            @click="emit('add-to-cart', prod)"
                            class="px-2 py-0.5 rounded bg-zinc-950 hover:bg-pink-600 text-white text-[10px] font-bold transition-colors cursor-pointer flex items-center gap-1"
                            title="Thêm vào giỏ"
                          >
                            <ShoppingCart class="w-3 h-3" />
                            <span>Mua</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- SQL Query Inspection Pill if available -->
              <div v-if="msg.sqlGenerated" class="mt-3 pt-2.5 border-t border-zinc-100">
                <button 
                  @click="toggleSqlView(index)"
                  class="flex items-center gap-1 text-[11px] font-semibold text-pink-600 hover:text-pink-700 transition-colors cursor-pointer"
                >
                  <Code2 class="w-3.5 h-3.5" />
                  <span>{{ showSql[index] ? 'Ẩn câu lệnh SQL' : 'Xem câu lệnh SQL đã sinh' }}</span>
                  <component :is="showSql[index] ? ChevronUp : ChevronDown" class="w-3 h-3" />
                </button>
                <div 
                  v-if="showSql[index]" 
                  class="mt-1.5 p-2.5 rounded-lg bg-zinc-950 text-pink-400 border border-zinc-800 font-mono text-[11px] overflow-x-auto select-all leading-relaxed"
                >
                  {{ msg.sqlGenerated }}
                </div>
              </div>
            </div>

            <!-- Timestamp -->
            <span class="text-[10px] text-zinc-400 mt-1 px-1 font-medium">
              {{ msg.timestamp || 'Vừa xong' }}
            </span>
          </div>
        </div>
      </div>

      <!-- AI Generating / Thinking indicator in Pink -->
      <div v-if="isGenerating" class="flex items-start gap-2.5 max-w-[85%]">
        <div class="w-7 h-7 rounded-lg bg-zinc-950 border border-pink-500/40 text-pink-400 flex items-center justify-center shrink-0 shadow-xs">
          <Bot class="w-4 h-4 animate-bounce" />
        </div>
        <div class="px-4 py-3 rounded-2xl rounded-tl-xs bg-white border border-zinc-200/90 text-zinc-500 shadow-2xs flex items-center gap-1.5">
          <span class="text-xs font-medium mr-1 text-zinc-700">
            {{ activeModel().name }} đang xử lý
          </span>
          <span class="w-1.5 h-1.5 rounded-full bg-pink-600 animate-bounce [animation-delay:-0.3s]"></span>
          <span class="w-1.5 h-1.5 rounded-full bg-pink-600 animate-bounce [animation-delay:-0.15s]"></span>
          <span class="w-1.5 h-1.5 rounded-full bg-pink-600 animate-bounce"></span>
        </div>
      </div>
    </div>

    <!-- 4. Fixed Bottom Input Area in Pink & Black Theme -->
    <div class="p-3.5 bg-white border-t border-zinc-200 shrink-0 z-10">
      <div class="flex items-center gap-2">
        <div class="relative flex-1 flex items-center">
          <input 
            v-model="inputQuery"
            @keydown="handleKeyDown"
            type="text"
            placeholder="Nhập sản phẩm hoặc nhu cầu bạn muốn mua..."
            class="w-full pl-3.5 pr-9 py-2.5 rounded-lg border border-zinc-200 bg-zinc-50 text-zinc-900 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 focus:bg-white transition-all shadow-2xs"
            :disabled="isGenerating"
          />
          <button 
            @click="toggleVoiceSimulation"
            type="button"
            class="absolute right-2.5 p-1 text-zinc-400 hover:text-pink-600 transition-colors cursor-pointer"
            :class="{ 'text-pink-600 animate-pulse': isListening }"
            title="Tìm kiếm bằng giọng nói"
          >
            <Mic v-if="!isListening" class="w-4 h-4" />
            <MicOff v-else class="w-4 h-4 text-pink-600" />
          </button>
        </div>

        <button 
          @click="handleSend"
          :disabled="!inputQuery.trim() || isGenerating"
          class="h-10 px-4 rounded-lg bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 active:scale-98 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-xs shadow-md shadow-pink-500/20 transition-all flex items-center justify-center gap-1.5 cursor-pointer shrink-0"
        >
          <span>Gửi</span>
          <Send class="w-3.5 h-3.5" />
        </button>
      </div>

      <div class="mt-2 flex items-center justify-between text-[11px] text-zinc-400 px-1">
        <span>Đang dùng: <strong class="text-zinc-700 font-semibold">{{ activeModel().name }}</strong></span>
        <span>Nhấn Enter để gửi</span>
      </div>
    </div>
  </div>
</template>
