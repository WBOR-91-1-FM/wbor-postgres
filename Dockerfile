# Use a specific, smaller Python image as a base
FROM python:3.10-slim

# Set environment variables and define working directory
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy only the requirements file and install dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the Flask app port
EXPOSE 3000

# Start Flask app with Gunicorn on port 3000, with 4 worker processes
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:3000", "app:app", "-c", "gunicorn_config.py"]