#!/bin/sh
set -e

echo "Starting Nginx Blue/Green configuration..."

# Determine primary and backup based on ACTIVE_POOL
if [ "$ACTIVE_POOL" = "blue" ]; then
    export PRIMARY_HOST="app_blue"
    export PRIMARY_PORT="8080"
    export BACKUP_HOST="app_green"
    export BACKUP_PORT="8080"
    echo "✓ Active pool: BLUE (primary), GREEN (backup)"
elif [ "$ACTIVE_POOL" = "green" ]; then
    export PRIMARY_HOST="app_green"
    export PRIMARY_PORT="8080"
    export BACKUP_HOST="app_blue"
    export BACKUP_PORT="8080"
    echo "✓ Active pool: GREEN (primary), BLUE (backup)"
else
    echo "ERROR: ACTIVE_POOL must be 'blue' or 'green'"
    exit 1
fi

# Process template with envsubst
echo "Processing nginx.conf.template..."
envsubst '${PRIMARY_HOST} ${PRIMARY_PORT} ${BACKUP_HOST} ${BACKUP_PORT}' \
    < /etc/nginx/nginx.conf.template \
    > /etc/nginx/nginx.conf

# Validate configuration
echo "Validating nginx configuration..."
nginx -t

# Start nginx in foreground
echo "Starting nginx..."
exec nginx -g 'daemon off;'
