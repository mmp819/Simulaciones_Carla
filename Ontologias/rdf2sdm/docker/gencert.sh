openssl req \
    -subj '/C=SI/ST=Ljubljana/L=Ljubljana/O=None/CN=github-com' \
    -x509 -newkey rsa:4096 \
    -nodes -keyout ./nginx/conf.d/default_key.pem \
    -keyout ./nginx/conf.d/github-com.key \
    -out ./nginx/conf.d/github-com.crt
