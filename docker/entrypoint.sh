#!/bin/sh
set -e

echo "🟡 Waiting DB..."

until pg_isready -h database -p 5432 -U "$POSTGRES_USER"; do
  sleep 2
done

echo "🟡 Rodando migrations..."
python manage.py migrate --noinput

echo "🟡 Rodando testes..."
python manage.py test --verbosity=2

echo "🟢 Iniciando servidor..."
python manage.py runserver 0.0.0.0:8000