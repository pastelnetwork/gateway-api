# Gateway: Introductory Builder's Guide.

### [Pastel Testnet API Gateway](https://testnet.gateway-api.pastel.network/)

#### Pastel Network's OpenAPI Gateway provides Web3 developers with easy, robust, and reliable access to the Pastel Network and its underlying decentralized protocols via a lightweight, centralized service. For more information on how the Gateway works, please see visit our Swagger docs [here](https://testnet.gateway-api.pastel.network/).

Current URL: https://testnet.gateway-api.pastel.network/

## Introductory Concepts

### Gateway Requests
A `gateway_request` allows users to upload one or more files to Cascade or Sense.

Each `gateway_request` has a corresponding `gateway_request_id` that uniquely identifies it globally. The `gateway_request_id` is available to the user the moment a `gateway_request` is submitted. Users do not need to wait a while for a request to propagate to the underlying Pastel blockchain itself.

Each `gateway_request` has a `current_status` of:
* `gateway_request_pending`
* `gateway_request_successful`
* `gateway_request_failed`
* `gateway_request_rejected`

> Where: 
    * `gateway_request_pending` - the request is processed by gateway. It can be that the original request has failed, and gateway is still trying to re-process it.
    * `gateway_request_failed` - the request failed and cannot be reprocessed automatically, customer must resubmit failed files
    * `gateway_request_rejected` - request was rejected by gateway or Pastel network as invalid

> For `current_status` of `gateway_request_pending` and `gateway_request_successful` the response will have and `request_id` that can be used to get more info about request in the future

### Gateway Results
A `gateway_result` refers to the output generated from a `gateway_request` for an individual file which contains various pieces of metadata. 

A single `gateway_request` can generate multiple `gateway_result` objects, and each `gateway_result` has a corresponding `gateway_result_id` that uniquely identifies it globally. 

Users can obtain a list of `gateway_result_id` objects from the corresponding `gateway_request_id`.

The following metadata fields are returned from a `gateway_result` in JSON:

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

*Note: Information for any `gateway_result_id` will only be provided if the `current_status` is `gateway_request_successful`*

## Accessing Gateway

Login to the Gatway using your credentials from the Foundation (username and password) and obtain an OAuth2 compataible token [here](https://testnet.gateway-api.pastel.network/#/login/login_access_token_api_v1_login_access_token_post) 

  ```
  POST /api/v1/login/access-token
  ```
  
Create a new API Key [here](https://testnet.gateway-api.pastel.network/#/api_keys/create_apikey_api_v1_api_keys__post)

  ```
  POST /api/v1/api_keys/
  ```
  
View all existing API Keys [here](https://testnet.gateway-api.pastel.network/#/api_keys/read_apikeys_api_v1_api_keys__get)

  ```
  GET /api/v1/api_keys/
  ```

For each `gateway_request`, include the following headers:

  ```
  Authorization: Bearer `${accessToken}`
  apiKey: `${apiKey}`
  ```

## Cascade Requests

### Start processing

Upload one or more files to Cascade [here](https://testnet.gateway-api.pastel.network/#/cascade/process_request_api_v1_cascade__post)

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

### Get information about request or individual result

```
GET /api/v1/cascade/gateway_requests/{gateway_request_id}
```

Method returnes the same JSON as POST above

```
{
  "request_id": "string",
  "request_status": "PENDING",
  "results": [
    {
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
     ...
    }
  ]
}
```


```
GET /api/v1/cascade/gateway_results/{gateway_result_id}
```

Response

```
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
```

### Get registered file

```
/api/v1/cascade/stored_file/{gateway_result_id}
```

Response is registerd file. 
> Note: this method can take some time, when called for the first time, as it will be searchung for the file in Pastel Network


## Sense Requests

### Start processing

Upload one or more files to Sense [here](https://testnet.gateway-api.pastel.network/#/sense/process_request_api_v1_sense__post)

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

### Get information about request or individual result

```
GET /api/v1/sense/gateway_requests/{gateway_request_id}
```

Method returnes the same JSON as POST above

```
{
  "request_id": "string",
  "request_status": "PENDING",
  "results": [
    {
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
      "error": "string"
     }
     ...
    }
  ]
}
```


```
GET /api/v1/sense/gateway_results/{gateway_result_id}
```

Response

```
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
      "error": "string"
}
```

### Get sense data of the file

To get sense data from the Pastel Network about processd file

```
/api/v1/sense/parsed_output_file/{gateway_result_id}
```

The response will be a JOSN of the format, like this:
```
{
  "pastel_block_hash_when_request_submitted": "string",
  "pastel_block_height_when_request_submitted": "string",
  "utc_timestamp_when_request_submitted": "YYYY-MM-DD hh:mm:ss",
  "pastel_id_of_submitter": "string",
  "pastel_id_of_registering_supernode_1": "string",
  "pastel_id_of_registering_supernode_2": "string",
  "pastel_id_of_registering_supernode_3": "string",
  "is_pastel_openapi_request": boolean,
  "open_api_subset_id_string": "string",
  "dupe_detection_system_version": "2.3.1",
  "is_likely_dupe": boolean,
  "is_rare_on_internet": boolean,
  "overall_rareness_score ": double,
  "pct_of_top_10_most_similar_with_dupe_prob_above_25pct": 0,
  "pct_of_top_10_most_similar_with_dupe_prob_above_33pct": 0,
  "pct_of_top_10_most_similar_with_dupe_prob_above_50pct": 0,
  "rareness_scores_table_json_compressed_b64": {
    "image_hash": {
      "0": "string",
...
      "9": "string",
    },
    "register_time": {
      "0": [
        [
          "data-time"
        ]
      ],
...
      "9": [
        [
          "data-time"
        ]
      ]
    },
    "cos_scores": {
      "0": double,
...
      "9": double
    },
    "hoef_scores": {
      "0": double,
...
      "9": double
    },
    "hsic_scores": {
      "0": double,
...
      "9": double

    },
    "cos_gains": {
      "0": double,
...
      "9": double
    },
    "hoef_gains": {
      "0": double,
...
      "9": double
    },
    "hsic_gains": {
      "0": double,
...
      "9": double
    },
    "final_dupe_probability": {
      "0": double,
...
      "9": double
    },
    "is_likely_dupe": {
      "0": boolean,
...
      "9": boolean
    },
    "thumbnail": {
      "0": [
        [
        "base64-encioded"
        ]
      ],
...
      "9": [
        [        
        "base64-encioded"
        ]
      ]
    },
    "match_type": {
      "0": "Image",
...
      "9": "Image"
    }
  },
  "internet_rareness": {
    "rare_on_internet_summary_table_as_json_compressed_b64": {
      "title": {
        "2": "string",
...
      },
      "description_text": {
        "2": "",
...
      },
      "original_url": {
        "2": "https://...",
...
      },
      "google_cached_url": {
        "2": "https://...",
...
      },
      "date_string": {
        "2": "",
...
      },
      "resolution_string": {
        "2": "",
...
      },
      "img_alt_string": {
        "2": "",
...
      },
      "img_src_string": {
        "2": "base64",
...
      },
      "search_result_ranking": {
        "2": 2,
...
      }
    },
    "rare_on_internet_graph_json_compressed_b64": {
      "nodes": [
      ],
      "links": [
      ]
    },
    "alternative_rare_on_internet_dict_as_json_compressed_b64": {
      "list_of_image_src_strings": [
      ],
      "list_of_image_alt_strings": [
      ],
      "list_of_images_as_base64": [
      ],
      "list_of_sha3_256_hashes_of_images_as_base64": [
      ],
      "list_of_href_strings": [
      ],
      "alternative_rare_on_internet_graph_json_compressed_b64": ""
    },
    "min_number_of_exact_matches_in_page": int,
    "earliest_available_date_of_internet_results": "NA"
  },
  "open_nsfw_score": double,
  "alternative_nsfw_scores": {
    "drawings": double,
    "hentai": double,
    "neutral": double,
    "porn": double,
    "sexy": double
  },
  "image_fingerprint_of_candidate_image_file": [
  ],
  "hash_of_candidate_image_file": "string"
}
```
