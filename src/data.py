import json

AEVO_CONTRACT = '0x80d40e32FAD8bE8da5C6A42B8aF1E181984D137c'
USDC_CONTRACT = '0xff970a61a04b1ca14834a43f5de4533ebddb5cc8'

with open('assets/abi/aevo_abi.json') as file:
    AEVO_ABI = json.load(file)

with open('assets/abi/erc20.json') as file:
    ERC20_ABI = json.load(file)

with open('wallets.txt', 'r') as file:
    private_keys = [line.strip() for line in file]
