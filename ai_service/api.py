from fastapi import FastAPI
from pydantic import BaseModel
import torch
import torch.nn as nn
import torch.nn.functional as F
import mmh3
from transformers import AutoTokenizer, AutoModel

app = FastAPI(title="Que2Search Query Embedding API")

class QueryRequest(BaseModel):
    text: str

# --- BẢN THIẾT KẾ MÔ HÌNH TỪ KAGGLE NOTEBOOK ---
class AttentionFusion(nn.Module):
    def __init__(self, hidden_dim, num_channels):
        super(AttentionFusion, self).__init__()
        self.attn_proj = nn.Linear(hidden_dim * num_channels, num_channels)

    def forward(self, channels):
        concat_features = torch.cat(channels, dim=-1)
        attn_weights = F.softmax(self.attn_proj(concat_features), dim=-1)
        fused_representation = 0
        for i, channel in enumerate(channels):
            weight = attn_weights[:, i].unsqueeze(1)
            fused_representation += weight * channel
        return fused_representation

class QueryTower(nn.Module):
    def __init__(self, hidden_dim=256, vocab_size=100000):
        super(QueryTower, self).__init__()
        self.text_encoder = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        self.text_proj = nn.Linear(self.text_encoder.config.hidden_size, hidden_dim)
        self.char_trigram_emb = nn.EmbeddingBag(num_embeddings=vocab_size, embedding_dim=hidden_dim, mode='sum')
        self.fusion = AttentionFusion(hidden_dim, num_channels=2)

    def forward(self, input_ids, attention_mask, char_trigram_ids, char_offsets):
        text_outputs = self.text_encoder(input_ids=input_ids, attention_mask=attention_mask)
        text_rep = self.text_proj(text_outputs.last_hidden_state[:, 0, :])
        char_rep = self.char_trigram_emb(char_trigram_ids, char_offsets)
        final_rep = self.fusion([text_rep, char_rep])
        return F.normalize(final_rep, p=2, dim=-1)
# -----------------------------------------------

# Khởi tạo mô hình và tải trọng số
device = torch.device("cpu")
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")

model = QueryTower(hidden_dim=256)
model.load_state_dict(torch.load("checkpoints/que2search/que2search_epoch3_final.pth", map_location=device), strict=False)
model.eval()

# Endpoint xử lý tìm kiếm
@app.post("/api/v1/embed-query")
def embed_query(request: QueryRequest):
    query = request.text
    
    tokens = tokenizer(query, padding='max_length', truncation=True, max_length=32, return_tensors='pt')
    trigrams = [query[i:i+3] for i in range(max(1, len(query)-2))]
    char_ids = torch.tensor([abs(mmh3.hash(tg)) % 100000 for tg in trigrams], dtype=torch.long)
    
    with torch.no_grad():
        vector = model(
            input_ids=tokens['input_ids'],
            attention_mask=tokens['attention_mask'],
            char_trigram_ids=char_ids,
            char_offsets=torch.tensor([0])
        )
        
    return {"query": query, "vector": vector.squeeze(0).tolist()}