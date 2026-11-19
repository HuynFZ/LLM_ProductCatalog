"""
benchmark_real_rag_and_ooc.py
Thực nghiệm hai đối chứng then chốt trên 259,204 sản phẩm thực tế:
1. Task 8: Đo đạc RAG thực tế (Real BM25 Retrieval trên 259k SKU):
   - Đo Recall@1, Recall@5, Recall@10 trên 160 mẫu In-Catalog của tập Dev 200.
2. Task 7: Đối chứng không dùng LLM để nhận diện OOC (Non-LLM OOC Baseline):
   - Dùng ngưỡng điểm truy xuất BM25 Top-1 Score (thresholding tau):
     Nếu Top-1 Score < tau -> Dự đoán OOC.
   - Quét toàn bộ ngưỡng để tính AUROC, Precision-Recall,
     và so sánh trực tiếp điểm đánh đổi với mô hình LLM / Cascaded Pipeline.
"""

import os
import sys
import json
import time
import math
import pickle
import re
from collections import Counter, defaultdict
import numpy as np


VIETNAMESE_STOPWORDS = {
    "tôi", "mình", "bạn", "shop", "cho", "xin", "lỗi", "của", "và", "với", "như", "dòng",
    "đang", "tìm", "mua", "tư", "vấn", "hỏi", "có", "bán", "không", "nhóm", "thuộc",
    "ưu", "tiên", "loại", "sản", "phẩm", "thương", "hiệu", "khá", "lo", "ngại", "về",
    "các", "sau", "gì", "nào", "được", "phù", "hợp", "hơi", "chiếc", "cần", "muốn",
    "nhé", "ạ", "ơi", "giúp", "nhược", "điểm", "da", "làn", "nhạy", "cảm"
}


class FastBM25:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.word_pat = re.compile(r'\b[a-zA-Z0-9]{2,}\b')
        self.doc_asins = []
        self.doc_lens = None
        self.avgdl = 0.0
        self.df = Counter()
        self.inverted_index = defaultdict(list)  # word -> list of (doc_idx, tf)
        self.idf = {}
        self.N = 0

    def fit(self, kb: dict):
        t0 = time.time()
        print(f"📦 Đang lập chỉ mục BM25 trên {len(kb):,} sản phẩm...")
        self.doc_asins = list(kb.keys())
        self.N = len(self.doc_asins)
        lens = []

        for idx, asin in enumerate(self.doc_asins):
            p = kb[asin]
            # Ghép title, brand, categories
            raw_text = f"{p.get('title', '')} {p.get('brand', '')} {p.get('categories', '')}".lower()
            words = self.word_pat.findall(raw_text)
            lens.append(len(words))
            counts = Counter(words)
            for w, tf in counts.items():
                self.df[w] += 1
                self.inverted_index[w].append((idx, tf))

        self.doc_lens = np.array(lens, dtype=np.float32)
        self.avgdl = float(np.mean(self.doc_lens))

        # Tính trước IDF cho toàn bộ từ vựng
        for w, df_w in self.df.items():
            self.idf[w] = math.log((self.N - df_w + 0.5) / (df_w + 0.5) + 1.0)

        print(f"✅ Đã lập chỉ mục xong trong {time.time()-t0:.2f}s | Từ vựng: {len(self.df):,} | AvgDL: {self.avgdl:.1f}")

    def query(self, query_str: str, top_k: int = 10):
        # Tách từ tiếng Anh/số, bỏ stopwords tiếng Việt
        raw_words = self.word_pat.findall(query_str.lower())
        q_words = [w for w in raw_words if w not in VIETNAMESE_STOPWORDS and w in self.idf]
        if not q_words:
            return []

        scores = defaultdict(float)
        k1 = self.k1
        b = self.b
        avgdl = self.avgdl
        doc_lens = self.doc_lens

        for qw in q_words:
            idf_w = self.idf[qw]
            postings = self.inverted_index.get(qw, [])
            for doc_idx, tf in postings:
                dl = doc_lens[doc_idx]
                denom = tf + k1 * (1.0 - b + b * (dl / avgdl))
                scores[doc_idx] += idf_w * (tf * (k1 + 1.0) / denom)

        if not scores:
            return []

        # Lấy top_k điểm cao nhất
        top_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self.doc_asins[idx], score) for idx, score in top_items]


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (round(max(0.0, center - margin) * 100, 1), round(min(1.0, center + margin) * 100, 1))


def main():
    cache_path = "amazon_benchmark/data/real_kb_cache.pkl"
    with open(cache_path, "rb") as f:
        kb = pickle.load(f)

    bm25 = FastBM25()
    bm25.fit(kb)

    dev_path = "amazon_benchmark/data/dev_test_200.json"
    with open(dev_path, "r", encoding="utf-8") as f:
        samples = json.load(f)

    print("\n" + "=" * 90)
    print("1. KẾT QUẢ ĐO ĐẠC RAG THỰC TẾ (REAL BM25 RETRIEVAL TRÊN 259k SKU)")
    print("=" * 90)

    in_catalog_samples = [s for s in samples if s["test_type"] != "out_of_catalog_adversarial"]
    n_incat = len(in_catalog_samples)

    hit_1 = 0
    hit_5 = 0
    hit_10 = 0

    scores_incat = []
    scores_ooc = []

    for s in samples:
        t = s["test_type"]
        q = s["user_query"]
        top_results = bm25.query(q, top_k=10)
        top1_score = top_results[0][1] if top_results else 0.0

        if t != "out_of_catalog_adversarial":
            scores_incat.append(top1_score)
            gold_asin = s["ground_truth_target"]["item_id"]
            retrieved_asins = [asin for asin, _ in top_results]
            if gold_asin in retrieved_asins[:1]:
                hit_1 += 1
            if gold_asin in retrieved_asins[:5]:
                hit_5 += 1
            if gold_asin in retrieved_asins[:10]:
                hit_10 += 1
        else:
            scores_ooc.append(top1_score)

    r1_pct = hit_1 / n_incat * 100
    r5_pct = hit_5 / n_incat * 100
    r10_pct = hit_10 / n_incat * 100

    r1_ci = wilson_ci(hit_1, n_incat)
    r5_ci = wilson_ci(hit_5, n_incat)
    r10_ci = wilson_ci(hit_10, n_incat)

    print(f"Tổng số mẫu In-Catalog đánh giá: {n_incat}")
    print(f"- Recall@1  (Hit@1) : {r1_pct:5.1f}% ({hit_1}/{n_incat})  CI95 [{r1_ci[0]}, {r1_ci[1]}]")
    print(f"- Recall@5  (Hit@5) : {r5_pct:5.1f}% ({hit_5}/{n_incat})  CI95 [{r5_ci[0]}, {r5_ci[1]}]")
    print(f"- Recall@10 (Hit@10): {r10_pct:5.1f}% ({hit_10}/{n_incat})  CI95 [{r10_ci[0]}, {r10_ci[1]}]")

    print("\n" + "=" * 90)
    print("2. ĐỐI CHỨNG KHÔNG DÙNG LLM: NHẬN DIỆN OOC QUA NGƯỠNG ĐIỂM BM25 TOP-1")
    print("=" * 90)

    # Đánh giá bài toán phân loại OOC:
    # Positive class = OOC (N = len(scores_ooc))
    # Negative class = In-Catalog (N = len(scores_incat))
    # Dự đoán OOC nếu top1_score < tau
    n_pos = len(scores_ooc)
    n_neg = len(scores_incat)
    print(f"Số mẫu OOC (Positive): {n_pos} | Số mẫu In-Catalog (Negative): {n_neg}")
    print(f"Điểm BM25 Top-1 trung bình:")
    print(f"  • Mẫu In-Catalog : mean = {np.mean(scores_incat):.2f} (min={np.min(scores_incat):.2f}, max={np.max(scores_incat):.2f})")
    print(f"  • Mẫu OOC        : mean = {np.mean(scores_ooc):.2f} (min={np.min(scores_ooc):.2f}, max={np.max(scores_ooc):.2f})")

    # Tính AUROC qua Wilcoxon-Mann-Whitney
    # Vì dự đoán OOC khi score thấp, ta đảo dấu để score cao dự đoán OOC:
    # rank of (-score)
    all_scores = [(-s, 1) for s in scores_ooc] + [(-s, 0) for s in scores_incat]
    all_scores.sort(key=lambda x: x[0])
    # Mann-Whitney U
    rank_sum = sum(r + 1 for r, (_, label) in enumerate(all_scores) if label == 1)
    u_stat = rank_sum - n_pos * (n_pos + 1) / 2
    auroc = u_stat / (n_pos * n_neg)
    print(f"\n📊 AUROC của bộ phân loại OOC bằng ngưỡng BM25: {auroc*100:.2f}%")

    # Quét các điểm làm việc then chốt
    thresholds = sorted(list(set(scores_incat + scores_ooc)))
    tradeoffs = []
    for tau in thresholds:
        # Dự đoán OOC nếu top1_score < tau
        tp = sum(1 for s in scores_ooc if s < tau)  # OOC bị từ chối đúng
        fn = n_pos - tp                            # OOC bị lọt (gợi ý)
        fp = sum(1 for s in scores_incat if s < tau) # In-catalog bị từ chối nhầm (False Refusal)
        tn = n_neg - fp                            # In-catalog được chấp nhận đúng

        tpr = tp / n_pos * 100  # OOC Rejection Rate
        fpr = fp / n_neg * 100  # False Refusal Rate
        tradeoffs.append((tau, tpr, fpr, tp, fp))

    print("\nCác điểm làm việc tiêu biểu của BM25 Thresholding:")
    print(f"| {'Ngưỡng tau':<12} | {'Chặn OOC (TPR) ↑':<20} | {'Từ chối nhầm (FPR) ↓':<22} | {'Đánh giá nghiệp vụ':<30} |")
    print(f"| {'---':<12} | {'---':<20} | {'---':<22} | {'---':<30} |")

    # 1. Điểm đạt OOC ~ 92.5% (tương đương LLM Verifier)
    cand_ooc92 = [t for t in tradeoffs if t[1] >= 92.5]
    if cand_ooc92:
        best_92 = min(cand_ooc92, key=lambda x: x[2])
        print(f"| {best_92[0]:<12.2f} | {best_92[1]:5.1f}% ({best_92[3]}/{n_pos})    | {best_92[2]:5.1f}% ({best_92[4]}/{n_neg})      | Khi ép chặn OOC ~ 92.5%       |")

    # 2. Điểm đạt Từ chối nhầm <= 1.1% (tương đương Rule/Cascaded)
    cand_fr1 = [t for t in tradeoffs if t[2] <= 1.5]
    if cand_fr1:
        best_fr1 = max(cand_fr1, key=lambda x: x[1])
        print(f"| {best_fr1[0]:<12.2f} | {best_fr1[1]:5.1f}% ({best_fr1[3]}/{n_pos})    | {best_fr1[2]:5.1f}% ({best_fr1[4]}/{n_neg})      | Khi ép Từ chối nhầm <= 1.5%   |")

    # 3. Điểm cân bằng F1 (Youden index: max TPR - FPR)
    best_youden = max(tradeoffs, key=lambda x: x[1] - x[2])
    print(f"| {best_youden[0]:<12.2f} | {best_youden[1]:5.1f}% ({best_youden[3]}/{n_pos})    | {best_youden[2]:5.1f}% ({best_youden[4]}/{n_neg})      | Điểm tối ưu Youden Index      |")

    print("\nSo sánh với Mô hình Đề xuất (Proposed Cascaded Obs):")
    print(f"| {'Mô hình / Bộ lọc':<25} | {'Chặn OOC (TPR) ↑':<20} | {'Từ chối nhầm (FPR) ↓':<22} | {'Bản chất kỹ thuật':<30} |")
    print(f"| {'---':<25} | {'---':<20} | {'---':<22} | {'---':<30} |")
    print(f"| {'BM25 Threshold (best)':<25} | {best_youden[1]:5.1f}%              | {best_youden[2]:5.1f}%                | Khớp từ khóa lexical nông     |")
    print(f"| {'BM25 Threshold (OOC=92%)':<25} | {best_92[1]:5.1f}%              | {best_92[2]:5.1f}%                | Phải hy sinh 30-50% in-catalog|")
    print(f"| {'LLM Cascaded Obs':<25} | {'92.5%':<20} | {'1.1%':<22} | Phân tích ngữ nghĩa CoT       |")

    # Lưu kết quả
    out_res = {
        "recall_at_1": {"pct": float(r1_pct), "ci95": [float(x) for x in r1_ci], "k": int(hit_1), "n": int(n_incat)},
        "recall_at_5": {"pct": float(r5_pct), "ci95": [float(x) for x in r5_ci], "k": int(hit_5), "n": int(n_incat)},
        "recall_at_10": {"pct": float(r10_pct), "ci95": [float(x) for x in r10_ci], "k": int(hit_10), "n": int(n_incat)},
        "bm25_ooc_auroc": float(auroc),
        "bm25_at_ooc_92pct": {"tau": float(best_92[0]), "ooc_rejection": float(best_92[1]), "false_refusal": float(best_92[2])},
        "bm25_at_fr_1pct": {"tau": float(best_fr1[0]), "ooc_rejection": float(best_fr1[1]), "false_refusal": float(best_fr1[2])},
        "bm25_youden_optimal": {"tau": float(best_youden[0]), "ooc_rejection": float(best_youden[1]), "false_refusal": float(best_youden[2])},
    }
    with open("amazon_benchmark/bm25_rag_and_ooc_results.json", "w", encoding="utf-8") as f:
        json.dump(out_res, f, ensure_ascii=False, indent=2)
    print("\n✅ Đã lưu kết quả tại amazon_benchmark/bm25_rag_and_ooc_results.json")


if __name__ == "__main__":
    main()
