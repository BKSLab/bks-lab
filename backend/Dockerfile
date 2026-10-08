FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh \
    && groupadd --gid 1001 app && useradd --uid 1001 --gid app --no-create-home app

USER app
EXPOSE 8000

# The entrypoint applies Alembic migrations, then execs the command
# (compose `command:` overrides CMD and is passed through as "$@").
ENTRYPOINT ["./entrypoint.sh"]
CMD ["hypercorn", "main:app", "--bind", "0.0.0.0:8000"]
