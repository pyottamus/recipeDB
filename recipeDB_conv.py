from .quantified import Quantified
from .recipeDB_types import *

class classproperty(property):
    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)
    
from abc import ABCMeta
class ConvMeta(ABCMeta):

    def __subclasscheck__(cls, C):
        if (ret := cls.__subclasshook__(C)) is not NotImplemented:
            return ret
        return NotImplemented
    
    def __instancecheck__(cls, instance):
        if (ret := cls.__isinstancehook__(instance)) is not NotImplemented:
            return ret
        return ConvMeta.__subclasscheck__(cls, type(instance))

    def __call__(cls, C):
        if isinstance(C, cls):
            return C

        if (ret := cls._try_conv(C)) is not None:
            return ret
        raise TypeError


class ConvBase(metaclass=ConvMeta):
    @classproperty
    def RecipeDB(self):
        return CRecipeDB.get()
    @classmethod
    def __subclasshook__(cls, C):
        return NotImplemented
    @classmethod
    def __isinstancehook__(cls, C):
        return NotImplemented
    def _try_conv(self, C):
        return None
    @classmethod
    def list_conv(cls, C):
        try:
            return [cls(C)]
        except TypeError:
            return [cls(x) for x in C]

class ProductItem(ConvBase):
    @classmethod
    def __subclasshook__(cls, C):
        return issubclass(C, Item)

class ComponentProductItem(ConvBase):
    @classmethod
    def __subclasshook__(cls, C):
        return issubclass(C, (Component)) or ProductItem.__subclasshook__(C)

class RecipeItem(ConvBase):
    @classmethod
    def __subclasshook__(cls, C):
        return issubclass(C, Tool) or ProductItem.__subclasshook__(C)


class ComponentRecipeItem(ConvBase):
    @classmethod
    def __subclasshook__(cls, C):
        return issubclass(C, Component) or RecipeItem.__subclasshook__(C)

class QuantifiedConvMeta(ABCMeta):
    def __new__(cls, name, base, dct, **kwargs):
        if name == 'QuantifiedBase':
            return super().__new__(cls, name, base, dct, **kwargs)
        if len(kwargs) != 1:
            raise TypeError
        quant_for = kwargs['quant_for']
        dct['quant_for'] = quant_for
        del kwargs['quant_for']
        return super().__new__(cls, name, base, dct, **kwargs)
    def __subclasscheck__(cls, C):
        if (ret := cls.__subclasshook__(C)) is not NotImplemented:
            return ret
        return NotImplemented
    
    def __instancecheck__(cls, instance):
        if (ret := cls.__isinstancehook__(instance)) is not NotImplemented:
            return ret
        return ConvMeta.__subclasscheck__(cls, type(instance))

    def __call__(cls, C):
        if isinstance(C, Quantified):
            if isinstance(C.val, cls.quant_for):
                return C
            raise TypeError

        
        if isinstance(C, cls.quant_for):
            return Quantified(1, C)

        raise TypeError

class QuantifiedBase(metaclass=QuantifiedConvMeta):
    @classproperty
    def RecipeDB(self):
        return CRecipeDB.get()
    @classmethod
    def __subclasshook__(cls, C):
        return NotImplemented
    @classmethod
    def __isinstancehook__(cls, C):
        return isinstance(C, Quantified) and isinstance(C.val, cls.quant_for)
    @classmethod
    def list_conv(cls, C):
        try:
            return [cls(C)]
        except TypeError:
            return [cls(x) for x in C]

class QuantifiedProductItem(QuantifiedBase, quant_for=ProductItem):
    pass

class QuantifiedRecipeItem(QuantifiedBase, quant_for=RecipeItem):
    pass

class QuantifiedComponentRecipeItem(QuantifiedBase, quant_for=ComponentRecipeItem):
    pass

class QuantifiedComponent(ConvBase):

    @classmethod
    def _try_conv(cls, C):
        if isinstance(C, Component):
            return Quantified(1, C)
        elif isinstance(C, str):
            return Quantified(1, Component(C))

        return None
    
    @classmethod
    def __isinstancehook__(cls, instance):
        if not isinstance(instance, Quantified):
            return False
        return isinstance(instance.val, (Component))

