FROM debian:bullseye-slim

RUN apt-get update && \
    apt-get install --no-install-recommends -y git python3 python3-pip python3-setuptools \
                                               procps net-tools iproute2 tcpdump && \
    apt-get autoclean && \
    rm -rf /var/cache/apt/* /var/lib/apt/*

COPY requirements.txt /tmp/
RUN python3 -m pip install -r /tmp/requirements.txt

COPY main.py /

VOLUME ["/root/.credentials"]

ENTRYPOINT [ "/main.py" ]
