from habstranslate.cache import LRUSet


def test_add():
    x = LRUSet(3)
    x.add(1)
    x.add(2)
    x.add(3)
    x.add(4)
    x.add(5)

    assert not x.has(1)
    assert not x.has(2)
    assert x.has(3)
    assert x.has(4)
    assert x.has(5)
    assert len(x) == 3
    assert list(x.items()) == [3, 4, 5]
