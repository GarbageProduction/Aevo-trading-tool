from aiohttp import ClientSession
from asyncio import sleep
import random
import time

from typing import (
    Optional,
    Union,
    Dict,
    List,
)

from eth_account.datastructures import SignedMessage
from web3.contract import Contract
from loguru import logger

from src.client.utils import approve_token
from src.bot.trading_bot import Trader
from config import LEVERAGE

from src.bot.utils.data_exctractor import (
    sign_withdraw,
    sign_order,
)

from src.data import (
    USDC_CONTRACT,
    AEVO_CONTRACT,
    AEVO_ABI,
)


class Aevo(Trader):
    def __init__(
            self,
            private_key: str,
            open_positions: bool,
            close_positions: bool,
            token: str,
            deposit_amount: float = None,
            use_percentage: bool = None,
            deposit_percentage: float = None,
    ) -> None:
        self.private_key = private_key
        super().__init__(private_key, open_positions, close_positions, token, deposit_amount, use_percentage,
                         deposit_percentage)

    @property
    def contract(
            self,
            contract_address: str = AEVO_CONTRACT,
            abi: str = AEVO_ABI,
    ) -> Contract:
        return self.web3.eth.contract(address=contract_address, abi=abi)

    @staticmethod
    async def get_instrument_id(token: str) -> tuple[int, int]:
        async with ClientSession(headers={"accept": "application/json"}) as session:
            response = await session.get(f'https://api.aevo.xyz/markets?asset={token}&instrument_type=PERPETUAL')
            response_text = await response.json()
        asset = response_text[0]
        instrument_id = int(asset['instrument_id'])
        price_step = int(float(asset['amount_step']) * 10 ** 6)
        return instrument_id, price_step

    @staticmethod
    async def get_api_keys(headers: Dict[str, str]) -> List[str]:
        async with ClientSession(headers=headers) as session:
            response = await session.get('https://api.aevo.xyz/account')
            response_text = await response.json()
        api_keys = [api_key['api_key'] for api_key in response_text['api_keys']]
        return api_keys

    async def balance(
            self,
            headers: Dict[str, str]
    ) -> float:
        async with ClientSession(headers=headers) as session:
            response = await session.get('https://api.aevo.xyz/portfolio')
            response_text = await response.json()

        return float(response_text['balance'])

    async def deposit(self) -> None:
        eth_balance = await self.get_wallet_balance('ETH')
        if eth_balance == 0:
            logger.error(f'Your ETH balance is 0. [{self.wallet_address}]')
            return

        while True:
            usdc_balance = await self.get_wallet_balance('USDC')
            if usdc_balance == 0:
                logger.warning(f'Your USDC balance is 0. [{self.wallet_address}]')
                await sleep(10)
            break

        amount = int(self.deposit_amount * 10 ** 6)
        if self.use_percentage:
            amount = int(usdc_balance * self.deposit_percentage)
        amount = str(amount)
        amount = amount[:3] + '0' * (len(amount) - 3)
        amount = int(amount)

        await approve_token(amount, self.private_key, USDC_CONTRACT,
                            self.contract.address, self.wallet_address, self.web3)

        tx = await self.contract.functions.depositToAppChain(
            self.wallet_address,
            amount,
            1000000,
            self.web3.to_checksum_address('0x69Adf49285c25d9f840c577A0e3cb134caF944D3')
        ).build_transaction({
            'from': self.wallet_address,
            'value': self.web3.to_wei(random.uniform(0.0017, 0.0018), 'ether'),
            'nonce': await self.web3.eth.get_transaction_count(self.wallet_address),
            'gas': 0
        })

        tx.update({'maxFeePerGas': await self.web3.eth.gas_price})
        tx.update({'maxPriorityFeePerGas': await self.web3.eth.gas_price})
        gas_limit = await self.web3.eth.estimate_gas(tx)
        tx.update({'gas': gas_limit})
        tx_hash = await self.sign_transaction(tx)
        logger.success(
            f'Successfully deposited {amount / 10 ** 6} USDC tokens | TX: https://arbiscan.io/tx/{tx_hash}'
        )

    async def close_position(
            self,
            headers: Dict[str, str],
            close_side: str,
            orders_amount: float,
            unrealized_pnl: float,
            ticker: str
    ) -> None:
        is_buy = True if close_side == 'BUY' else False
        limit_price = 115792089237316195423570985008687907853269984665640564039457584007913129639935 if close_side == 'BUY' else 0
        instrument_id, price_step = await self.get_instrument_id(ticker)
        salt = random.randint(0, 10 ** 10)
        timestamp = time.time()
        amount = int(orders_amount * 10 ** 6)

        signature = sign_order(self.wallet_address, self.private_key, is_buy, amount, limit_price, salt,
                               timestamp, instrument_id)
        payload = {
            "instrument": instrument_id,
            "maker": self.wallet_address,
            "is_buy": is_buy,
            "amount": str(amount),
            "limit_price": str(limit_price),
            "salt": str(salt),
            "signature": signature,
            "timestamp": int(timestamp)
        }
        async with ClientSession(headers=headers) as session:
            response = await session.post('https://api.aevo.xyz/orders', json=payload)
            response_text = await response.json()

        if response.status != 200:
            logger.error(f'Something went wrong: {response_text}')
            return
        logger.success(f'Successfully closed {ticker} position. Total PNL: {unrealized_pnl}$')

    async def open_position(
            self,
            balance: float,
            side: str,
            headers: Dict[str, str],
            token: str = 'ETH',
            unrealized_pnl: float = None
    ) -> None:
        is_buy = True if side == 'BUY' else False
        limit_price = 115792089237316195423570985008687907853269984665640564039457584007913129639935 if side == 'BUY' else 0
        async with ClientSession(headers={"accept": "application/json"}) as session:
            response = await session.get(f'https://api.aevo.xyz/index?asset={token}')
            response_text = await response.json()
        instrument_id, price_step = await self.get_instrument_id(token)
        price = float(response_text['price'])
        token_amount = balance / price
        salt = random.randint(0, 10 ** 10)
        timestamp = time.time()
        leverage = LEVERAGE
        amount = int(token_amount * leverage * 10 ** 6)
        amount = int(price_step * round(amount / price_step))

        signature = sign_order(self.wallet_address, self.private_key, is_buy, amount, limit_price, salt,
                               timestamp, instrument_id)
        payload = {
            "instrument": instrument_id,
            "maker": self.wallet_address,
            "is_buy": is_buy,
            "amount": str(amount),
            "limit_price": str(limit_price),
            "salt": str(salt),
            "signature": signature,
            "timestamp": int(timestamp)
        }
        async with ClientSession(headers=headers) as session:
            response = await session.post('https://api.aevo.xyz/orders', json=payload)
            response_text = await response.json()

        if response.status != 200:
            logger.error(f'Something went wrong: {response_text}')
            return

        eth_amount = response_text['amount']
        avg_price = response_text['avg_price']

        logger.success(
            f'Successfully opened {"LONG" if is_buy is True else "SHORT"} position for {eth_amount} {token} with {leverage} LEVERAGE. AVG Price: {avg_price} | [{self.wallet_address}]')

    async def withdraw_from_aevo(
            self,
            amount: float,
            evm_balance: int
    ) -> None:
        balance_before_withdraw = evm_balance
        salt = random.randint(0, 10 ** 10)
        amount = int(amount * 10 ** 6)
        socket_fees = random.randint(4326304606198636, 4326309606198636)
        socket_msg_gas_limit = 2000000
        collateral = '0x643aaB1618c600229785A5E06E4b2d13946F7a1A'
        to = '0xE3EF8bEE5c378D4D3DB6FEC96518e49AE2D2b957'
        socket_connector = '0x73019b64e31e699fFd27d54E91D686313C14191C'
        signature = sign_withdraw(self.web3, collateral, to, amount, salt,
                                  self.private_key, socket_fees, socket_msg_gas_limit, socket_connector)
        payload = {
            "account": self.wallet_address,
            "amount": str(amount),
            "collateral": self.web3.to_checksum_address(collateral),
            "salt": str(salt),
            "signature": signature,
            "socket_connector": socket_connector,
            "socket_fees": str(socket_fees),
            "socket_msg_gas_limit": str(socket_msg_gas_limit),
            "to": self.web3.to_checksum_address(to),
        }

        async with ClientSession(headers={"accept": "application/json"}) as session:
            response = await session.post('https://api.aevo.xyz/withdraw', json=payload)
            response_text = await response.json()

        if response.status != 200:
            logger.error(f'Something went wrong: {response_text}')
            return

        logger.success(f'Successfully withdrawn {amount / 10 ** 6} USDC')
        await self.wait_for_withdraw(balance_before_withdraw, 'USDC')

    async def delete_api_keys(
            self,
            headers: Dict[str, str]
    ) -> None:
        api_keys = await self.get_api_keys(headers)
        api_keys.remove(headers['AEVO-KEY'])
        api_keys.append(headers['AEVO-KEY'])
        for api_key in api_keys:
            payload = {
                "api_key": api_key
            }
            async with ClientSession(headers=headers) as session:
                response = await session.delete('https://api.aevo.xyz/api-key', json=payload)
                response_text = await response.json()
            if response.status == 200:
                logger.success(f'Successfully deleted API KEY: {api_key}')
            else:
                logger.error(f'Something went wrong | {response_text}')
            await sleep(1)
        logger.success(f'Successfully deleted {len(api_keys)} API KEYS')

    async def get_positions(
            self,
            headers: Dict[str, str]
    ) -> tuple[float, float, int, Optional[str], str]:
        async with ClientSession(headers=headers) as session:
            response = await session.get('https://api.aevo.xyz/account')
            response_text = await response.json()
        positions = response_text['positions']
        if not positions:
            return 0, 0, 0, None, None
        positions_count = len(positions)
        amount = float(positions[0]['amount'])
        unrealized_pnl = float(positions[0]['unrealized_pnl'])
        ticker = positions[0]['asset']
        side = positions[0]['side']
        return amount, unrealized_pnl, positions_count, ticker, side

    async def register(
            self,
            signing_key: str,
            account_signature: SignedMessage,
            signing_key_signature: str
    ) -> tuple[str, str]:
        url = "https://api.aevo.xyz/register"
        payload = {
            "account": self.wallet_address,
            "account_signature": account_signature,
            "expiry": int(time.time() + 10000),
            "signing_key": signing_key,
            "signing_key_signature": signing_key_signature
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json"
        }
        async with ClientSession(headers=headers) as session:
            response = await session.post(url=url, json=payload)
            response_text = await response.json()
        api_key = response_text['api_key']
        api_secret = response_text['api_secret']
        return api_key, api_secret
