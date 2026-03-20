Versão v2 com timeout maior para Render.

Se antes dava Internal Server Error ao processar PDFs grandes, esta versão corrige isso com:
- timeout maior no gunicorn
- tratamento de erro melhor
- limite de upload de 50 MB
