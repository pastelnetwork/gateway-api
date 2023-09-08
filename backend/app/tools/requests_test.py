import httpx
import json
import asyncio
import time


async def master_openapi_gateway_func(email: str, api_key: str, oauth_token: str, request_type: str,
                                      request_argument: str):
    headers = {
        # "authorization": f"bearer {oauth_token}",
        "api_key": f"{api_key}"
    }
    base_url = "https://testnet.gateway-api.pastel.network/api/v1/"
    #base_url = "http://localhost:9000/api/v1/"
    final_url = base_url + f"{request_type}/{request_argument}"

    start_time = time.time()
    async with httpx.AsyncClient(timeout=120.0, limits=httpx.Limits(max_keepalive_connections=10)) as client:
        response = await client.get(final_url, headers=headers)

    if response.status_code == 200:
        response_dict = json.loads(response.content)
        print(f"API call for request type {request_type}-{request_argument} took {time.time() - start_time} seconds")
        return response_dict
    else:
        return {"error": f"Request failed with status code: {response.status_code}"}


async def main():
    email = "example@email.com"
    # api_key = "39d0420ea4fbf7bd738f55c88b4a476bf9f57f72b5634192bc336dc5cb3cb628"
    # api_key = "c3a94aff312e2c3007b9c65a1fe6f8c819dbfda5baf2fad6fd8e47f7e427714c"
    # api_key = "f839fb8e0124a9ddfe807419fd686c5ec6edee19a1892854153a9d420e0655ac"
    api_key = "b293a49f3e804be4fce361b0b18250565b8adebb7c5e7bac83a00fa20f6e5a4c"
    oauth_token = "your_oauth_token"

    task_list = [
        master_openapi_gateway_func(email, api_key, oauth_token, 'sense', 'gateway_requests'),
        master_openapi_gateway_func(email, api_key, oauth_token, 'cascade', 'gateway_requests'),
        master_openapi_gateway_func(email, api_key, oauth_token, 'nft', 'gateway_requests'),
        master_openapi_gateway_func(email, api_key, oauth_token, 'sense', 'gateway_results'),
        master_openapi_gateway_func(email, api_key, oauth_token, 'cascade', 'gateway_results'),
        master_openapi_gateway_func(email, api_key, oauth_token, 'nft', 'gateway_results')
    ]

    responses = await asyncio.gather(*task_list)
    print("All tasks completed")
    for response in responses:
        print(response)


if __name__ == "__main__":
    asyncio.run(main())
