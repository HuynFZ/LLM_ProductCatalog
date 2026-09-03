import axios from 'axios';
import { availableModels } from '../data/products';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const placeholderImages = [
  "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=600&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=600&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=600&auto=format&fit=crop&q=80"
];

// Hàm chuẩn hóa một sản phẩm từ Backend Qdrant/MySQL
export function normalizeProductData(p, index = 0) {
  const originalPrice = Number(p.original_price ?? p.originalPrice ?? p.price ?? 0);
  const discountPercent = Number(p.discount_percent ?? p.discountPercent ?? 0);
  const finalPrice = p.final_price ?? p.finalPrice ?? (discountPercent > 0 ? (originalPrice * (1 - discountPercent / 100)) : originalPrice);

  return {
    id: String(p.id ?? p.parent_asin ?? `SP_${index}`),
    name: p.name || p.title || `Sản phẩm #${p.id || index + 1}`,
    brand: p.brand || "Chính hãng",
    category: p.category || p.main_category || "Điện tử & Phụ kiện",
    description: p.description || `${p.name || p.title || 'Sản phẩm'} chính hãng với công nghệ hiện đại và chất lượng cao cấp.`,
    originalPrice: originalPrice,
    discountPercent: discountPercent,
    finalPrice: finalPrice,
    rating: p.rating ? Number(p.rating) : (p.average_rating ? Number(p.average_rating) : 4.8),
    reviewsCount: p.reviews_count ? Number(p.reviews_count) : (p.rating_number ? Number(p.rating_number) : 95),
    image: p.image || p.image_url || placeholderImages[index % placeholderImages.length],
    matchScore: p.match_score !== undefined ? Number(p.match_score) : null,
    inStock: p.in_stock !== undefined ? Boolean(p.in_stock) : true,
    tags: p.tags || ["Vector Search", "Gợi ý AI"],
    specs: p.specs || {
      "Tình trạng": "Mới 100% nguyên seal",
      "Bảo hành": "12 tháng chính hãng",
      "Giao hàng": "Toàn quốc 2-3 ngày"
    }
  };
}

export async function sendChatMessage(query, selectedModelId = 'que2search-vector', allProducts = [], isAiChat = true) {
  const normalizedQuery = query.toLowerCase().trim();
  const currentModel = availableModels.find(m => m.id === selectedModelId) || availableModels[0];

  // 1. Ưu tiên gọi API sang Backend FastAPI (Vector Search qua Qdrant + Que2Search)
  let backendResult = null;
  try {
    const response = await axios.post(`${API_BASE_URL}/api/chat`, {
      query: query,
      model: selectedModelId,
      limit: isAiChat ? 5 : 200,
      is_ai_chat: isAiChat
    }, { timeout: 15000 });
    
    if (response?.data?.ai_response) {
      backendResult = response.data;
    }
  } catch (e) {
    console.warn("Backend API Chat error / fallback to local:", e?.message || e);
  }

  // 2. Nếu Backend trả về kết quả thành công từ Qdrant Vector Search
  if (backendResult?.products_data && backendResult.products_data.length > 0) {
    const normalizedAiProducts = backendResult.products_data.map((p, idx) => normalizeProductData(p, idx));
    const modelTag = `*[Xử lý bởi ${currentModel.name}]*\n\n`;

    return {
      userQuery: query,
      aiResponse: `${modelTag}${backendResult.ai_response}`,
      matchedProductIds: backendResult.matched_product_ids || normalizedAiProducts.map(p => p.id),
      productsData: normalizedAiProducts,
      searchMethod: backendResult.search_method || "Semantic Vector Search (Que2Search + Qdrant)",
      sqlGenerated: backendResult.sql_generated || null,
      modelUsed: currentModel,
      timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    };
  }

  // 3. Fallback: Nếu Backend không có kết quả hoặc offline, phân tích từ khóa trực tiếp
  let matchedProducts = [];
  let responseText = '';
  const formatVND = (v) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(v);
  const keywords = normalizedQuery.split(/\s+/).filter(w => w.length > 1);
  
  if (allProducts.length > 0) {
    let maxPrice = null;
    const millionMatch = normalizedQuery.match(/(?:dưới|tầm|nhỏ hơn|<|dưới mức)\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m)/i);
    if (millionMatch) {
      maxPrice = parseFloat(millionMatch[1].replace(',', '.')) * 1000000;
    } else {
      const rawNumberMatch = normalizedQuery.match(/(?:dưới|nhỏ hơn|<)\s*(\d{6,9})/i);
      if (rawNumberMatch) {
        maxPrice = parseInt(rawNumberMatch[1], 10);
      }
    }

    matchedProducts = allProducts.filter(p => {
      const text = `${p.name || ''} ${p.brand || ''} ${p.category || ''} ${p.description || ''} ${(p.tags || []).join(' ')}`.toLowerCase();
      return keywords.some(kw => text.includes(kw));
    });

    if (/giảm giá|khuyến mãi|sale|ưu đãi|rẻ|rẻ nhất|tiết kiệm/i.test(normalizedQuery)) {
      const discounted = allProducts.filter(p => Number(p.discountPercent || p.discount_percent || 0) > 0);
      if (discounted.length > 0) {
        matchedProducts = discounted;
      }
    }

    if (maxPrice !== null && matchedProducts.length > 0) {
      const priceFiltered = matchedProducts.filter(p => (p.finalPrice || p.originalPrice || 0) <= maxPrice);
      if (priceFiltered.length > 0) {
        matchedProducts = priceFiltered;
      }
    }

    if (matchedProducts.length === 0) {
      matchedProducts = allProducts.slice(0, 3);
    }
  }

  const modelTag = `*[Xử lý bởi ${currentModel.name}]*\n\n`;

  if (backendResult?.ai_response) {
    responseText = `${modelTag}${backendResult.ai_response}`;
  } else if (allProducts.length === 0) {
    responseText = `${modelTag}Hiện tại chưa có dữ liệu sản phẩm nào từ API Web. Hãy khởi chạy Backend FastAPI và kết nối CSDL để tìm kiếm sản phẩm nhé!`;
  } else if (matchedProducts.length === 0) {
    responseText = `${modelTag}Tôi chưa tìm thấy sản phẩm nào khớp với yêu cầu *"${query}"* trong danh mục hiện tại.`;
  } else {
    const topItem = matchedProducts[0];
    const itemPrice = topItem.finalPrice || topItem.originalPrice || 0;
    const itemDiscount = topItem.discountPercent || topItem.discount_percent || 0;

    responseText = `${modelTag}Tôi đã tìm thấy **${matchedProducts.length} sản phẩm** phù hợp với yêu cầu của bạn!\n\n🌟 Gợi ý hàng đầu: **${topItem.name}** với giá ưu đãi **${formatVND(itemPrice)}** ${itemDiscount > 0 ? `(Giảm ${itemDiscount}%)` : ''}.`;
  }

  const sqlGenerated = backendResult?.sql_generated || 
    `SELECT id, name, original_price, discount_percent FROM products WHERE name LIKE '%${query}%' LIMIT 10;`;

  return {
    userQuery: query,
    aiResponse: responseText,
    matchedProductIds: matchedProducts.map(p => p.id),
    productsData: matchedProducts,
    searchMethod: "Text Keyword Search (Fallback)",
    sqlGenerated: sqlGenerated,
    modelUsed: currentModel,
    timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
  };
}

// Hàm tìm kiếm trực tiếp cho thanh tìm kiếm danh mục sản phẩm (is_ai_chat = false để lấy danh sách đầy đủ)
export async function searchCatalogVector(query) {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/chat`, {
      query: query,
      model: 'que2search-vector',
      limit: 200,
      is_ai_chat: false
    }, { timeout: 15000 });
    
    if (response?.data?.products_data) {
      return response.data.products_data.map((p, idx) => normalizeProductData(p, idx));
    }
    return [];
  } catch (e) {
    console.warn("Lỗi tìm kiếm vector danh mục:", e?.message || e);
    return [];
  }
}

