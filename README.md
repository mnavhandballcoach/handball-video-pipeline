# Handball Video Pipeline

Pipeline automático para:
- receber vídeos dos utilizadores
- processar YOLO no Kaggle
- enviar vídeo anotado por email
- mover vídeos processados
- correr hora a hora via GitHub Actions

## Estrutura
- api/ → FastAPI para uploads
- kaggle/ → notebook de processamento
- .github/workflows → automação
