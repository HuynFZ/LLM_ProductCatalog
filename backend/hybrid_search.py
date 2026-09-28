import os
import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from sqlalchemy.orm import Session
from database import SessionLocal
from db_models import Product, ProductVariant
from llm_agent import (
    cot_unified_search_intent,
    ALL_HM_CATEGORIES,
    RELATED_CATEGORIES_MAP
)

GENDER_MAP = {
    "Ladies": ["Ladieswear", "Divided"],
    "Mens": ["Menswear"],
    "Kids": ["Baby/Children"]
}

# ==========================================
# 1. ĐỊNH DẠNG KẾT QUẢ TÌM KIẾM
# ==========================================
class SearchResult:
    """Wrapper class lưu trữ thông tin sản phẩm và biến thể tối ưu nhất"""
    def __init__(self, product_obj, matched_variant=None, match_score=1.0, match_reason=""):
        self.product_id = str(product_obj.id)
        self.product = product_obj
        self.name = product_obj.name
        self.product_type = product_obj.product_type or "N/A"
        self.product_group = getattr(product_obj, "product_group", "") or "Thời trang H&M"
        self.department = product_obj.department or "H&M Collection"
        self.gender_group = getattr(product_obj, "gender_group", "") or "H&M Collection"
        self.pattern = getattr(product_obj, "pattern", "") or "Solid"
        self.detail_desc = product_obj.detail_desc or "Sản phẩm thời trang H&M chính hãng."
        self.match_score = float(match_score)
        self.match_reason = match_reason
        
        if not matched_variant:
            try:
                vars_list = product_obj.variants
                if vars_list:
                    matched_variant = vars_list[0]
            except Exception:
                matched_variant = None

        self.price = float(matched_variant.price) if matched_variant and matched_variant.price else 29.99
        self.color = matched_variant.color if matched_variant and matched_variant.color else "Tiêu chuẩn"
        self.size = matched_variant.size if matched_variant and matched_variant.size else "M"
        self.stock_quantity = int(matched_variant.stock_quantity) if matched_variant and matched_variant.stock_quantity is not None else 15
        self.variant_id = matched_variant.variant_id if matched_variant and matched_variant.variant_id else f"{self.product_id}-{self.color}-{self.size}"
        self.article_id = str(getattr(matched_variant, "article_id", None) or product_obj.id).zfill(10)
        
        try:
            vars_list = product_obj.variants or []
            self.available_colors = list(dict.fromkeys(v.color for v in vars_list if v.color)) or [self.color]
            self.available_sizes = list(dict.fromkeys(v.size for v in vars_list if v.size)) or [self.size]
            
            self.color_images = {}
            self.color_details = {}
            for v in vars_list:
                c = v.color or "Tiêu chuẩn"
                art = str(getattr(v, "article_id", None) or product_obj.id).zfill(10)
                img = f"http://localhost:8080/images/{art[:3]}/{art}.jpg"
                self.color_images[c] = img
                
                if c not in self.color_details:
                    self.color_details[c] = {
                        "color": c,
                        "article_id": art,
                        "image_url": img,
                        "price": round(float(v.price), 2) if v.price else self.price,
                        "stock_quantity": 0,
                        "sizes": [],
                        "size_stocks": {}
                    }
                if v.size:
                    if v.size not in self.color_details[c]["sizes"]:
                        self.color_details[c]["sizes"].append(v.size)
                    s_qty = int(v.stock_quantity) if v.stock_quantity is not None else 0
                    self.color_details[c]["size_stocks"][v.size] = s_qty
                    self.color_details[c]["stock_quantity"] += s_qty
        except Exception:
            self.available_colors = [self.color]
            self.available_sizes = [self.size]
            self.color_images = {}
            self.color_details = {}

class HybridSearchResult(list):
    """Subclass của list cho phép truy cập metadata Chain-of-Thought (CoT)"""
    def __init__(self, items, cot_metadata=None):
        super().__init__(items)
        self.cot_metadata = cot_metadata or {}

# ==========================================
# 2. HÀM TẠO CÂU LỆNH SQL THỰC TẾ DỰA TRÊN CoT
# ==========================================
def build_real_sql_query(categories: list, gender_groups: list, color: str, size: str, max_price: float, color_matched: bool = True, limit: int = 12) -> str:
    """Tạo câu lệnh SQL động chuẩn xác phản ánh đúng kết quả bóc tách từ CoT"""
    where_clauses = ["1=1"]
    
    if categories:
        if len(categories) == 1:
            where_clauses.append(f"p.product_type = '{categories[0]}'")
        else:
            cat_in = ", ".join([f"'{c}'" for c in categories])
            where_clauses.append(f"p.product_type IN ({cat_in})")
        
    if gender_groups:
        g_in = ", ".join([f"'{g}'" for g in gender_groups])
        where_clauses.append(f"p.gender_group IN ({g_in})")
        
    if color and color_matched:
        where_clauses.append(f"LOWER(v.color) LIKE '%{color.lower()}%'")
        
    if size:
        where_clauses.append(f"UPPER(v.size) = '{size.upper()}'")
        
    if max_price is not None:
        where_clauses.append(f"v.price <= {max_price:.2f}")

    where_str = "\n  AND ".join(where_clauses)
    comment = ""
    if color and not color_matched and categories:
        comment = f"-- Lưu ý: Màu '{color}' hiện tạm hết hàng cho danh mục {categories[0]}, hiển thị các màu sẵn có\n"

    sql = (
        f"{comment}"
        "SELECT p.id, p.name, p.product_type, p.gender_group, p.department, v.color, v.size, v.price\n"
        "FROM products p\n"
        "JOIN product_variants v ON p.id = v.product_id\n"
        f"WHERE {where_str}\n"
        f"LIMIT {limit};"
    )
    return sql

# ==========================================
# 3. HÀM THỰC THI GRAPH CHAIN-OF-THOUGHT (GRAPH-COT)
# ==========================================
def execute_hybrid_search(user_query: str):
    """
    Thực thi tìm kiếm lai bằng Chain-of-Thought (Graph-CoT):
    1. Bước 1: Suy luận CoT đa tầng (Ý định -> Danh mục đồ thị -> Thuộc tính -> Chiến lược CSDL).
    2. Bước 2: Truy vấn ưu tiên tuyệt đối danh mục chính (Primary Category).
    3. Bước 3: Lọc và xếp hạng sản phẩm (100% khớp chuẩn nếu có màu, 85% nếu đúng loại nhưng hết màu).
    4. Bước 4: Đóng gói danh sách sản phẩm cùng metadata CoT hoàn chỉnh.
    """
    print(f"\n🔍 [Graph-CoT Search] Nhận truy vấn: '{user_query}'")
    
    all_db_categories = []
    db_init: Session = SessionLocal()
    try:
        all_db_categories = [r[0] for r in db_init.query(Product.product_type).filter(Product.product_type.isnot(None)).distinct().all() if r[0]]
    except Exception as e:
        print(f"Lỗi lấy danh mục từ DB: {e}")
    finally:
        db_init.close()

    # Bước 1: Chạy Chain-of-Thought (CoT)
    intent = cot_unified_search_intent(user_query, db_categories=all_db_categories)
    
    thought_process = intent.get("thought_process", [])
    suy_luan = intent.get("suy_luan", "")
    primary_category = intent.get("category")
    related_categories = intent.get("related_categories", [])
    extracted_gender = intent.get("gender")
    target_color = intent.get("color")
    target_size = intent.get("size")
    target_max_price = intent.get("max_price")

    target_gender_groups = []
    if extracted_gender and extracted_gender in GENDER_MAP:
        target_gender_groups = GENDER_MAP[extracted_gender]

    print(f"🎯 CoT Danh mục chính: {primary_category} | Danh mục phụ: {related_categories} | Giới tính: {target_gender_groups} | Màu: {target_color} | Size: {target_size} | Giá max: {target_max_price}")

    # Nếu hoàn toàn không phát hiện danh mục hay bất kỳ thuộc tính nào
    if not primary_category and not related_categories and not target_color and not target_size and not target_max_price and not target_gender_groups:
        print("⚠️ Không tìm thấy tiêu chí thời trang phù hợp.")
        cot_metadata = {
            "thought_process": thought_process,
            "suy_luan": suy_luan,
            "intent": intent,
            "predicted_categories": [],
            "target_gender_groups": [],
            "color": target_color,
            "size": target_size,
            "max_price": target_max_price,
            "sql_query": "-- Không tìm thấy tiêu chí phù hợp"
        }
        return HybridSearchResult([], cot_metadata=cot_metadata)

    db: Session = SessionLocal()
    try:
        color_lower = target_color.lower() if target_color else ""
        size_upper = target_size.upper() if target_size else ""

        # --- GIAI ĐOẠN 1: TRUY VẤN DANH MỤC CHÍNH (PRIMARY CATEGORY) ---
        primary_products = []
        if primary_category:
            p_query = db.query(Product).join(ProductVariant).filter(Product.product_type == primary_category)
            if target_gender_groups:
                extended_genders = list(set(target_gender_groups + ["Divided"]))
                if p_query.filter(Product.gender_group.in_(extended_genders)).first():
                    p_query = p_query.filter(Product.gender_group.in_(extended_genders))
            primary_products = p_query.distinct().all()

        scored_primary = []
        primary_color_matched = False

        if primary_products:
            # Kiểm tra xem danh mục chính có sản phẩm nào khớp màu yêu cầu hay không
            if color_lower:
                for prod in primary_products:
                    for v in (prod.variants or []):
                        if v.color and color_lower in v.color.lower():
                            primary_color_matched = True
                            break
                    if primary_color_matched:
                        break

            for prod in primary_products:
                cat_score = 50  # Điểm cơ sở cao nhất cho đúng danh mục chính yêu cầu
                
                # Điểm giới tính (tối đa 20 điểm)
                g = prod.gender_group or ""
                if target_gender_groups:
                    gender_score = 20 if g in target_gender_groups else (15 if g == "Divided" else 5)
                else:
                    gender_score = 20

                # Tìm biến thể tốt nhất cho sản phẩm
                variants = prod.variants or []
                best_variant = None
                best_variant_score = -1
                this_prod_color_match = False

                for v in variants:
                    v_score = 0
                    v_color = (v.color or "").lower()
                    v_size = (v.size or "").upper()
                    v_price = float(v.price or 0)

                    # Điểm màu sắc (Tối đa 20 điểm)
                    if color_lower:
                        if color_lower in v_color:
                            v_score += 20
                            this_prod_color_match = True
                        else:
                            v_score += 0
                    else:
                        v_score += 20

                    # Điểm kích cỡ (Tối đa 5 điểm)
                    if size_upper:
                        if size_upper == v_size:
                            v_score += 5
                    else:
                        v_score += 5

                    # Điểm giá (Tối đa 5 điểm)
                    if target_max_price is not None:
                        if v_price <= target_max_price:
                            v_score += 5
                    else:
                        v_score += 5

                    if v_score > best_variant_score:
                        best_variant_score = v_score
                        best_variant = v

                if not best_variant and variants:
                    best_variant = variants[0]

                # Tính tổng điểm
                if color_lower and not primary_color_matched:
                    # Trường hợp danh mục chính có hàng nhưng tạm hết màu yêu cầu:
                    # Giữ điểm ở mức 85% để người dùng biết đúng loại nhưng khác màu
                    total_score = 85
                    available_colors = list(dict.fromkeys(v.color for v in variants if v.color))
                    match_label = f"Đúng loại {prod.product_type} (Tạm hết màu {target_color}, còn: {', '.join(available_colors[:3])})"
                else:
                    total_score = cat_score + gender_score + max(best_variant_score, 0)
                    available_colors = list(dict.fromkeys(v.color for v in variants if v.color))
                    if total_score >= 95:
                        match_label = "Khớp chuẩn xác 100%"
                    elif total_score >= 80:
                        match_label = "Khớp tiêu chí chính"
                    else:
                        match_label = f"Sản phẩm {prod.product_type}"

                match_percentage = min(round(total_score / 100.0, 2), 1.0)
                scored_primary.append((
                    match_percentage,
                    SearchResult(prod, best_variant, match_score=match_percentage, match_reason=match_label)
                ))

            # Sắp xếp danh mục chính giảm dần theo điểm
            scored_primary.sort(key=lambda x: x[0], reverse=True)

        # --- GIAI ĐOẠN 2: TRUY VẤN BỔ SUNG NẾU THIẾU HOẶC KHÔNG CÓ DANH MỤC CHÍNH ---
        scored_secondary = []
        # Chỉ bổ sung từ danh mục phụ nếu danh mục chính có ít hơn 12 sản phẩm
        slots_needed = 12 - len(scored_primary)
        if slots_needed > 0:
            supp_categories = related_categories if primary_category else []
            if not primary_category and not supp_categories:
                # Không có danh mục cụ thể, tìm kiếm theo thuộc tính (màu sắc, giới tính, giá)
                attr_query = db.query(Product).join(ProductVariant)
                if color_lower:
                    attr_query = attr_query.filter(ProductVariant.color.ilike(f"%{color_lower}%"))
                if target_gender_groups:
                    attr_query = attr_query.filter(Product.gender_group.in_(target_gender_groups))
                supp_products = attr_query.limit(24).all()
                for prod in supp_products:
                    variants = prod.variants or []
                    best_v = variants[0] if variants else None
                    scored_secondary.append((
                        0.85,
                        SearchResult(prod, best_v, match_score=0.85, match_reason=f"Phù hợp màu {target_color or ''}")
                    ))
            elif supp_categories and not scored_primary:
                # Danh mục chính hoàn toàn không có trong kho, chuyển sang danh mục phụ
                sec_query = db.query(Product).join(ProductVariant).filter(Product.product_type.in_(supp_categories))
                if target_gender_groups:
                    sec_query = sec_query.filter(Product.gender_group.in_(target_gender_groups))
                supp_products = sec_query.distinct().limit(slots_needed).all()
                for prod in supp_products:
                    variants = prod.variants or []
                    best_v = variants[0] if variants else None
                    scored_secondary.append((
                        0.70,
                        SearchResult(prod, best_v, match_score=0.70, match_reason=f"Gợi ý thay thế: {prod.product_type}")
                    ))
            elif supp_categories and len(scored_primary) < 12 and not (color_lower and not primary_color_matched):
                # Chỉ gợi ý thêm phụ kiện nếu màu sắc của danh mục chính có sẵn
                sec_query = db.query(Product).join(ProductVariant).filter(Product.product_type.in_(supp_categories))
                supp_products = sec_query.distinct().limit(slots_needed).all()
                for prod in supp_products:
                    variants = prod.variants or []
                    best_v = variants[0] if variants else None
                    scored_secondary.append((
                        0.60,
                        SearchResult(prod, best_v, match_score=0.60, match_reason=f"Gợi ý đi kèm: {prod.product_type}")
                    ))

        # Tổng hợp kết quả: Danh mục chính LUÔN ĐỨNG ĐẦU
        final_scored = scored_primary + scored_secondary
        if not final_scored:
            print("⚠️ Không tìm thấy sản phẩm nào trong CSDL thỏa mãn.")
            real_sql = build_real_sql_query(
                categories=[primary_category] if primary_category else [],
                gender_groups=target_gender_groups,
                color=target_color,
                size=target_size,
                max_price=target_max_price,
                color_matched=True
            )
            cot_metadata = {
                "thought_process": thought_process,
                "suy_luan": suy_luan,
                "intent": intent,
                "predicted_categories": [primary_category] if primary_category else [],
                "target_gender_groups": target_gender_groups,
                "color": target_color,
                "size": target_size,
                "max_price": target_max_price,
                "sql_query": real_sql,
                "color_out_of_stock": False
            }
            return HybridSearchResult([], cot_metadata=cot_metadata)

        final_list = [item[1] for item in final_scored[:12]]

        # Xây dựng câu lệnh SQL thực tế thể hiện đúng trạng thái CoT
        color_out_of_stock = bool(primary_category and color_lower and not primary_color_matched)
        real_sql = build_real_sql_query(
            categories=[primary_category] if primary_category else (related_categories if not scored_primary else []),
            gender_groups=target_gender_groups,
            color=target_color,
            size=target_size,
            max_price=target_max_price,
            color_matched=not color_out_of_stock,
            limit=12
        )

        cot_metadata = {
            "thought_process": thought_process,
            "suy_luan": suy_luan,
            "intent": intent,
            "predicted_categories": [primary_category] if primary_category else related_categories,
            "target_gender_groups": target_gender_groups,
            "color": target_color,
            "size": target_size,
            "max_price": target_max_price,
            "sql_query": real_sql,
            "color_out_of_stock": color_out_of_stock,
            "total_found": len(final_scored)
        }

        print(f"🎉 Graph-CoT hoàn tất: Trả về {len(final_list)} sản phẩm {primary_category or ''} (Khớp từ {final_list[0].match_score*100:.0f}% xuống {final_list[-1].match_score*100:.0f}%)" if final_list else "⚠️ 0 kết quả.")
        return HybridSearchResult(final_list, cot_metadata=cot_metadata)

    except Exception as e:
        print(f"Lỗi truy vấn Database: {e}")
        return HybridSearchResult([], cot_metadata={})
    finally:
        db.close()