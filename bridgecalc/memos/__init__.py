"""Memorias handcalcs para BridgeCalc."""
from .lrfd_hl93 import HL93MemoInput, HL93MemoResult, generar_memoria_hl93
from .hl93_handcalcs import (
    HL93HandcalcsInput,
    HL93HandcalcsResult,
    generar_memoria_handcalcs,
)

__all__ = [
    "HL93MemoInput", "HL93MemoResult", "generar_memoria_hl93",
    "HL93HandcalcsInput", "HL93HandcalcsResult", "generar_memoria_handcalcs",
]
