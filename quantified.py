from functools import wraps
import types
from dataclasses import dataclass, field
from collections.abc import Sequence, Set
from typing import Any, Iterable


#from .recipeDB_types import NamedItem, Tool, Component, MaterializedComponent


@dataclass(repr=False, slots=True)
class Quantified[T]:

    count: int
    val: T
    def copy(self) -> Quantified[T]:
        return Quantified(self.count, self.val)
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
        return hash((type(self),  self.count, self.val))
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
        return f'{self.count_repr} {val!r}'
    def __mul__(self, count: int):
        return Quantified[T](self.count * count, self.val)
    def __rmul__(self, count: int):
        return Quantified[T](self.count * count, self.val)
    def __imul__(self, count: int):
        self.count *= count
    def __isub__(self, other: Quantified[T] | int):
        if isinstance(other, Quantified):
            if self.val != other.val:
                raise TypeError(f"Cannot subtract other of type {other.val} from {self.val}")
            other = other.count
        if self.count <= other:
            raise RuntimeError(f"Cannot subtract other of count {other} which is greater than or equal to {self.count}")
        self.count -= other
        return self
    def __sub__(self, other: int | Quantified[T]):
        copy = self.copy()
        copy.__isub__(other)
        return copy
    def __getitem__(self, key):
        return Quantified[T](self.count, self.val[key])

type SemiQuantifiedIterable[T] = Sequence[Quantified[T] | T] | Set[Quantified[T] | T] | Iterable[Quantified[T] | T]

def quantify[T](arg: Quantified[T] | T, *args: tuple[Quantified[T] | T, ...]) -> Quantified[T] | list[Quantified[T]]:
    if len(args) == 0:
        return arg if isinstance(arg, Quantified) else Quantified(1, arg)
    else:
        return [x if isinstance(x, Quantified) else Quantified(1, x) for x in (arg, *args)]

def quantify_list[T](lst: SemiQuantifiedIterable[T]) -> list[Quantified[T]]:
    return [x if isinstance(x, Quantified) else Quantified(1, x) for x in lst]

def quantify_tuple[T](lst: SemiQuantifiedIterable[T]) -> tuple[Quantified[T], ...]:
    return tuple((x if isinstance(x, Quantified) else Quantified(1, x) for x in lst))

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
    def copy(self) -> QuantifiedDict[T]:
        return QuantifiedDict[T](super().copy())

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
    def to_tuple(self) -> tuple[Quantified[T], ...]:
        return tuple(self.to_list())
    def reduce(self, key: T, amount: int):
        if (val:=self.get(key)) is None:
            return amount
        if val > amount:
            self[key] -= val
            return 0
        elif val == amount:
            del self[key]
            return 0
        else:
            del self[key]
            return amount - val
    def pop(self, key):
        return super().pop(key, 0)
    def dec_jz(self, key: T):
        if (val := self.get(key)) is None:
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
            
            
    def __isub__(self, other: QuantifiedDict[T] | Quantified[T]):
        if isinstance(other, QuantifiedDict):
            for key in (self.keys() & other.keys()):
                sval = self[key]
                oval = other[key]
                if sval <= oval:
                    del self[key]
                else:
                    self[key] = sval - oval
        else:
            sval = self[other.val]
            if sval <= other.count:
                del self[other.val]
            else:
                self[other.val] = sval - other.count
        return self
    def __iadd__(self, other: QuantifiedDict[T] | Quantified[T]):
        if isinstance(other, QuantifiedDict):
            for k, v in other.items():
                self[k] += v
        else:
            self[other.val] += other.count

        return self
    def __add__(self, other: QuantifiedDict[T]):
        new = self.copy()
        return new.__iadd__(other)

