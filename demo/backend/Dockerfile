# Sử dụng Python môi trường nhẹ
FROM python:3.10-slim

WORKDIR /app

# Copy file requirements và cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code backend vào container
COPY . .

# Mở port 8080 và chạy FastAPI bằng Uvicorn
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]

