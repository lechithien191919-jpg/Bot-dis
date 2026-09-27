FROM python:3.11-slim

WORKDIR /app

# Cài đặt các công cụ build cơ bản để tránh lỗi pip install
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

# Nâng cấp pip và cài đặt thư viện
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8080

CMD ["python", "bot.py"]
