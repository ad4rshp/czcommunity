web: python manage.py migrate --noinput && (python manage.py createsuperuser --noinput || true) && python manage.py collectstatic --noinput && daphne -b 0.0.0.0 -p $PORT config.asgi:application
