import json
from typing import Any
from urllib.parse import quote
import logging

import boto3
from botocore.exceptions import ClientError
from pydantic import PostgresDsn

logger = logging.getLogger(__name__)


def connect_to_secrets_manager(region: str):
    if not region:
        raise ValueError("AWS_REGION_NAME is not set")

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region
    )
    return client


def add_item_to_secret_in_secret_manager(region: str, secret_name: str, secret_key: str, secret_value: str):
    client = connect_to_secrets_manager(region)
    try:
        # Retrieve the existing secret
        response = client.get_secret_value(SecretId=secret_name)

        # Parse the existing secret JSON string (if it exists)
        if 'SecretString' in response:
            existing_secret = json.loads(response['SecretString'])
        else:
            existing_secret = {}

        # Add the new key-value pair to the existing secret
        existing_secret[secret_key] = secret_value

        # Convert the updated secret back to JSON string
        updated_secret_json = json.dumps(existing_secret)

        # Update the secret with the additional key-value pair
        response = client.update_secret(
            SecretId=secret_name,
            SecretString=updated_secret_json
        )
    except ClientError as e:
        logger.error(f'Failed to add "{secret_key}" to to secret "{secret_name}".')
        raise e
    # Check the response for errors
    if response['ResponseMetadata']['HTTPStatusCode'] != 200:
        logger.error(f'Failed to add "{secret_key}" to to secret "{secret_name}".')
        raise ValueError(f'Failed to add "{secret_key}" to to secret "{secret_name}".')

    logger.info(f'Successfully added key "{secret_key}" to the secret "{secret_name}"')


def get_secret_string_from_secret_manager(region_name, secret_id) -> Any:
    # Get a Secrets Manager client
    client = connect_to_secrets_manager(region_name)
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_id)
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret_json = json.loads(get_secret_value_response["SecretString"])
    if not secret_json:
        raise ValueError(f"Cannot get {secret_id} values from AWS secret manager")
    return secret_json


def get_database_url_from_secret_manager(region_name, secret_creds_id, secret_params_id) -> Any:
    secret_json = get_secret_string_from_secret_manager(region_name, secret_creds_id)
    if secret_params_id:
        secret_params_json = get_secret_string_from_secret_manager(region_name, secret_params_id)
        if secret_params_json:
            secret_json.update(secret_params_json)

    url_encoded_password = quote(secret_json["password"])

    return PostgresDsn.build(
        scheme="postgresql",
        username=secret_json["username"],
        port=secret_json["port"],
        password=url_encoded_password,
        host=secret_json["host"],
        path=f"{secret_json['dbname']}",
    )
