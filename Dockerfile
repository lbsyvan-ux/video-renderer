FROM python:3.10-slim

# Installer FFmpeg et polices de caractères
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-freefont-ttf \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /app

# Installer les dépendances Python
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copier le code de l'application
COPY --chown=user:user . .

# Créer le dossier des vidéos en sortie
RUN mkdir -p /app/videos

EXPOSE 7860

# Supporte la variable $PORT de Render tout en ayant un fallback à 7860
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]
