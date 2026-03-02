FROM nginx:alpine

# Copy app files
COPY apps/ /usr/share/nginx/html/apps/

# Copy nginx config
COPY server/nginx.conf /etc/nginx/conf.d/default.conf

# Generate manifest
COPY server/build-manifest.sh /tmp/build-manifest.sh
RUN chmod +x /tmp/build-manifest.sh && /tmp/build-manifest.sh && rm /tmp/build-manifest.sh
