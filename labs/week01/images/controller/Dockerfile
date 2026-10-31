FROM alpine:3.20.3

RUN apk add --no-cache openssh-server=9.7_p1-r5 \
    && mkdir -p /run/sshd /evidence \
    && adduser -D -s /bin/sh -h /home/labuser labuser \
    && passwd -d labuser

COPY sshd_config /etc/ssh/sshd_config
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
