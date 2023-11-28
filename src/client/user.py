from asyncio import sleep

from web3.types import TxParams
from web3.eth import AsyncEth
from hexbytes import HexBytes
from loguru import logger

from web3 import AsyncWeb3
from config import RPC

from src.data import (
    USDC_CONTRACT,
    ERC20_ABI,
)


class User:
    def __init__(self, private_key: str) -> None:
        self.private_key = private_key

        self.web3 = AsyncWeb3(
            provider=AsyncWeb3.AsyncHTTPProvider(
                endpoint_uri=RPC,
            ),
            modules={'eth': (AsyncEth,)},
            middlewares=[]
        )
        self.account = self.web3.eth.account.from_key(private_key)
        self.wallet_address = self.account.address

    async def get_wallet_balance(self, token: str = 'USDC', stable_address: str = USDC_CONTRACT) -> int:
        if token.lower() != 'eth':
            contract = self.web3.eth.contract(address=self.web3.to_checksum_address(stable_address),
                                              abi=ERC20_ABI)
            balance = await contract.functions.balanceOf(self.wallet_address).call()
        else:
            balance = await self.web3.eth.get_balance(self.wallet_address)

        return balance

    async def sign_transaction(self, tx: TxParams) -> HexBytes:
        signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
        raw_tx_hash = await self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        tx_hash = self.web3.to_hex(raw_tx_hash)
        return tx_hash

    async def wait_for_withdraw(self, balance_before_withdraw: int, token: str) -> None:
        logger.info(f'Waiting for {token.upper()} to arrive on Metamask...')
        while True:
            balance = await self.get_wallet_balance(token)
            if balance > balance_before_withdraw:
                logger.success(f'{token.upper()} has arrived | [{self.wallet_address}]')
                break
            await sleep(20)
