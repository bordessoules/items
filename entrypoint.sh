#!/bin/bash

# Wait for database to be ready
echo "Waiting for postgres..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 0.1
done
echo "PostgreSQL started"

# Make migrations
echo "Making migrations..."
python manage.py makemigrations --noinput

# Apply migrations
echo "Applying migrations..."
python manage.py migrate --noinput

# Initialize application (including superuser creation)
if [ "$DJANGO_SUPERUSER_USERNAME" ] && [ "$DJANGO_SUPERUSER_EMAIL" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Checking for superuser..."
    user_exists=$(python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); print(User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists())")
    
    if [ "$user_exists" = "False" ]; then
        echo "Creating superuser..."
        python manage.py createsuperuser \
            --noinput \
            --username $DJANGO_SUPERUSER_USERNAME \
            --email $DJANGO_SUPERUSER_EMAIL
        echo "Superuser created successfully!"
    else
        echo "Superuser already exists, skipping creation"
    fi
fi

# Make migrations
echo "Making migrations..."
python manage.py makemigrations --noinput

# Apply migrations
echo "Applying migrations..."
python manage.py migrate --noinput

# Start server
echo "Starting server..."
python manage.py runserver 0.0.0.0:8000
