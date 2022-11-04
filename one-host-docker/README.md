

```shell
docker compose up -d
```

```shell
docker exec -it one-host-docker-wn-1 /root/pastel/pastel-cli getnewaddress
docker exec -it one-host-docker-wn-1 /root/pastel/pastel-cli pastelid newkey <PASSWORD> | jq -r '.pastelid'
```

Send 100K PSL to the address generated in the previous step.

```shell
docker exec -it one-host-docker-wn-1 /root/pastel/pastel-cli tickets register id <PASTELID> <PASSWORD> <ADDRESS>
docker exec -it one-host-docker-wn-1 cat /root/.pastel/pastel.conf
```
