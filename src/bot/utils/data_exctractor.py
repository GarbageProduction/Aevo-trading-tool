import time

from eth_account.messages import encode_structured_data
from eth_account.datastructures import SignedMessage
from eth_account import Account
from eth_abi import encode
from web3 import AsyncWeb3

from eip712_structs import (
    make_domain,
    Address,
)

from src.aevo.order import Order


def get_signatures(
        web3: AsyncWeb3,
        wallet_address: str,
        account: Account
) -> tuple[str, SignedMessage, str]:
    new_acc = web3.eth.account.create()
    signing_key = new_acc.address
    signing_private = new_acc.key.hex()

    register_data = {
        "name": "Aevo Mainnet",
        "version": "1",
        "chainId": 1
    }
    register_types = {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"}
        ],
        "Register": [
            {"name": "key", "type": "address"},
            {"name": "expiry", "type": "uint256"}
        ],

    }
    register_values = {
        "key": signing_key,
        "expiry": int(time.time() + 10000)
    }
    register_structured_data = {
        "types": register_types,
        "primaryType": "Register",
        "domain": register_data,
        "message": register_values
    }

    msg = encode_structured_data(register_structured_data)
    account_signature = account.sign_message(msg).signature.hex()

    signing_key_signature = web3.eth.account.sign_typed_data(
        domain_data={
            "name": "Aevo Mainnet",
            "version": "1",
            "chainId": 1,
        },
        message_types={
            "SignKey": [
                {"name": "account", "type": "address"}
            ]
        },
        message_data={
            "account": wallet_address
        },
        private_key=signing_private

    )
    signing_key_signature = signing_key_signature.signature.hex()

    return signing_key, account_signature, signing_key_signature


def sign_withdraw(
        web3: AsyncWeb3,
        collateral: str,
        to: str,
        amount: int,
        salt: int,
        private_key: str,
        socket_fees: int,
        socket_msg_gas_limit: int,
        socket_connector: str
) -> str:
    data = encode(
        ["uint256", "uint256", "address"],
        [socket_fees, socket_msg_gas_limit, socket_connector]
    )

    key_signature = web3.eth.account.sign_typed_data(
        domain_data={
            "name": "Aevo Mainnet",
            "version": "1",
            "chainId": 42161,
        },
        message_types={
            "Withdraw": [
                {"name": "collateral", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "salt", "type": "uint256"},
                {"name": "data", "type": "bytes32"}
            ]
        },
        message_data={
            "collateral": web3.to_checksum_address(collateral),
            "to": web3.to_checksum_address(to),
            "amount": str(amount),
            "salt": str(salt),
            "data": web3.keccak(data)
        },
        private_key=private_key

    )

    signature = key_signature.signature.hex()
    return signature


def sign_staking_withdraw(
        web3: AsyncWeb3,
        private_key: str,
        collateral: str,
        to: str,
        amount: int,
        salt: int
) -> str:
    key_signature = web3.eth.account.sign_typed_data(
        domain_data={
            "name": "Aevo Mainnet",
            "version": "1",
            "chainId": 1,
        },
        message_types={
            "Transfer": [
                {"name": "collateral", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "salt", "type": "uint256"}
            ]
        },
        message_data={
            "collateral": web3.to_checksum_address(collateral),
            "to": web3.to_checksum_address(to),
            "amount": str(amount),
            "salt": str(salt),
        },
        private_key=private_key

    )

    signature = key_signature.signature.hex()
    return signature


def sign_staking(
        web3: AsyncWeb3,
        private_key: str,
        collateral: str,
        to: str,
        amount: int,
        salt: int
) -> str:
    key_signature = web3.eth.account.sign_typed_data(
        domain_data={
            "name": "Aevo Mainnet",
            "version": "1",
            "chainId": 42161,
        },
        message_types={
            "Transfer": [
                {"name": "collateral", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "salt", "type": "uint256"}
            ]
        },
        message_data={
            "collateral": web3.to_checksum_address(collateral),
            "to": web3.to_checksum_address(to),
            "amount": str(amount),
            "salt": str(salt),
        },
        private_key=private_key

    )

    signature = key_signature.signature.hex()
    return signature


def sign_order(
        wallet_address: Address,
        private_key: str,
        is_buy: bool,
        amount: float,
        limit_price: int,
        salt: int,
        timestamp: float,
        instrument_id: int
) -> SignedMessage:
    order_struct = Order(
        maker=wallet_address,
        isBuy=is_buy,
        limitPrice=int(limit_price),
        amount=int(amount),
        salt=salt,
        instrument=instrument_id,
        timestamp=int(timestamp)
    )

    domain = make_domain(name='Aevo Mainnet', version='1', chainId=1)
    signable_bytes = AsyncWeb3.keccak(order_struct.signable_bytes(domain=domain))
    return Account._sign_hash(signable_bytes, private_key).signature.hex()
