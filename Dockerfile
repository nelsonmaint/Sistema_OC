FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências primeiro, para aproveitar o cache de camadas do Docker.
# psycopg[binary] traz a libpq embutida, então não é preciso compilar nada.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Uploads de fotos/assinaturas vão para cá (helpers.py). Montado como volume
# no compose — o diretório precisa existir e pertencer ao usuário da app.
RUN mkdir -p /app/static/uploads \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

# run_prod.py sobe o Waitress em 0.0.0.0:5000 e força FLASK_DEBUG=0.
CMD ["python", "run_prod.py"]
