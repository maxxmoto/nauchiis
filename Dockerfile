FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf

WORKDIR /usr/share/nginx/html
COPY index.html articles-data.js manifest.json robots.txt sitemap.xml ./
COPY logo.png og.png og-image.png favicon.svg favicon.ico favicon-16.png favicon-32.png favicon-48.png apple-touch-icon.png icon-192.png icon-512.png ./
COPY cat-warning.webp cat-relax.webp cat-ai.webp footer.webp ./

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
