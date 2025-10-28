FROM python:3.12-slim


ENV PYTHONDONTWRITEBYTECODE=1 \
PYTHONUNBUFFERED=1 \
PIP_NO_CACHE_DIR=1


WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
build-essential \
&& rm -rf /var/lib/apt/lists/*


COPY requirements.txt ./
RUN pip install -r requirements.txt


COPY . .


# Create a non-root user (optional but recommended)
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser


EXPOSE 8000
CMD ["gunicorn", "backend.wsgi:application", "-c", "docker/gunicorn.conf.py"]