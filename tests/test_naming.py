from django.test import RequestFactory
from iommi import Table, Column, Field, Form
from iommi.base import traverse, get_path, EndPointHandlerProxy
from iommi.page import Fragment, Page
from tri_struct import Struct


def test_traverse():
    baz = Struct(name='baz')
    buzz = Struct(name='buzz')
    bar = Struct(
        name='bar',
        children=lambda: Struct(
            baz=baz,
            buzz=buzz,
        ),
        default_child=True,
    )
    foo = Struct(
        name='foo',
        children=lambda: Struct(
            bar=bar,
        ),
        default_child=True,
    )
    root = Struct(
        name='root',
        children=lambda: Struct(
            foo=foo
        ),
    )

    expected = {
        '': baz,
        'buzz': buzz,
        'bar': bar,
        'foo': foo,
        'root': root,
    }
    actual = traverse(root)
    assert actual.items() == expected.items()

    for path, node in actual.items():
        assert get_path(root, node) == path
    assert len(actual.keys()) == len(set(actual.keys()))


def test_traverse_on_iommi():
    class MyPage(Page):
        header = Fragment()
        some_form = Form(fields=dict(
            fisk=Field(),
        ))
        some_other_form = Form(fields=dict(
            fjomp=Field(),
        ))
        a_table = Table(columns=dict(
            fusk=Column(query__include=True, query__form__include=True),
        ))

    page = MyPage().bind(request=RequestFactory().get('/'))

    actual = traverse(page)
    for k, v in actual.items():
        print(k, repr(v))

    for path, node in actual.items():
        print(path, get_path(page, node), repr(node))
        # assert get_path(page, node) == path

    assert len(actual.keys()) == len(set(actual.keys()))
