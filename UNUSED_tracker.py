from functools import wraps
import types
from .context import *
class _update_init:
    def __init__(self, dst, call_wrapper_obj):
        self.dst = dst
        self.call_wrapper_obj = call_wrapper_obj

    def __get__(self, obj, objtype=None):
        if obj is None:
            return types.MethodType(type.__init__, objtype)
        else:
            return obj._real_init

    def __set__(self, obj, value):
        self.dst.__call__ = wraps(value)(self.call_wrapper_obj)
        obj._real_init = value
    
class RecipeDBMeta(type):
    to_bind = []
    @wraps(type.__call__)
    def __new__(metacls, name, bases, namespace):
        #print(metacls, name, bases)
        new_metacls = type(metacls.__name__ + "_sigfix", (metacls,), {})
        namespace['db'] = None
        
        new_metacls.__init__ = _update_init(new_metacls, RecipeDBMeta.__call__)


        real_init = namespace.pop('__init__', None)
        cls = super().__new__(new_metacls, name, bases, namespace)
        
            
        
        if real_init is not None:
            cls.__init__ = real_init
        cls.__init__ = _update_init(new_metacls, RecipeDBMeta.__call__)
        metacls.root = cls
        return cls

        
    def __call__(cls, *args, **kwargs):
        args, kwargs = cls.normalize_args(*args, **kwargs)
        if len(args) == 1 and len(kwargs) == 0 and args[0].__class__ is cls:
            return args[0]

        """
        key = cls.get_key(*args, **kwargs)
        if (ret := cls._key_get(key)) is not None:
            return ret
        #print(cls)
        #print(type(cls))
        #print(super().__call__)

        
        
        """     
        ret = cls.__new__(cls)
        ret._real_init(*args, **kwargs)
        #cls._set(key, ret)
        return ret
class RecipeDBBase(metaclass=RecipeDBMeta):
    def __init__(self):
        pass
    @classmethod
    def normalize_args(cls, *args, **kwargs):
        return args, kwargs
    
    @classmethod
    def get_key(cls, *args, **kwargs):
        
        if len(kwargs):
            raise TypeError("Cannot use kwargs with default get_key")

        if len(args) == 1:
            return args[0]
        else:
            return tuple(args)

def tracker(cls=None):
    def wraper(cls):
        #l = {}
        tracker_name = cls.tracker_name

        g = globals()
        names = "_key_get", "_get", "_set"
        
        fns = (f"""(cls, key):\n\treturn CRecipeDB.get().key_get_{tracker_name}(key)""",
               f"""(cls, key):\n\treturn CRecipeDB.get().get_{tracker_name}(key)""",
               f"""(cls, key, val):\n\treturn CRecipeDB.get().add_{tracker_name}(key, val)"""
              )
        
        #exec(f"""def _key_get(cls, key):\n\treturn RecipeDB.key_get_{tracker_name}(key)""", globals(), l)
        #exec(f"""def _get(cls, key):\n\treturn RecipeDB.get_{tracker_name}(key)""", globals(), l)
        #exec(f"""def _set(cls, key, val):\n\treturn RecipeDB.add_{tracker_name}(key, val)""", globals(), l)
        for name, fn in zip(names, fns):
            if hasattr(cls, name):
                continue

            l = {}
            exec(f'def {name}{fn}', g, l)
            setattr(cls, name, types.MethodType(l[name], cls))
        
        return cls
    if cls is None:
        return wraper
    return wraper(cls)

@tracker
class MaterialTracker(RecipeDBBase):
    tracker_name = "material"
    
@tracker
class ComponentTracker(RecipeDBBase):
    tracker_name = 'component'

@tracker
class SpecifiedComponentTracker(RecipeDBBase):
    tracker_name = 'specified_component'
    @classmethod
    def _key_get(self, key):
        return CRecipeDB.get().get_specified_component(*key)
    @classmethod
    def _get(self, key):
        return CRecipeDB.get().get_specified_component(key)
    @classmethod
    def _set(self, key, val):
        return CRecipeDB.get().add_specified_component(val)
@tracker
class GeneralizedItemTracker(RecipeDBBase):
    tracker_name = 'generalized_item'

@tracker
class NamedItemTracker(RecipeDBBase):
    tracker_name = 'named_item'

@tracker
class ToolTracker(RecipeDBBase):
    tracker_name = 'tool'

@tracker
class StationTracker(RecipeDBBase):
    tracker_name = 'station'
