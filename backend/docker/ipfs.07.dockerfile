FROM ubuntu:22.04

ENV IPFS_PATH /data/ipfs
RUN mkdir -p $IPFS_PATH

VOLUME $IPFS_PATH

ADD https://github.com/ipfs/go-ipfs/releases/download/v0.7.0/go-ipfs_v0.7.0_linux-amd64.tar.gz ./
COPY ./docker/start_ipfs.sh /start_ipfs.sh
RUN tar -xzf go-ipfs_v0.7.0_linux-amd64.tar.gz &&  \
    cd go-ipfs &&  \
    ./install.sh &&  \
    chmod +x /start_ipfs.sh

CMD ["/start_ipfs.sh"]

EXPOSE 4001 5001 8080