FROM nginx:alpine

# Удаляем дефолтные конфиги
RUN rm /etc/nginx/conf.d/default.conf

# Копируем наш полный конфиг как ОСНОВНОЙ
COPY nginx.conf /etc/nginx/nginx.conf

# Создаем папку и копируем proxy_params
RUN mkdir -p /etc/nginx/conf.d
COPY conf.d/proxy_params /etc/nginx/conf.d/proxy_params

# Фавикон
RUN mkdir -p /var/www/media/images/
COPY favicon.ico /var/www/media/images/favicon.ico

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]