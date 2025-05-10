# Use official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project files
COPY . /app

# Expose port
EXPOSE 5000

# Start the app
CMD ["python", "app.py"]
