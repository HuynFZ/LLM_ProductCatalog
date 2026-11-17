export const availableModels = [
  {
    id: "auto-cot",
    name: "Auto-CoT Hybrid Search",
    provider: "Ollama (Qwen 2.5) & MySQL",
    badge: "Auto-CoT 🌟",
    description: "Phân tích ý định qua suy luận CoT BFS & trích xuất thuộc tính JSON",
    color: "from-pink-500 to-rose-600",
    status: "connected",
    type: "llm"
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
