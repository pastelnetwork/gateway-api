FROM ubuntu:22.04

RUN apt-get update && \
      apt-get -y install sudo ca-certificates jq

#ADD https://download.pastel.network/latest/pastelup-linux-amd64 /pastelup-linux-amd64
COPY ./docker/pastelup-linux-amd64 /pastelup-linux-amd64
COPY ./docker/start-node.sh /start-node.sh
RUN chmod +x /pastelup-linux-amd64 /start-node.sh

RUN ["/pastelup-linux-amd64", "install", "node", "-n=testnet", "--force", "-r=latest", "-p=18.118.218.206,18.116.26.219"]

CMD /start-node.sh