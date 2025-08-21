Agromerica API — Dockerized

Resumo
- Dockerfile multi-stage para empacotar a API Flask que usa Ultralytics (YOLO) para inferência.
- .dockerignore para manter a imagem limpa e evitar incluir dados/venv.
- docker-compose.yml para desenvolvimento/execução local.

Principais comandos (PowerShell)

# Build da imagem
docker build -t agromerica-api:latest .

# Rodar o container (mapeia porta e usa volume nomeado para uploads)
docker run --rm -p 5052:5052 -e PORT=5052 -e WORKERS=2 -v agromerica_uploads:/app/static/uploads --name agromerica-api agromerica-api:latest

# Alternativa com modelo montado do host (útil para atualizar modelo sem rebuild)
# docker run --rm -p 5052:5052 -e PORT=5052 -e WORKERS=2 -v C:\path\to\models:/app/models:ro -v agromerica_uploads:/app/static/uploads --name agromerica-api agromerica-api:latest

# Usando docker-compose
# Subir: docker-compose up -d
# Descer: docker-compose down

Recomendações e notas rápidas
- Preferences for production:
  - Pin versions in `requirements.txt` to ensure reproducible builds.
  - Consider mounting `models/` at runtime if you update the model frequentemente.
  - Evaluate using the official TensorFlow Docker images if you move to `tensorflow` instead of Ultralytics/PyTorch ecosystem.
  - Tune `WORKERS` (Gunicorn) according to memory/CPU. Start with 2-4 workers and measure.
  - Implement readiness/liveness endpoints and a Docker HEALTHCHECK if you plan to run under an orchestrator.

Segurança
- O contêiner roda com usuário não-root (`appuser`).
- Não inclua credenciais no repositório; use variáveis de ambiente ou um secrets manager.

Próximos passos que posso implementar (me diga qual prefere):
- Adicionar HEALTHCHECK no `Dockerfile` usando um `/health` endpoint.
- Fixar/pinar versões no `requirements.txt` e gerar wheels novamente.
- Mudar para uma base de imagem TensorFlow otimizada se você usar `tensorflow`.
- Remover arquivos locais sensíveis e garantir que `venv/` não seja enviado (já está no `.dockerignore`).
