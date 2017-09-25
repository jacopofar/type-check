from typing import Any, AnyStr, Dict, List, Optional, Set, Sized, TypeVar, Tuple, Union

import pytest

from runtime_typecheck import check_type, check_args, DetailedTypeError


def test_any():
    assert check_type(3, Any)
    assert check_type([5, "hi"], Any)


def test_numbers():
    assert check_type(3, int)
    assert not check_type(3, float)


def test_strings():
    assert check_type('stringy mcstringface', str)
    assert check_type(u'a string', AnyStr)
    assert check_type(b'another string', AnyStr)
    assert check_type(f'a third string', AnyStr)


def test_unions():
    assert check_type(3, Union[int, str])
    assert check_type("hello", Union[int, str])
    assert not check_type(4.78, Union[int, str])


def test_tuples():
    assert check_type((1, 67), Tuple[int, int])
    assert not check_type((1, "new york"), Tuple[int, int])
    # NOTE not a tuple, currently a list is accepted instead of a tuple and vice-versa
    assert check_type([1, "new york"], Tuple[int, str])
    assert check_type((1, 67, "Amsterdam"), Tuple[int, int, str])
    assert not check_type(("Amsterdam", 1, 67), Tuple[int, int, str])


def test_lists():
    """
    :return:  None - the
    """
    assert check_type([1, 27, 33, 1956], List[int])
    assert not check_type(41, List[int])
    assert not check_type([1.11, 27, 33, 1956], List[int])
    assert not check_type([1, 27, 33, 1956, "h", 42], List[int])


def test_sets():
    assert check_type({1, 27, 33, 1956}, Set[int])
    assert check_type(set(), Set[int])
    assert not check_type(41, Set[int])
    assert not check_type({1.11, 27, 33, 1956}, Set[int])
    assert not check_type({1, 27, 33, 1956, "h", 42}, Set[int])


def test_dicts():
    assert check_type({"pi": 3.1415}, Dict[str, float])
    assert check_type({}, Dict[str, float])
    assert not check_type({"something": "wrong"}, Dict[str, float])


def test_nested_types():
    assert check_type([1, 27, 33, 1956], List[Union[str, int]])
    assert check_type([(12, "Texas"), (-5, "Particle")], List[Tuple[int, str]])
    assert not check_type([(1.9, "Texas"), (-5, "Particle")],
                          List[Tuple[int, str]])
    assert not check_type([1.11, 27, 33, 1956], List[Tuple[int, str]])


def test_aliases():
    Vector = List[float]
    assert check_type([1.0, 2.0], Vector)
    assert not check_type(1, Vector)


def test_typevar():
    T = TypeVar('T') # Any type
    Num = TypeVar('Num', int, float) # Either int or float
    assert check_type(1, T)
    assert check_type(1, Num)
    assert check_type(1.0, Num)
    assert not check_type('str', Num)


def test_optional():
    assert check_type([1], Optional[List[int]])
    assert check_type(None, Optional[List[int]])
    assert not check_type([1.0], Optional[List[int]])


# Some important ABCs
def test_sized():
    assert check_type([1, 27, 33, 1956], Sized)
    assert not check_type(5, Sized)


@check_args
def dummy_fun(a: int = 0, b: str = '', c: Tuple[int, str] = (0, '')) -> int:
    return a + len(b) + c[0] + len(c[1]) + 7


@check_args
def dummy_fun_with_nonoptional(x: int, y: str = '', z: Tuple[int, str] = (0, '')) -> int:
    return x + len(y) + z[0] + len(z[1]) + 7


@check_args
def dummy_fun_with_base_collections(x: dict = {"0": 1}, y: tuple = (0, 1)) -> int:
    return 1


def test_args():
    assert dummy_fun() == 7
    assert dummy_fun(10, 'antani', (1, '0')) == 25
    assert dummy_fun(a=10, b='antani', c=(1, '0')) == 25


def test_dict():
    param_dic = {'y': 'antani', 'z': (1, '0')}
    assert dummy_fun_with_nonoptional(10, **param_dic) == 25


def test_collections():
    assert dummy_fun_with_base_collections() == 1
    assert dummy_fun_with_base_collections({}, (0, 0)) == 1


def test_raises_simple():
    with pytest.raises(DetailedTypeError):
        dummy_fun('1')
    with pytest.raises(DetailedTypeError):
        dummy_fun(1, 1)
    with pytest.raises(DetailedTypeError):
        dummy_fun(1, '1', ('1', '0'))
    with pytest.raises(TypeError):
        dummy_fun(1, '1', (1, '0'), extra=42) # pylint: disable=E1123
    with pytest.raises(DetailedTypeError):
        dummy_fun(a=1, b='1', c=('1', '0'))
    with pytest.raises(TypeError):
        dummy_fun_with_nonoptional() # pylint: disable=E1120


def test_raises_with_dictionary():
    with pytest.raises(DetailedTypeError):
        param_dic = {'y': 'antani', 'z': (1, '0')}
        assert dummy_fun_with_nonoptional('a string', **param_dic) == 25
    with pytest.raises(DetailedTypeError):
        param_dic = {'y': 11, 'z': (1, '0')}
        dummy_fun_with_nonoptional(49, **param_dic)


def test_raises_with_base_collections():
    with pytest.raises(DetailedTypeError):
        dummy_fun_with_base_collections(0, (0, 1))
    with pytest.raises(DetailedTypeError):
        dummy_fun_with_base_collections({}, 'a_string')
    with pytest.raises(DetailedTypeError):
        dummy_fun_with_base_collections(0, 'a_string')


def test_exception_content():
    with pytest.raises(DetailedTypeError) as excinfo:
        param_dic = {'y': 11, 'z': (1, '0')}
        dummy_fun_with_nonoptional('I am a string!', **param_dic)
    # The two issues were identified
    assert ('x', int, 'I am a string!', False, None) in excinfo.value
    assert ('y', str, 11, False, None) in excinfo.value
    # and nothing else was
    assert len(excinfo.value) == 2


def test_no_value_no_default():
    with pytest.raises(DetailedTypeError) as excinfo:
        param_dic = {'y': 11, 'z': (1, '0')}
        dummy_fun_with_nonoptional(**param_dic)
    # The missing x parameter was spotted
    assert ('x', int, None, True, None) in excinfo.value
    # and nothing else was
    assert len(excinfo.value) == 1


def test_unknown_parameters():
    with pytest.raises(DetailedTypeError) as excinfo:
        param_dic = {'x': 67, 'y': 11, 'z': (1, '0'), 'w': 999}
        dummy_fun_with_nonoptional(**param_dic)
    # The unknown w parameter was spotted
    assert (None, None, None, None, "got an unexpected keyword argument 'w'") in excinfo.value
    # and nothing else was
    assert len(excinfo.value) == 1
