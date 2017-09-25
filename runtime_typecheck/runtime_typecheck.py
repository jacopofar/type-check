"""Provides `check_type`, `check_args`, `DetailedTypeError`"""
from functools import wraps
import inspect
from typing import (
    Any,
    Dict,
    List,
    NamedTuple,
    Tuple,
    TypeVar,
    Type,
    Union)

# pylint: disable=C0123
def check_type(obj: Any,
               candidate_type: Any,
               reltype: str = 'invariant') -> bool:
    """Tell wether a value correspond to a type,
    optionally specifying the type as contravariant or covariant.

    Args:
        obj (Any): The value to check.
        candidate_type (Any): The type to check the object against.
        reltype (:obj:`str`, optional): Variance of the type, can be contravariant,
            covariant or invariant. By default is invariant.
    Returns:
        bool: True if the type is fine, False otherwise

    Raises:
        ValueError: When the variance or the type are not among the ones the function can manage.
    """
    if reltype not in ['invariant', 'covariant', 'contravariant']:
        raise ValueError(f' Variadic type {reltype} is unknown')

    # builtin type like str, or a class
    if type(candidate_type) == type and reltype in ['invariant']:
        return isinstance(obj, candidate_type)

    if type(candidate_type) == type and reltype in ['covariant']:
        return issubclass(obj.__class__, candidate_type)

    if type(candidate_type) == type and reltype in ['contravariant']:
        return issubclass(candidate_type, obj.__class__)

    # Any accepts everything
    if type(candidate_type) == type(Any):
        return True

    # Union, at least one match in __args__
    if type(candidate_type) == type(Union):
        return any(check_type(obj, t, reltype) for t in candidate_type.__args__)

    # Tuple, each element matches the corresponding type in __args__
    if type(candidate_type) == type(Tuple) and tuple in candidate_type.__bases__:
        if not hasattr(obj, '__len__'):
            return False
        if len(candidate_type.__args__) != len(obj):
            return False
        return all(check_type(o, t, reltype) for (o, t) in zip(obj, candidate_type.__args__))

    # Dict, each (key, value) matches the type in __args__
    if type(candidate_type) == type(Dict) and dict in candidate_type.__bases__:
        if type(obj) != dict:
            return False
        return all(check_type(k, candidate_type.__args__[0], reltype)
                   and check_type(v, candidate_type.__args__[1], reltype)
                   for (k, v) in obj.items())

    # List or Set, each element matches the type in __args__
    if type(candidate_type) == type(List) and \
       (list in candidate_type.__bases__ or set in candidate_type.__bases__):
        if not hasattr(obj, '__len__'):
            return False
        return all(check_type(o, candidate_type.__args__[0], reltype) for o in obj)

    # TypeVar, this is tricky
    if type(candidate_type) == TypeVar:
        # TODO consider contravariant, variant and bound
        # invariant with a list of constraints, acts like a Tuple
        if not candidate_type.__constraints__:
            return True
        if not (candidate_type.__covariant__ or candidate_type.__contravariant__):
            return any(check_type(obj, t) for t in candidate_type.__constraints__)

    if type(candidate_type) == type(Type):
        return check_type(obj, candidate_type.__args__[0], reltype='covariant')

    if inspect.isclass(candidate_type) and reltype in ['invariant']:
        return isinstance(obj, candidate_type)

    raise ValueError(f'Cannot check against {reltype} type {candidate_type}')


def check_args(func):
    """A decorator that performs type checking using type hints at runtime::
            @check_args
            def fun(a: int):
                print(f'fun is being called with parameter {a}')
            # this will raise a TypeError describing the issue without the function being called
            fun('not an int')
    """

    @wraps(func)
    def check(*args, **kwargs):  # pylint: disable=C0111
        sig = inspect.signature(func)
        found_errors = []
        binding = None
        try:
            binding = sig.bind(*args, **kwargs)
        except TypeError as te:
            for name, metadata in sig.parameters.items():
                # Comparison with the message error as a string :(
                # Know a nicer way? Please drop me a message
                if metadata.default == inspect.Parameter.empty:
                    # copy from inspect module, it is the very same error message
                    error_in_case = 'missing a required argument: {arg!r}'.format(arg=name)
                    if str(te) == error_in_case:
                        found_errors.append(IssueDescription(
                            name, sig.parameters[name].annotation, None, True))
            # NOTE currently only find one, at most, detecting what else
            # is missing is tricky if not impossible
            if not found_errors:
                raise DetailedTypeError([IssueDescription(None, None, None, None, str(te))])
            raise DetailedTypeError(found_errors)

        for name, value in binding.arguments.items():
            if not check_type(value, sig.parameters[name].annotation):
                found_errors.append(IssueDescription(
                    name, sig.parameters[name].annotation, value, False))

        if found_errors:
            raise DetailedTypeError(found_errors)
        return func(*args, **kwargs)

    return check


class IssueDescription(NamedTuple):
    """Represents single type mismatch"""
    name: str
    expected_type: Any
    value: Any
    missing_parameter: bool
    generic_message: str = None

    def __repr__(self) -> str:
        if self.name is None:
            return f'Generic type error: {self.generic_message}'
        if self.missing_parameter:
            return f'{self.name} has no default value and was not given,' \
                   f'expected a value of type {self.expected_type}'
        return f'{self.name} had to be of type {self.expected_type} but was {self.value}, ' \
               f'which has type {type(self.value)}'


class DetailedTypeError(TypeError):
    """Error for more detailed info about type mismatches"""
    issues = []

    def __init__(self, issues: List[IssueDescription]):
        self.issues = issues
        super().__init__(f'typing issues found:{issues}')

    def __str__(self):
        return '\n'.join(str(i) for i in self.issues)

    def __iter__(self):
        return (x for x in self.issues)

    def __len__(self):
        return len(self.issues)
