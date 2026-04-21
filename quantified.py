from functools import wraps
import types
from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import Any



#from .recipeDB_types import NamedItem, Tool, Component, MaterializedComponent


@dataclass(frozen=True, repr=False, slots=True)
class Quantified[T]:

    count: int
    val: T

    def __le__(self, other: Quantified[T]):
        if self.val == other.val:
            return self.count < other.count
        return self.val < other.val
    def __gt__(self, other: Quantified[T]):
        if self.val == other.val:
            return self.count > other.count
        return self.val > other.val
    def __eq__(self, other: Quantified[T]):
        return self.val == other.val and self.count == other.count
    def __hash__(self):
        return hash((type(self), self.val, self.count))
    @property
    def count_repr(self) -> str:
        count = f'{self.count}'
        if self.fluid:
            count = f'{count}L'
        return count
    @property
    def fluid(self):
        if not hasattr(self.val , 'fluid'):
            return False
        return self.val.fluid
    def __repr__(self):
        val = self.val
        return f'{self.count_repr} * {val!r}'

    def __getitem__(self, key):
        return Quantified(self.count, self.val[key])

def quantify[T](arg: Quantified[T] | T, *args: tuple[Quantified[T] | T, ...]):
    if len(args) == 0:
        return arg if isinstance(arg, Quantified) else Quantified(1, arg)
    else:
        return [x if isinstance(x, Quantified) else Quantified(1, x) for x in (arg, *args)]

def quantify_list[T](lst: Sequence[Quantified[T] | T]) -> list[Quantified[T]]:
    return [x if isinstance(x, Quantified) else Quantified(1, x) for x in lst]



class QuantifiedMixin:
    def __mul__(self, count: int):
        assert count > 0
        return Quantified(count, self)
    def __rmul__(self, count: int):
        return self.__mul__(count)

def dequantify(elem):
    if isinstance(elem, Quantified):
        return elem.val, elem.count
    return elem, None


class QuantifiedDict[T](dict[T, int]):
    @wraps(dict.copy)
    def copy(self) -> QuantifiedDict[T]:
        return QuantifiedDict(super().copy())
    @classmethod
    def from_list(cls, items: Sequence[Quantified[T] | T]):
        items = quantify_list(items)
        new = cls()
        for item in items:
            if item.count == 0:
                continue
            new[item.val] += item.count
        return new
    def __missing__(self, key):
        return 0
    def to_list(self) -> list[Quantified[T]]:
        out = []
        for val, count in self.items():
            out.append(Quantified(count, val))
        return out
    def pop(self, key):
        return super().pop(key, 0)
    def dec_jz(self, key):
        if (val := self.get(key)) is None:
            #print(self, key)
            raise RuntimeError

        val -= 1
        if val == 0:
            del self[key]
            return True
        else:
            self[key] = val
            return False
    def __setitem__(self, key: T, val: int):
        if val == 0:
            super().pop(key, 0)
            return
        super().__setitem__(key, val)
    def add(self, quant: Quantified[T]):
        self[quant.val] += quant.count
    def reduce_sub(self, quant: Quantified[T], val: T | None=None, /, diff_out: QuantifiedDict[T]=None):
        
        if val is None:
            from_quant=True
            val = quant.val
            qcount = quant.count
        else:
            from_quant=False
            qcount = quant
        
        if (count := self.get(val)) is None:
            return quant

        diff = qcount - count

        if diff >= 0:
            del self[val]
            leftover = diff
        else:
            self[val] = -diff
            leftover = 0
        
        if diff_out is not None:
            diff_out[val] += qcount - leftover

        if leftover:
            return Quantified(leftover, val) if from_quant else leftover
        else:
            return None if from_quant else 0        

    def add_val(self, quant: Quantified[T]):
        """ add quant to dict set.
            If quant.val is present, add quant.count and return true
            else, insert (quant.val, quant.count) and return false
        """
        val = quant.val
        count = quant.count
        try:
            self[val] += count
            return True
        except KeyError:
            self[val] = count
            return False
    def sub_retz(self, other: QuantifiedDict[T]):
        new_zeros = []
        for key, oval in other.items():
            sval = self[key]
            sval -= oval
            if sval == 0:
                #print("DEL")
                del self[key]
                new_zeros.append(key)
            else:
                self[key] = sval
        return new_zeros
    def sub(self, other: QuantifiedDict[T]):
        #print("SUB")
        new_zeros = []
        for key, oval in other.items():
            sval = self[key]
            sval -= oval
            if sval == 0:
                #print("DEL")
                del self[key]
            else:
                self[key] = sval
            
            
    def __isub__(self, other: QuantifiedDict[T]):
        for key in (self.keys() & other.keys()):
            sval = self[key]
            oval = other[key]
            if sval <= oval:
                del self[key]
            else:
                self[key] = sval - oval
        return self
    def __iadd__(self, other: QuantifiedDict[T]):
        for k, v in other.items():
            self[k] += v
        return self
    def __add__(self, other: QuantifiedDict[T]):
        new = self.copy()
        return new.__iadd__(other)
