import requests
import json

def get_base_url() -> str:
    return 'http://localhost:9000/api/v1'

def get_api_key() -> str:
    return '04b5bb3300da7e41c18530d3ad093f5c7138e5dffd37b4397e0113b1b0bd7a96'

def get_file_name_and_path() -> (str, str):
    return 'Dicklesworthstone_Pastel_Network_self_healing_decentralized_sto_6fdd92b4-e805-4025-95b8-1820b195a8d8.png',\
        '/Users/alexey/Downloads/Dicklesworthstone_Pastel_Network_self_healing_decentralized_sto_6fdd92b4-e805-4025-95b8-1820b195a8d8.png'

def generate_new_nft_details() -> str :
    nft_details = {
        "creator_name": "Super Artist",
        "creator_website_url": "SuperArtist.art",
        "description": "Super Art 2",
        "green": true,
        "issued_copies": 1,
        "keywords": "Super,Art, 2",
        "maximum_fee": 0,
        "name": "SuperArt2",
        "royalty": 0.2,
        "series_name": "",
        "youtube_url": ""
    }
    return json.dumps(nft_details)

def get_is_publicly_accessible() -> bool:
    return True

def get_collection_txid() -> str:
    return ''

def validate_result_output(json_data, file_name, file_type, make_publicly_accessible, collection_act_txid):
    try:
        # Load JSON data
        data = json.loads(json_data)

        # Check that file_name and make_publicly_accessible match the provided values
        if (data.get('file_name') == file_name and
            data.get('file_type') == file_type and
            data.get('collection_act_txid', '') == collection_act_txid and
            data.get('make_publicly_accessible') == make_publicly_accessible):

            # If the checks pass, return original_file_ipfs_link and result_id
            return data.get('original_file_ipfs_link'), data.get('result_id')
        else:
            return False
    except json.JSONDecodeError:
        # The input is not valid JSON
        return False
    except Exception as e:
        # Some other error occurred
        return False

def process_new_nft_request():
    file_name, file_path = get_file_name_and_path()
    is_publicly_accessible = get_is_publicly_accessible()
    collection_txid = get_collection_txid()
    url = f"{get_base_url()}/nft?" \
          f"make_publicly_accessible={is_publicly_accessible}&" \
          f"collection_act_txid={collection_txid}&" \
          f"open_api_group_id=pastel"
    payload = {'nft_details_payload': generate_new_nft_details()}
    files=[
        ('file',(file_name, open(file_path,'rb'), 'image/png'))
    ]
    headers = {
      'Content-Type': 'multipart/form-data',
      'Accept': 'application/json',
      'api_key': get_api_key()
    }
    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    orig_ipfs_link, result_id = \
        validate_result_output(response.text, file_name, 'image/png', is_publicly_accessible, collection_txid)
    print(response.text)
    return result_id

def get_result(result_id: str, result_type: str):
    url = f"{get_base_url()}/{result_type}/gateway_results/{result_id}"
    payload = {}
    headers = {
        'Accept': 'application/json',
        'api_key': get_api_key()
    }
    response = requests.request("GET", url, headers=headers, data=payload)
    print(response.text)

def nft_runner():
    result_id = process_new_nft_request()
    get_result(result_id, 'nft')
