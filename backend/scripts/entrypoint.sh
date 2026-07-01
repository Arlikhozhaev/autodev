#!/bin/sh
set -e

cd /app
echo "Running database migrations..."
python -m app.db_migrate

# If docker-compose passed a command (worker, flower), run it; otherwise start API.
if [ "$#" -gt 0 ]; then
  echo "Starting: $*"
  exec "$@"
fi

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
