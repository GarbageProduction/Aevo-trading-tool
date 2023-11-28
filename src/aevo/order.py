from eip712_structs import (
    EIP712Struct,
    Address,
    Boolean,
    Uint,
)


class Order(EIP712Struct):
    maker = Address()
    isBuy = Boolean()
    limitPrice = Uint(256)
    amount = Uint(256)
    salt = Uint(256)
    instrument = Uint(256)
    timestamp = Uint(256)
