# Pastel Network Open API Gateway Introductory Builder's Guide.

### [Pastel Testnet API Gateway](https://testnet.gateway-api.pastel.network/)

Current URL: https://testnet.gateway-api.pastel.network/

Pastel Network's OpenAPI Gateway provides Web3 developers with easy, robust, and reliable access to the Pastel Network and its underlying decentralized protocols via a lightweight, centralized service. For more information on how the Gateway works, please see visit our Swagger docs [here](https://testnet.gateway-api.pastel.network/).

## Gateway Concepts

### Gateway Requests
A `gateway_request` allows users to submit via Gateway a set of one or more files to be stored in Cascade or one or more media files to be submitted to Sense.

Each `gateway_request` has a corresponding `gateway_request_id` that uniquely identifies it globally. The `gateway_request_id` is available to the user the moment a `gateway_request` is submitted. Users do not need to wait a while for a request to propagate to the underlying Pastel blockchain itself.

The following items are returned by the Gateway for each `gateway_request`:

- `current_status` of the request of type:
    - `gateway_request_pending`
    - `gateway_request_successful`
    - `gateway_request_failed`
- A set of `status_messages` which provide the user with fine-grained information about the state of a given gateway_request and include the following:
    - “The gateway_request has been received by OpenAPI Gateway and is pending submission to the Pastel Network”
    - “The gateway_request has been submitted to the Pastel Network and is currently being processed.”
    - “The gateway_request has been successfully processed by the Pastel Network and the corresponding Registration Ticket has been included in block <block_height> with registration transaction id <registration_ticket_txid>”
    - “The gateway_request has been successfully finalized and activated on the Pastel Network at block <block_height> with activation transaction id <activation_ticket_txid>”
    - *In the case of a Cascade* `gateway_request`*, there will also be an additional status message: “*The file has been successfully stored (pinned) in IPFS, and can be retrieved with the following identifier: /ipfs/<ipfs_identifier>”

### Gateway Results
A `gateway_result` refers to the output generated from a `gateway_request`, which contains various pieces of metadata. 

A single `gateway_request` can generate multiple `gateway_result` objects, and each `gateway_result` has a corresponding `gateway_result_id` that uniquely identifies it globally. 

Users can obtain a list of `gateway_result_id` objects from the corresponding `gateway_request_id`.

The following metadata fields are returned by the OpenAPI Gateway from a `gateway_result`; some fields are only included depending on the `gateway_request_id` type:

- File Name
- File Type
- Gateway Result ID
- Datetime Created
- Datetime Last Updated
- Gateway Request Status
- Retry Attempt Number
- Status Message
- Registration Ticket TXID
- Activation Ticket TXID
- IPFS Link (another backup to Cascade)
- AWS Link (another backup to Cascade)

*Note: Information for any `gateway_result_id` will only be provided if the `current_status` is `gateway_request_successful`; if `current_status` is `gateway_request_failed`, then the OpenAPI Gateway will automatically resubmit the request for the user. If the `current_status` is `gateway_request_pending` or  `gateway_request_failed`, then the user will receive a placeholder informing them that results are `pending`.*

### 1. Accessing the Gateway

- Obtain OAuth2 token login credentials from the Foundation and login [here](https://testnet.gateway-api.pastel.network/#/login/login_access_token_api_v1_login_access_token_post) 

  ```
  POST /api/v1/login/access-token
  ```
  
### 2. Obtaining API Credentials

- Create a new API Key [here](https://testnet.gateway-api.pastel.network/#/api_keys/create_apikey_api_v1_api_keys__post)

  ```
  POST /api/v1/api_keys/
  ```

- After api keys from the service after getting an access token

  https://testnet.gateway-api.pastel.network/#/api_keys/read_apikeys_api_v1_api_keys__get


- Please include these additional headers for access token, and api key to each requests

  ```
  Authorization: Bearer `${accessToken}`
  apiKey: `${apiKey}`
  ```

### 3. Using Cascade 



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
