FROM golang:1.24-alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Set alternative Go proxy
ENV GOPROXY=https://goproxy.io,direct

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o main .

# Final stage - using alpine for minimal image
FROM alpine:latest

WORKDIR /app

# Install ca-certificates for HTTPS requests
RUN apk --no-cache add ca-certificates

# Copy the binary from builder
COPY --from=builder /app/main .

# Copy static files
COPY static ./static

# Create non-root user (Alpine/BusyBox compatible)
RUN addgroup -g 1000 appuser && \
    adduser -D -u 1000 -G appuser appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Health check - check if main process is running
# Alpine's /proc might not have standard structure, so use a simple sleep based check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD sleep 1 || exit 1

# Run the application
CMD ["./main"]
