# Get the macless-haystack web application and host it locally

FROM alpine:latest AS setup-env

RUN apk add --no-cache wget unzip

# Download and unzip the app
WORKDIR /app
RUN wget -O webapplication.zip "https://github.com/dchristl/macless-haystack/releases/download/v2.1.0/webapplication.zip" && \
    unzip webapplication.zip && \
    rm webapplication.zip

FROM nginx:alpine

RUN apk add --no-cache openssl

RUN mkdir /etc/nginx/ssl

RUN openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/nginx.key -out /etc/nginx/ssl/nginx.crt \
    -subj "/C=XX/ST=State/L=City/O=Organization/CN=localhost"

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/

COPY --from=setup-env /app/web /usr/share/nginx/html

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
