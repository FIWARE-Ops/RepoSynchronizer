FROM alpine
MAINTAINER Dmitrii Demin <mail@demin.co>

ADD server.py /opt/
ADD version /opt/

RUN apk add --no-cache --update python3 git \
&&  pip3 install requests \
&&  mkdir -p /tmp/reposynchronizer

WORKDIR /opt

CMD ["/usr/bin/python3", "-u", "/opt/server.py"]

EXPOSE 8000
