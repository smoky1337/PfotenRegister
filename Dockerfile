FROM python:3.8-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg62-turbo \
    libpng16-16 \
    libfreetype6 \
    zlib1g \
    libstdc++6 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*
    
WORKDIR /app


# Copy the requirements file and install dependencies.
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code.
COPY . .

# Expose the port the app runs on.
ENV PORT 8080

# Use Gunicorn as the production WSGI server.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 run:app
