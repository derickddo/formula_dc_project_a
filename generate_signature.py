import hmac
import hashlib
import json

# ====================================================================
# CONFIGURATION
# IMPORTANT: Replace this with your actual secret key.
# This must be the same key used by the webhook sender and receiver.
# ====================================================================
SECRET_KEY = 'super-secret-key-123'


def generate_hmac_signature(payload, secret_key):
    """
    Generates an HMAC-SHA256 signature from a JSON payload.

    Args:
        payload (dict): The dictionary representation of the JSON payload.
        secret_key (str): The secret key for HMAC hashing.

    Returns:
        str: The hexadecimal HMAC-SHA256 signature.
    """
    # 1. Canonicalize the payload.
    # We re-dump the dictionary to a string with a consistent format:
    # - `sort_keys=True` ensures the key order is always the same.
    # - `separators=(',', ':')` removes any extra whitespace.
    canonical_payload = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    
    # Encode both the key and the payload to bytes, which is required by hmac.new()
    payload_bytes = canonical_payload.encode('utf-8')
    key_bytes = secret_key.encode('utf-8')
    
    # 2. Generate the HMAC hash.
    # We use the SHA256 hashing algorithm.
    hmac_hash = hmac.new(key_bytes, payload_bytes, hashlib.sha256)
    
    # 3. Return the hexadecimal representation of the hash.
    return hmac_hash.hexdigest()


# ====================================================================
# SCRIPT EXECUTION
# ====================================================================

# This is the JSON payload you provided, represented as a Python dictionary.
webhook_payload = {
    "provider_reference": "momo_txn_456def789",
    "order_id": "70307493-246f-4c44-8f08-de30d576653d",
    "status": "success"
}

# Call the function to generate the signature
generated_signature = generate_hmac_signature(webhook_payload, SECRET_KEY)

# Print the canonical string and the final signature
print(f"Canonical Payload String:\n{json.dumps(webhook_payload, separators=(',', ':'), sort_keys=True)}\n")
print(f"Generated HMAC-SHA256 Signature:\n{generated_signature}")
