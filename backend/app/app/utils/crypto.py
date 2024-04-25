from secp256k1 import PublicKey
import base58
import hashlib


network_prefixes = {"mainnet": b'\x04\x88\xb2\x1e',
                    "testnet": b'\x04\x35\x87\xcf',
                    "devtest": b'\x04\x35\x87\xcf'}


# def create_signature(message, account_id):
#     """ Sign a message using a private key. """
#     pub_key, _ = decode_ext_pub_key(account_id)
#     signature = priv_key.ecdsa_sign(message)
#     return signature


async def create_sha256_hash(message):
    message_bytes = message.encode('utf-8')
    hash_object = hashlib.sha256()
    hash_object.update(message_bytes)
    return hash_object.digest()  # Return bytes


async def verify_signature(message, signature, account_id):
    """ Verify a signature based on the original message and public key. """
    pub_key_bytes = await decode_base58(account_id)
    signature_bytes_der = await decode_base58(signature)
    pub_key = PublicKey(pub_key_bytes, raw=True)
    sig = pub_key.ecdsa_deserialize(signature_bytes_der)

    hash_bytes = await create_sha256_hash(message)
    return pub_key.ecdsa_verify(hash_bytes, sig)


async def decode_base58(pub_key_base58):
    """ Decode a base58-encoded public key. """
    return base58.b58decode(pub_key_base58)


async def decode_base58_check(address):
    """Decode a base58-encoded string with checksum verification."""
    decoded = base58.b58decode(address)
    if len(decoded) < 4:
        return None
    # Split the data and checksum
    data, checksum = decoded[:-4], decoded[-4:]
    # Calculate the checksum of the data
    hash_ = hashlib.sha256(hashlib.sha256(data).digest()).digest()
    if checksum != hash_[:4]:
        return None
    return data


async def decode_ext_pub_key(str_key) -> tuple:
    """Decode an extended public key from a base58-encoded string."""
    decoded_data = decode_base58_check(str_key)
    if decoded_data is None:
        return None, None
    # Check and strip the prefix
    for network, network_prefix in network_prefixes.items():
        prefix_len = len(network_prefix)
        if decoded_data[:prefix_len] == network_prefix:
            # Extract and return the key data after the prefix
            return decoded_data[prefix_len:], network
    return None, None
