# Stage 1: Build the image
FROM python:3.9-slim AS builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Run the image
FROM python:3.9-slim

WORKDIR /app

# Copy from builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY app.py .

EXPOSE 5000
CMD ["python", "app.py"]
