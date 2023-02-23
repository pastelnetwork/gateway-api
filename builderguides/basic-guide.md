# Gateway: Introductory Builder's Guide.

### [Pastel Testnet API Gateway](https://testnet.gateway-api.pastel.network/)

Current URL: https://testnet.gateway-api.pastel.network/

Pastel Network's OpenAPI Gateway provides Web3 developers with easy, robust, and reliable access to the Pastel Network and its underlying decentralized protocols via a lightweight, centralized service. For more information on how the Gateway works, please see visit our Swagger docs [here](https://testnet.gateway-api.pastel.network/).

## Introductory Concepts

### Gateway Requests
A `gateway_request` allows users to submit via Gateway a set of one or more files to be stored in Cascade or one or more media files to be submitted to Sense.

Each `gateway_request` has a corresponding `gateway_request_id` that uniquely identifies it globally. The `gateway_request_id` is available to the user the moment a `gateway_request` is submitted. Users do not need to wait a while for a request to propagate to the underlying Pastel blockchain itself.

The following items are returned Gateway for each `gateway_request`:

- `current_status` of the request:
    - `gateway_request_pending`
    - `gateway_request_successful`
    - `gateway_request_failed`
- A set of `status_messages` which provide the user with information about the state of a given gateway_request such as:
    - “The gateway_request has been received by OpenAPI Gateway and is pending submission to the Pastel Network”
    - “The gateway_request has been submitted to the Pastel Network and is currently being processed.”
    - “The gateway_request has been successfully processed by the Pastel Network and the corresponding Registration Ticket has been included in block <block_height> with registration transaction id <registration_ticket_txid>”
    - “The gateway_request has been successfully finalized and activated on the Pastel Network at block <block_height> with activation transaction id <activation_ticket_txid>”
    - *In the case of a Cascade* `gateway_request`*, there will also be an additional status message: “*The file has been successfully stored (pinned) in IPFS, and can be retrieved with the following identifier: /ipfs/<ipfs_identifier>”

### Gateway Results
A `gateway_result` refers to the output generated from a `gateway_request`, which contains various pieces of metadata. 

A single `gateway_request` can generate multiple `gateway_result` objects, and each `gateway_result` has a corresponding `gateway_result_id` that uniquely identifies it globally. 

Users can obtain a list of `gateway_result_id` objects from the corresponding `gateway_request_id`.

The following metadata fields are returned from a `gateway_result`. Certain fields are only included depending on the `gateway_request_id` type:

    {
      "file_name": "string",
      "file_type": "string",
      "result_id": "string",
      "created_at": "yyyy-MM-ddTHH:mm:ss",
      "last_updated_at": "yyyy-MM-ddTHH:mm:ss",
      "result_status": "<STATUS>",
      "status_messages": [
        "string"
      ],
      "retry_num": <int>,
      "registration_ticket_txid": "string", //Pastel Network Registration TX ID 
      "activation_ticket_txid": "string", //Pastel Network Activation TX ID 
      "ipfs_link": "string",
      "aws_link": "string",
      "other_links": "string",
      "error": "string"
    }

*Note: Information for any `gateway_result_id` will only be provided if the `current_status` is `gateway_request_successful`; if `current_status` is `gateway_request_failed`, then the OpenAPI Gateway will automatically resubmit the request for the user. If the `current_status` is `gateway_request_pending` or  `gateway_request_failed`, then the user will receive a placeholder informing them that results are `pending`.*

## Accessing Gateway

- Login to the Gatway using your credentials from the Foundation (username and password) and obtain an OAuth2 compataible token [here](https://testnet.gateway-api.pastel.network/#/login/login_access_token_api_v1_login_access_token_post) 

  ```
  POST /api/v1/login/access-token
  ```
  
- Create a new API Key [here](https://testnet.gateway-api.pastel.network/#/api_keys/create_apikey_api_v1_api_keys__post)

  ```
  POST /api/v1/api_keys/
  ```
  
- View all existing API Keys [here](https://testnet.gateway-api.pastel.network/#/api_keys/read_apikeys_api_v1_api_keys__get)

  ```
  GET /api/v1/api_keys/
  ```

- For each `gateway_request`, include the following headers:

  ```
  Authorization: Bearer `${accessToken}`
  apiKey: `${apiKey}`
  ```

## Cascade Requests

## Upload one or more files to Cascade [here](https://testnet.gateway-api.pastel.network/#/cascade/process_request_api_v1_cascade__post)

  ```
  POST /api/v1/cascade/
  ```
  
This method returns JSON including the ```request_id```, ```request_status```, and JSON of ```results``` for each file:

```
{
  "request_id": "string",
  "request_status": "PENDING",
  "results": [
    {
    }
  ]
}
```

## Sense Requests

## Upload one or more files to Sense [here](https://testnet.gateway-api.pastel.network/#/sense/process_request_api_v1_sense__post)

  ```
  POST /api/v1/sense/
  ```
  
This method returns JSON including the ```request_id```, ```request_status```, and JSON of ```results``` for each file:

```
{
  "request_id": "string",
  "request_status": "PENDING",
  "results": [
    {
    }
  ]
}
```

