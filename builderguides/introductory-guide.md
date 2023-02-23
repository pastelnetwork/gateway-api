# Welcome to Pastel Network's Open API Gateway! See details below on how to get started today.

### Testnet Gateway URL

https://testnet.gateway-api.pastel.network/

### Accessing the Gateway

- Obtain OAuth2 token login credentials from the Foundation and login [here](https://testnet.gateway-api.pastel.network/#/login/login_access_token_api_v1_login_access_token_post) 
-   POST /api/v1/login/access-token
  
### Accessing the Gateway
- List api keys from the service after getting an access token

  https://testnet.gateway-api.pastel.network/#/api_keys/read_apikeys_api_v1_api_keys__get

- If there's no api key found, please create a new api key

  https://testnet.gateway-api.pastel.network/#/api_keys/create_apikey_api_v1_api_keys__post

- Please include these additional headers for access token, and api key to each requests

  ```
  Authorization: Bearer `${accessToken}`
  apiKey: `${apiKey}`
  ```

### How to upload files to Cascade

https://testnet.gateway-api.pastel.network/#/cascade/process_request_api_v1_cascade__post

It returns the data including result_status, ipfs_link, an d etc
Please wait until result_status is SUCCESS.

### How to upload files to Sense

https://testnet.gateway-api.pastel.network/#/sense/process_request_api_v1_sense__post

Same with the cascade service. Please wait until result_status is SUCCESS.

### How to get cascade details

https://testnet.gateway-api.pastel.network/#/cascade/get_result_by_result_id_api_v1_cascade_gateway_results__gateway_result_id__get
https://opennode-fastapi-testnet.pastel.network/#/Ticket%20Methods/get_ticket_by_txid_get_ticket_by_txid__txid__get

You can get the details of cascade ticket using these two API endpoints.

### How to get sense details

https://testnet.gateway-api.pastel.network/#/sense/get_parsed_output_file_api_v1_sense_parsed_output_file__gateway_result_id__get

You can get the details of sense ticket with this API.

### Service URL

https://testnet.gateway-api.pastel.network/

### How to authorize to the gateway

- Get access token from the service with correct username, and password

  https://testnet.gateway-api.pastel.network/#/login/login_access_token_api_v1_login_access_token_post

- List api keys from the service after getting an access token

  https://testnet.gateway-api.pastel.network/#/api_keys/read_apikeys_api_v1_api_keys__get

- If there's no api key found, please create a new api key

  https://testnet.gateway-api.pastel.network/#/api_keys/create_apikey_api_v1_api_keys__post

- Please include these additional headers for access token, and api key to each requests

  ```
  Authorization: Bearer `${accessToken}`
  apiKey: `${apiKey}`
  ```

### How to upload files to Cascade

https://testnet.gateway-api.pastel.network/#/cascade/process_request_api_v1_cascade__post

It returns the data including result_status, ipfs_link, an d etc
Please wait until result_status is SUCCESS.

### How to upload files to Sense

https://testnet.gateway-api.pastel.network/#/sense/process_request_api_v1_sense__post

Same with the cascade service. Please wait until result_status is SUCCESS.

### How to get cascade details

https://testnet.gateway-api.pastel.network/#/cascade/get_result_by_result_id_api_v1_cascade_gateway_results__gateway_result_id__get
https://opennode-fastapi-testnet.pastel.network/#/Ticket%20Methods/get_ticket_by_txid_get_ticket_by_txid__txid__get

You can get the details of cascade ticket using these two API endpoints.

### How to get sense details

https://testnet.gateway-api.pastel.network/#/sense/get_parsed_output_file_api_v1_sense_parsed_output_file__gateway_result_id__get

You can get the details of sense ticket with this API.
