export const availableModels = [
  {
    id: "que2search-vector",
    name: "Que2Search + Qdrant",
    provider: "Local Embedding & Vector DB",
    badge: "Vector Search ⚡",
    description: "Nhúng vector ngữ nghĩa 256 chiều và tìm kiếm khoảng cách Cosine trên Qdrant",
    color: "from-pink-500 to-rose-600",
    status: "connected"
  }
];

export const sampleSuggestions = [
  "Tìm các sản phẩm đang giảm giá",
  "Gợi ý sản phẩm giá tốt nhất",
  "Có những danh mục sản phẩm nào?",
  "Tìm sản phẩm theo mức giá",
  "Kiểm tra sản phẩm còn hàng"
];

// Khởi tạo mảng sản phẩm rỗng - Dữ liệu sẽ được tải 100% từ API Backend/Web
export const initialProducts = [];
