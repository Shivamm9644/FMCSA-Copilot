# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libmariadb-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY companyapi/requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install gunicorn

# Copy project
COPY companyapi /app/

# Expose port
EXPOSE 8000

# Run gunicorn
CMD ["gunicorn", "companyapi.wsgi:application", "--bind", "0.0.0.0:8000"]
