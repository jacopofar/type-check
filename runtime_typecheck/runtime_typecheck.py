#!/usr/bin/env python3
from functools import wraps
import inspect
from typing import (
    Any,
    List,
    NamedTuple,
    Tuple,
    TypeVar,
    Type,
    Union)

IssueDescription = NamedTuple('IssueDescription', [('name', str), ('expected_type', Any), ('value', Any)])


class DetailedTypeError(TypeError):
    issues = []

    def __init__(self, issues: List[IssueDescription]):
        self.issues = issues
        super().__init__(f'typing issues found:{issues}')

    def __str__(self):
        return ' '.join([f'{i.name} had to be of type {i.expected_type} but was {i.value}, which has type {type(i.value)}' for i in self.issues])

    def __iter__(self):
        return (x for x in self.issues)

    def __len__(self):
        return len(self.issues)

def check_type(obj: Any,
               candidate_type: Any,
               reltype: str = 'invariant') -> bool:
    """Tell wether a value correspond to a type, optionally specifying the type as contravariant or covariant.

    Args:
        obj (Any): The value to check.
        candidate_type (Any): The type to check the object against.
        reltype (:obj:`str`, optional): Variance of the type, can be contravariant, covariant or invariant.
            By default is invariant.
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
    if type(candidate_type) == type(Tuple):
        if not hasattr(obj, '__len__'):
            return False
        if len(candidate_type.__args__) != len(obj):
            return False
        return all(check_type(o, t, reltype) for (o, t) in zip(obj, candidate_type.__args__))

    # List, each element matches the type in __args__
    if type(candidate_type) == type(List):
        if not hasattr(obj, '__len__'):
            return False
        return all(check_type(o, candidate_type.__args__[0], reltype) for o in obj)

    # TypeVar, this is tricky
    if type(candidate_type) == type(TypeVar):
        # TODO consider contravariant, variant and bound
        # invariant with a list of constraints, acts like a Tuple
        if not (candidate_type.__covariant__ or candidate_type.__contracovariant__) and len(
                candidate_type.__constraints__) > 0:
            return any(check_type(obj, t) for t in candidate_type.__constraints__)

    if type(candidate_type) == type(Type):
        return check_type(obj, candidate_type.__args__[0], reltype='covariant')

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
    def check(*args, **kwargs):
        sig = inspect.signature(func)
        binding = sig.bind(*args, **kwargs)
        found_errors = []
        for name, value in binding.arguments.items():
            if not check_type(value, sig.parameters[name].annotation):
                found_errors.append(IssueDescription(name, sig.parameters[name].annotation, value))
        if len(found_errors) > 0:
            raise DetailedTypeError(found_errors)
        return func(*args, **kwargs)

    return check
