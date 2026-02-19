FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/
COPY compare.html /usr/share/nginx/html/
COPY src /usr/share/nginx/html/src

EXPOSE 80
