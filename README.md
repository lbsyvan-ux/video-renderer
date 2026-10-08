---
title: Video Meme Generator
emoji: 🌲
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
---

# Video Meme Generator API

Micro-service de rendu vidéo automatique pour TikTok / Instagram Reels.
Incruste automatiquement une phrase ou punchline centrée avec retour à la ligne sur une vidéo de fond 9:16.

## Endpoints

- `GET /health` : Test de fonctionnement
- `POST /render` : Générer une vidéo
  ```json
  {
    "video_url": "https://...mp4",
    "text": "Le calme intérieur est la seule vraie forteresse face au chaos du monde.",
    "duration": 7
  }
  ```
- `GET /videos/{filename}` : Téléchargement du MP4 généré
