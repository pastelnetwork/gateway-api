from app.utils.ipfs_tools import IPFSClient
import asyncio

file_local_path = "/Users/alexey/Work/Pastel/psltrader/sample_images/Dicklesworthstone_Pastel_Networks_new_Cascade_decentralized_sto_e96d86f2-eafc-41ad-a210-899197321e8c.png"
# file_local_path = "/tmp/test_ipfs.txt"


async def main():
    async with IPFSClient("http://localhost:5001/api/v0") as ipfs_client:
        res = await ipfs_client.add(file_local_path)
        cid = res['Hash']
        print(cid)

        await ipfs_client.get(cid, "/tmp/file.png")

        data = await ipfs_client.cat(cid)
        print(data)

        data = await ipfs_client.remove_pin(cid)
        print(data)

if __name__ == '__main__':
    asyncio.run(main())
