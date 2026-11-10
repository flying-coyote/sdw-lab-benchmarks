FROM alpine:3.22
RUN apk add --no-cache tcpdump dnsmasq && tcpdump --version 2>&1 | head -2 && dnsmasq --version | head -1
