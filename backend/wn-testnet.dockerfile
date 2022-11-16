FROM ubuntu:22.04

RUN apt-get update && \
      apt-get -y install sudo ca-certificates jq

#ADD https://download.pastel.network/latest/pastelup-linux-amd64 /pastelup-linux-amd64
COPY ./docker/pastelup-linux-amd64 /pastelup-linux-amd64
COPY ./docker/start-wn.sh /start-wn.sh
RUN chmod +x /pastelup-linux-amd64 /start-wn.sh

RUN ["/pastelup-linux-amd64", "install", "walletnode", "-n=testnet", "--force", "-r=latest", "-p=18.118.218.206,18.116.26.219"]
RUN sed -i -e '/hostname/s/localhost/0.0.0.0/' ~/.pastel/walletnode.yml && \
    sed -i -e '$arpcbind=0.0.0.0' ~/.pastel/pastel.conf && \
    sed -i -e '$arpcallowip=172.0.0.0/8' ~/.pastel/pastel.conf && \
    sed -i -e 's/rpcuser=.*/rpcuser=rpc_user/' ~/.pastel/pastel.conf && \
    sed -i -e 's/rpcpassword=.*/rpcpassword=rpc_pwd/' ~/.pastel/pastel.conf

CMD /start-wn.sh

EXPOSE 8080 19332