from typing import List
import asyncio

from asyncio import (
    create_task,
    gather,
    run,
)

from src.aevo.aevo import Aevo

from src.data import private_keys

from config import (
    DEPOSIT_PERCENTAGE,
    CLOSE_POSITIONS,
    USE_PERCENTAGE,
    OPEN_POSITIONS,
    DEPOSIT_AMOUNT,
    TOKEN,
)


async def process_tasks(private_key: str) -> List[asyncio.Task]:
    tasks = []
    trader = Aevo(
        private_key=private_key,
        open_positions=OPEN_POSITIONS,
        close_positions=CLOSE_POSITIONS,
        token=TOKEN,
        deposit_amount=DEPOSIT_AMOUNT,
        use_percentage=USE_PERCENTAGE,
        deposit_percentage=DEPOSIT_PERCENTAGE
    )
    task = create_task(trader.run())
    tasks.append(task)
    await task
    return tasks


async def main() -> None:
    tasks = []
    for private_key in private_keys:
        tasks.extend(await process_tasks(private_key))

    await gather(*tasks)


if __name__ == '__main__':
    run(main())
