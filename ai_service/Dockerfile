FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip --default-timeout=1000 install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
COPY . .
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"]