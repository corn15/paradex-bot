import hashlib
from enum import IntEnum
from typing import Dict, Tuple
from eth_account.messages import encode_structured_data
from web3.auto import w3
from starknet_py.common import int_from_bytes
from starknet_py.hash.address import compute_address
from starknet_py.hash.selector import get_selector_from_name
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.signer.stark_curve_signer import KeyPair
from starknet_py.utils.typed_data import TypedData
from starkware.crypto.signature.signature import EC_ORDER
from helpers.account import Account


def build_auth_message(chainId: int, now: int, expiry: int) -> TypedData:
    message = {
        "message": {
            "method": "POST",
            "path": "/v1/auth",
            "body": "",
            "timestamp": now,
            "expiration": expiry,
        },
        "domain": {"name": "Paradex", "chainId": hex(chainId), "version": "1"},
        "primaryType": "Request",
        "types": {
            "StarkNetDomain": [
                {"name": "name", "type": "felt"},
                {"name": "chainId", "type": "felt"},
                {"name": "version", "type": "felt"},
            ],
            "Request": [
                {"name": "method", "type": "felt"},
                {"name": "path", "type": "felt"},
                {"name": "body", "type": "felt"},
                {"name": "timestamp", "type": "felt"},
                {"name": "expiration", "type": "felt"},
            ],
        },
    }
    return message

def build_stark_key_message(chain_id: int) -> TypedData:
    message = {
        "domain": {"name": "Paradex", "version": "1", "chainId": chain_id},
        "primaryType": "Constant",
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
            ],
            "Constant": [
                {"name": "action", "type": "string"},
            ],
        },
        "message": {
            "action": "STARK Key",
        },
    }
    return message


def sign_stark_key_message(eth_private_key: int, stark_key_message) -> str:
    encoded = encode_structured_data(primitive=stark_key_message)
    signed = w3.eth.account.sign_message(encoded, eth_private_key)
    return signed.signature.hex()


def grind_key(key_seed: int, key_value_limit: int) -> int:
    max_allowed_value = 2**256 - (2**256 % key_value_limit)
    current_index = 0

    def indexed_sha256(seed: int, index: int) -> int:
        def padded_hex(x: int) -> str:
            # Hex string should have an even
            # number of characters to convert to bytes.
            hex_str = hex(x)[2:]
            return hex_str if len(hex_str) % 2 == 0 else "0" + hex_str

        digest = hashlib.sha256(bytes.fromhex(padded_hex(seed) + padded_hex(index))).hexdigest()
        return int(digest, 16)

    key = indexed_sha256(seed=key_seed, index=current_index)
    while key >= max_allowed_value:
        current_index += 1
        key = indexed_sha256(seed=key_seed, index=current_index)

    return key % key_value_limit


def get_private_key_from_eth_signature(eth_signature_hex: str) -> int:
    r = eth_signature_hex[2 : 64 + 2]
    return grind_key(int(r, 16), EC_ORDER)


def derive_stark_key_from_eth_key(msg: str, eth_private_key: str) -> int:
    message_signature = sign_stark_key_message(eth_private_key, msg)
    private_key = get_private_key_from_eth_signature(message_signature)
    return private_key


def get_acc_contract_address_and_call_data(
    proxy_contract_hash: str, account_class_hash: str, public_key: str
) -> str:
    calldata = [
        int(account_class_hash, 16),
        get_selector_from_name("initialize"),
        2,
        int(public_key, 16),
        0,
    ]

    address = compute_address(
        class_hash=int(proxy_contract_hash, 16),
        constructor_calldata=calldata,
        salt=int(public_key, 16),
    )
    return hex(address)


def generate_paradex_account(
    paradex_config: Dict, eth_account_private_key_hex: str
) -> Tuple[str, str]:
    eth_chain_id = int(paradex_config['l1_chain_id'])
    stark_key_msg = build_stark_key_message(eth_chain_id)
    paradex_private_key = derive_stark_key_from_eth_key(stark_key_msg, eth_account_private_key_hex)
    paradex_key_pair = KeyPair.from_private_key(paradex_private_key)
    paradex_account_private_key_hex = hex(paradex_private_key)
    paradex_account_address = get_acc_contract_address_and_call_data(
        paradex_config['paraclear_account_proxy_hash'],
        paradex_config['paraclear_account_hash'],
        hex(paradex_key_pair.public_key),
    )
    return paradex_account_address, paradex_account_private_key_hex


def get_chain_id(chain_id: str):
    class CustomStarknetChainId(IntEnum):
        PRIVATE_TESTNET = int_from_bytes(chain_id.encode("UTF-8"))
    return CustomStarknetChainId.PRIVATE_TESTNET


def get_account(account_address: str, account_key: str, paradex_config: dict):
    client = FullNodeClient(node_url=paradex_config["starknet_fullnode_rpc_url"])
    key_pair = KeyPair.from_private_key(key=hex_to_int(account_key))
    chain = get_chain_id(paradex_config["starknet_chain_id"])
    account = Account(
        client=client,
        address=account_address,
        key_pair=key_pair,
        chain=chain,
    )
    return account


def hex_to_int(val: str):
    return int(val, 16)
