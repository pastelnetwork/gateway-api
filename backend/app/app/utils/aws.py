import json

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


def connect_to_secrets_manager():
    if not settings.AWS_SECRET_MANAGER_REGION:
        raise ValueError("AWS_REGION_NAME is not set")

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=settings.AWS_SECRET_MANAGER_REGION
    )
    return client


def add_item_to_secret(secret_name, secret_key, secret_value):
    client = connect_to_secrets_manager()
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
        if e.response['Error']['Code'] == 'ResourceExistsException':
            print(f'Secret "{secret_name}" already exists.')
        else:
            raise e
    else:
        # Check the response for errors
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print(f'Successfully added key "{secret_key}" to the secret "{secret_name}"')
        else:
            print('Failed to add key-value pair to the secret')
        print(f'Successfully created secret "{secret_name}".')


def store_pastelid(pastel_id, pastelid_secret):
    add_item_to_secret(settings.AWS_SECRET_MANAGER_PASTEL_IDS, pastel_id, pastelid_secret)