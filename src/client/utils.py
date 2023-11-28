from typing import Optional
from random import uniform
from asyncio import sleep

from eip712_structs import Address
from web3.contract import Contract
from web3.types import TxParams
from eth_typing import HexStr
from web3 import AsyncWeb3
from loguru import logger

from src.data import ERC20_ABI


async def approve_token(
        amount: float,
        private_key: str,
        from_token_address: str,
        spender: str,
        address_wallet: Address,
        web3: AsyncWeb3
) -> Optional[HexStr]:
    try:
        spender = web3.to_checksum_address(spender)
        contract = load_contract(from_token_address, web3, ERC20_ABI)
        allowance_amount = await check_allowance(web3, from_token_address, address_wallet, spender)

        if amount > allowance_amount:
            logger.debug('🛠️ | Approving token...')
            tx = await contract.functions.approve(
                spender,
                int(amount * 2)
            ).build_transaction(
                {
                    'chainId': await web3.eth.chain_id,
                    'from': address_wallet,
                    'nonce': await web3.eth.get_transaction_count(address_wallet),
                    'gasPrice': 0,
                    'gas': 0,
                    'value': 0
                }
            )

            gas_price = await add_gas_price(web3)
            tx['gasPrice'] = gas_price

            gas_limit = await add_gas_limit(web3, tx)
            tx['gas'] = gas_limit

            signed_tx = web3.eth.account.sign_transaction(tx, private_key=private_key)
            raw_tx_hash = await web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_receipt = await web3.eth.wait_for_transaction_receipt(raw_tx_hash)
            while tx_receipt is None:
                await sleep(1)
                tx_receipt = web3.eth.get_transaction_receipt(raw_tx_hash)
            tx_hash = web3.to_hex(raw_tx_hash)
            logger.success(f'✔️ | Token approved')
            await sleep(5)
            return tx_hash

    except Exception as ex:
        logger.error(f'Something went wrong | {ex}')


async def check_allowance(
        web3: AsyncWeb3,
        from_token_address: str,
        address_wallet: Address,
        spender: str
) -> Optional[int]:
    try:
        contract = web3.eth.contract(address=web3.to_checksum_address(from_token_address),
                                     abi=ERC20_ABI)
        amount_approved = await contract.functions.allowance(address_wallet, spender).call()
        return amount_approved

    except Exception as ex:
        logger.error(f'Something went wrong | {ex}')


def load_contract(
        address: str,
        web3: AsyncWeb3,
        abi: str
) -> Optional[Contract]:
    if address is None:
        return

    address = web3.to_checksum_address(address)
    return web3.eth.contract(address=address, abi=abi)


async def add_gas_price(
        web3: AsyncWeb3
) -> Optional[int]:
    try:
        gas_price = await web3.eth.gas_price
        gas_price = int(gas_price * uniform(1.01, 1.02))
        return gas_price
    except Exception as ex:
        logger.error(f'Something went wrong | {ex}')


async def add_gas_limit(
        web3: AsyncWeb3,
        tx: TxParams
) -> int:
    tx['value'] = 0
    gas_limit = await web3.eth.estimate_gas(tx)
    return gas_limit
