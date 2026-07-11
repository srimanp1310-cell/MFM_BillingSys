web: sh -c "python -m flask --app wsgi.py db upgrade && gunicorn wsgi:app --workers 2 --timeout 60 --bind 0.0.0.0:${PORT:-8000}"
