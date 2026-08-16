# Шаг 1: Сборка (Используем последнюю стабильную 1.24)
FROM golang:1.24-bullseye AS builder

# Устанавливаем зависимости для SQLite
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libc6-dev \
    pkg-config \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# МАГИЯ: Принудительно понижаем версию в go.mod до 1.24, чтобы компилятор не ругался
RUN if [ -f go.mod ]; then \
    go mod edit -go=1.24; \
    go mod tidy; \
    fi

# Если модуля совсем нет — создаем с нуля
RUN if [ ! -f go.mod ]; then \
    go mod init easy_lock && \
    go get github.com/mattn/go-sqlite3 && \
    go get github.com/skip2/go-qrcode && \
    go get github.com/joho/godotenv && \
    go mod tidy; \
    fi

# Компилируем
RUN CGO_ENABLED=1 GOOS=linux go build -a -ldflags '-extldflags "-static"' -o easylock main.go

# Шаг 2: Финал
FROM debian:bullseye-slim
RUN apt-get update && apt-get install -y ca-certificates --no-install-recommends && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/easylock .
# Копируем файлы проекта (шаблоны и т.д.)
COPY . . 
RUN mkdir -p /app/data
EXPOSE 8080
CMD ["./easylock"]