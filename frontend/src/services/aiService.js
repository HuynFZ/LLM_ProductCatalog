import axios from 'axios';
import { availableModels } from '../data/products';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

const placeholderImages = [
  "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=600&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=600&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=600&auto=format&fit=crop&q=80"
];

const formatCurrency = (val) => {
  const num = Number(val || 0);
  if (num > 0 && num < 1000) return `$${num.toFixed(2)}`;
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(num);
};

// Hàm chuẩn hóa một sản phẩm từ Backend CSDL MySQL & Auto-CoT
export function normalizeProductData(p, index = 0) {
  const originalPrice = Number(p.original_price ?? p.originalPrice ?? p.price ?? 29.99);
  const discountPercent = Number(p.discount_percent ?? p.discountPercent ?? 0);
  const finalPrice = p.final_price ?? p.finalPrice ?? (discountPercent > 0 ? (originalPrice * (1 - discountPercent / 100)) : originalPrice);

  const productType = p.product_type || p.category || "Thời trang";
  const department = p.department || p.brand || "H&M Collection";
  const genderGroup = p.gender_group || "";
  const detailDesc = p.detail_desc || p.description || `${p.name || 'Sản phẩm'} thời trang chính hãng H&M.`;
  const color = p.color || "Tiêu chuẩn";
  const size = p.size || "M";
  const stockQuantity = p.stock_quantity !== undefined ? Number(p.stock_quantity) : 25;
  const variantId = p.variant_id || `${p.id || index}-${color}-${size}`;
  const availableColors = p.available_colors && p.available_colors.length > 0 ? p.available_colors : [color];
  const availableSizes = p.available_sizes && p.available_sizes.length > 0 ? p.available_sizes : [size];

  return {
    id: String(p.id ?? `SP_${index}`),
    name: p.name || p.title || `Sản phẩm #${p.id || index + 1}`,
    brand: department,
    category: productType,
    productType: productType,
    department: department,
    genderGroup: genderGroup,
    detailDesc: detailDesc,
    description: detailDesc,
    color: color,
    size: size,
    stockQuantity: stockQuantity,
    variantId: variantId,
    availableColors: availableColors,
    availableSizes: availableSizes,
    originalPrice: originalPrice,
    discountPercent: discountPercent,
    finalPrice: finalPrice,
    rating: p.rating ? Number(p.rating) : 4.8,
    reviewsCount: p.reviews_count ? Number(p.reviews_count) : 95,
    image: p.image || p.image_url || placeholderImages[index % placeholderImages.length],
    colorImages: p.color_images || {},
    matchScore: p.match_score !== undefined ? Number(p.match_score) : null,
    matchReason: p.match_reason || '',
    inStock: stockQuantity > 0,
    tags: [department, productType, color, `Size ${size}`, ...(genderGroup ? [genderGroup] : [])],
    specs: {
      "Mã SP (ID)": String(p.id ?? `SP_${index}`),
      "Loại sản phẩm": productType,
      "Bộ phận": department,
      "Đối tượng": genderGroup || "H&M Collection",
      "Màu sắc": color,
      "Kích cỡ": size,
      "Tồn kho": `${stockQuantity} sản phẩm`,
      "Mã biến thể": variantId
    }
  };
}

export async function sendChatMessage(query, selectedModelId = 'auto-cot', allProducts = [], isAiChat = true) {
  const normalizedQuery = query.toLowerCase().trim();
  const currentModel = availableModels.find(m => m.id === selectedModelId) || availableModels[0];

  // 1. Ưu tiên gọi API sang Backend FastAPI (Auto-CoT Hybrid Search)
  let backendResult = null;
  try {
    const response = await axios.post(`${API_BASE_URL}/api/chat`, {
      query: query,
      model_id: selectedModelId,
      model: selectedModelId,
      limit: isAiChat ? 5 : 200,
      is_ai_chat: isAiChat
    }, { timeout: 60000 });
    
    if (response?.data && (response.data.ai_response !== undefined || response.data.products_data !== undefined)) {
      backendResult = response.data;
    }
  } catch (e) {
    console.warn("Backend API Chat error / fallback to local:", e?.message || e);
  }

  // 2. Nếu Backend phản hồi thành công (kể cả khi products_data rỗng vẫn dùng dữ liệu thật từ Backend)
  if (backendResult) {
    const rawProducts = backendResult.products_data || [];
    const normalizedAiProducts = rawProducts.map((p, idx) => normalizeProductData(p, idx));
    const modelTag = `*[Xử lý bởi ${currentModel.name || 'Auto-CoT Hybrid Search'}]*\n\n`;
    
    // Đọc chính xác trường `sql_query` từ FastAPI Backend trả về
    const sqlQuery = backendResult.sql_query || backendResult.sql_generated || null;

    return {
      userQuery: query,
      aiResponse: backendResult.ai_response ? `${modelTag}${backendResult.ai_response}` : `${modelTag}Đã xử lý tìm kiếm thành công.`,
      matchedProductIds: backendResult.matched_product_ids || normalizedAiProducts.map(p => p.id),
      productsData: normalizedAiProducts,
      searchMethod: backendResult.search_method || "Auto-CoT Hybrid Search",
      sqlGenerated: sqlQuery,
      modelUsed: currentModel,
      timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    };
  }

  // 3. Fallback: Nếu Backend offline hoặc mất kết nối, chỉ tìm kiếm từ khóa thực sự có ý nghĩa
  let matchedProducts = [];
  const STOP_WORDS = new Set(["tìm", "mua", "cần", "muốn", "cho", "tôi", "màu", "size", "giá", "dưới", "chiếc", "cái", "sp", "với", "và", "của", "ở", "là", "bộ", "loại"]);
  const meaningfulKeywords = normalizedQuery.split(/\s+/).filter(w => w.length > 1 && !STOP_WORDS.has(w));
  
  if (allProducts.length > 0 && meaningfulKeywords.length > 0) {
    matchedProducts = allProducts.filter(p => {
      const text = `${p.name || ''} ${p.brand || ''} ${p.category || ''} ${p.description || ''} ${(p.tags || []).join(' ')}`.toLowerCase();
      // Bắt buộc phải khớp ít nhất một từ khóa chính
      return meaningfulKeywords.some(kw => text.includes(kw));
    });
  }

  const modelTag = `*[Xử lý bởi ${currentModel.name || 'Auto-CoT Hybrid Search'}]*\n\n`;

  if (matchedProducts.length === 0) {
    return {
      userQuery: query,
      aiResponse: `${modelTag}Rất tiếc, hệ thống không tìm thấy sản phẩm nào phù hợp với yêu cầu *"${query}"*. Bạn vui lòng thử lại với từ khóa khác nhé!`,
      matchedProductIds: [],
      productsData: [],
      searchMethod: "Text Keyword Search (0 kết quả)",
      sqlGenerated: null,
      modelUsed: currentModel,
      timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    };
  }

  const topItem = matchedProducts[0];
  const itemPrice = topItem.finalPrice || topItem.originalPrice || 0;

  return {
    userQuery: query,
    aiResponse: `${modelTag}Đã tìm thấy **${matchedProducts.length} sản phẩm** liên quan đến từ khóa của bạn.\n\n🌟 Gợi ý nổi bật: **${topItem.name}** (${formatCurrency(itemPrice)}).`,
    matchedProductIds: matchedProducts.map(p => p.id),
    productsData: matchedProducts,
    searchMethod: "Text Keyword Search (Fallback)",
    sqlGenerated: `SELECT * FROM products WHERE name LIKE '%${meaningfulKeywords[0] || query}%' LIMIT 10;`,
    modelUsed: currentModel,
    timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
  };
}

// Hàm tìm kiếm trực tiếp cho thanh tìm kiếm danh mục sản phẩm (is_ai_chat = false để lấy danh sách đầy đủ)
export async function searchCatalogVector(query) {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/chat`, {
      query: query,
      model: 'auto-cot',
      limit: 1000,
      is_ai_chat: false
    }, { timeout: 15000 });
    
    if (response?.data?.products_data) {
      return response.data.products_data.map((p, idx) => normalizeProductData(p, idx));
    }
    return [];
  } catch (e) {
    console.warn("Lỗi tìm kiếm danh mục:", e?.message || e);
    return [];
  }
}

