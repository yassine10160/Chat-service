FROM python:3.13-slim

# no .pyc files in the image; print logs immediately (no buffering)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# dependencies first: this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# don't run as root
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000

# default process: the WebSocket server.
# the same image runs the listener with: python manage.py nats_listener
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
