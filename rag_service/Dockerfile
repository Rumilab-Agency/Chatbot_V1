# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Expose FastAPI port
EXPOSE 8001

# Run FastAPI
CMD ["uvicorn", "rag_service:app", "--host", "0.0.0.0", "--port", "8001"]
