from asyncio import sleep
import random

from typing import (
    Optional,
    Dict,
    List,
)

from abc import (
    abstractmethod,
    ABC,
)

from eth_account.datastructures import SignedMessage
from loguru import logger

from src.bot.utils.data_exctractor import get_signatures
from src.client.user import User

from config import (
    USE_PERCENTAGE_WITHDRAW_STAKE,
    WITHDRAW_STAKING_PERCENTAGE,
    WITHDRAW_STAKING_AMOUNT,
    USE_PERCENTAGE_STAKE,
    WITHDRAW_ALL_STAKING,
    WITHDRAW_PERCENTAGE,
    WITHDRAW_STAKING,
    STAKE_PERCENTAGE,
    delete_api_keys,
    STAKE_AMOUNT,
    WITHDRAW_ALL,
    WITHDRAW,
    DEPOSIT,
    STAKE,
    TOKEN,
    SIDE,
)


class Trader(User, ABC):
    def __init__(
            self,
            private_key: str,
            open_positions: bool,
            close_positions: bool,
            token: str,
            deposit_amount: float,
            use_percentage: bool,
            deposit_percentage: float
    ) -> None:
        self.api_key = None
        self.api_secret = None
        self.headers = {
            "accept": "application/json",
        }
        self.open_positions = open_positions
        self.close_positions = close_positions
        self.token = token
        self.deposit_amount = deposit_amount
        self.use_percentage = use_percentage
        self.deposit_percentage = deposit_percentage
        self.withdraw = WITHDRAW
        self.withdraw_percentage = WITHDRAW_PERCENTAGE
        self.withdraw_all = WITHDRAW_ALL

        super().__init__(private_key)

    async def run(self) -> None:
        signing_key, account_signature, signing_key_signature = get_signatures(
            self.web3,
            self.wallet_address,
            self.account
        )

        api_key, api_secret = await self.register(signing_key, account_signature, signing_key_signature)
        self.api_key = api_key
        self.api_secret = api_secret
        self.headers.update({"AEVO-KEY": self.api_key, "AEVO-SECRET": self.api_secret})
        aevo_balance = await self.balance(self.headers)

        if DEPOSIT:
            balance_before_deposit = await self.balance(self.headers)
            await self.deposit()
            logger.debug(f'Waiting for USDC on AEVO...')
            while True:
                aevo_balance = await self.balance(self.headers)
                if aevo_balance > balance_before_deposit:
                    logger.info(f'Balance: {aevo_balance} USDC')
                    break
                await sleep(30)

        if STAKE:
            stake_amount = STAKE_AMOUNT
            if USE_PERCENTAGE_STAKE:
                staking_percentage = STAKE_PERCENTAGE
                stake_amount = aevo_balance * staking_percentage
            await self.stake_usdc(self.headers, stake_amount)

        if WITHDRAW_STAKING:
            staked_balance = await self.get_staking_balance(self.headers)
            if staked_balance == 0:
                logger.error(f'Your staked balance is 0 | [{self.wallet_address}]')
                return

            withdraw_amount = WITHDRAW_STAKING_AMOUNT
            if WITHDRAW_ALL_STAKING:
                withdraw_amount = staked_balance

            if USE_PERCENTAGE_WITHDRAW_STAKE:
                withdraw_percentage = WITHDRAW_STAKING_PERCENTAGE
                withdraw_amount = staked_balance * withdraw_percentage
            await self.withdraw_staking(self.headers, withdraw_amount)

        if self.open_positions:
            token = TOKEN
            await self.open_position(aevo_balance, SIDE, self.headers, token=token)

        if self.close_positions:
            while True:
                orders_amount, unrealized_pnl, positions_count, ticker, side = await self.get_positions(self.headers)
                logger.debug(f'Found {positions_count} positions.')
                if positions_count == 0:
                    logger.success(f'Closed all positions | [{self.wallet_address}]')
                    break
                close_side = 'BUY' if side.upper() == 'SELL' else 'SELL'
                await self.close_position(self.headers, close_side, orders_amount, unrealized_pnl, ticker)
                logger.info(f'Sleeping 10 seconds...')
                await sleep(10)
        if self.withdraw:
            balance = await self.balance(self.headers)
            if balance == 0:
                logger.error(f'Your AEVO balance is 0 | [{self.wallet_address}]')
                return
            if self.withdraw_all:
                amount = balance
            else:
                amount = int(balance * self.withdraw_percentage)
            evm_balance = await self.get_wallet_balance()
            await self.withdraw_from_aevo(amount, evm_balance)

        if delete_api_keys:
            await self.delete_api_keys(self.headers)

    @abstractmethod
    async def register(
            self,
            signing_key: str,
            account_signature: SignedMessage,
            signing_key_signature: str
    ) -> tuple[str, str]:
        """Creates API Key and API Secret"""

    @abstractmethod
    async def get_positions(
            self,
            headers: Dict[str, str]
    ) -> tuple[float, float, int, Optional[str], str]:
        """Gets all current orders"""

    @abstractmethod
    async def get_staking_balance(
            self,
            headers: Dict[str, str]
    ) -> float:
        """Gets total staked balance"""

    @abstractmethod
    async def stake_usdc(
            self,
            headers: Dict[str, str],
            amount: float
    ) -> None:
        """Staking USDC on AEVO"""

    @abstractmethod
    async def withdraw_staking(
            self,
            headers: Dict[str, str],
            amount: float
    ) -> None:
        """Withdraws from staking"""

    @abstractmethod
    async def open_position(
            self,
            balance: float,
            side: str,
            headers: Dict[str, str],
            token: str = 'ETH',
            unrealized_pnl: float = None
    ) -> None:
        """Opens position"""

    @abstractmethod
    async def close_position(
            self,
            headers: Dict[str, str],
            close_side: str,
            orders_amount: float,
            unrealized_pnl: float,
            ticker: str
    ) -> None:
        """Closes position"""

    @abstractmethod
    async def balance(
            self,
            headers: Dict[str, str]
    ) -> float:
        """Gets balance"""

    @abstractmethod
    async def deposit(self) -> None:
        """Deposits to AEVO"""

    @abstractmethod
    async def delete_api_keys(
            self,
            headers: Dict[str, str]
    ) -> None:
        """Deletes API Keys"""

    @abstractmethod
    async def withdraw_from_aevo(
            self,
            amount: float,
            evm_balance: int
    ) -> None:
        """Withdraws to metamask"""
