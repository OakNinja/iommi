from collections import defaultdict
from datetime import date

import pytest
from django.db.models import (
    F,
    Q,
    QuerySet,
)
from iommi.base import perform_ajax_dispatch
from tri_declarative import (
    class_shortcut,
    get_shortcuts_by_name,
)
from tri_struct import Struct
from iommi.form import (
    Field,
    Form,
)
from iommi.query import (
    FREETEXT_SEARCH_NAME,
    Q_OP_BY_OP,
    Query,
    QueryException,
    value_to_query_string_value_string,
    Variable,
)
from iommi.base import request_data

from tests.helpers import req
from tests.models import (
    Bar,
    EndPointDispatchModel,
    Foo,
    FromModelWithInheritanceTest,
    NonStandardName,
)


class MyTestQuery(Query):
    foo_name = Variable(attr='foo', freetext=True, form__include=True)
    bar_name = Variable.case_sensitive(attr='bar', freetext=True, form__include=True)
    baz_name = Variable(attr='baz')


# F/Q expressions don't have a __repr__ which makes testing properly impossible, so let's just monkey patch that in
def f_repr(self):
    return '<F: %s>' % self.name


F.__repr__ = f_repr
Q.__repr__ = lambda self: str(self)


def test_include():
    class ShowQuery(Query):
        foo = Variable()
        bar = Variable(
            include=lambda query, variable: query.request().GET['foo'] == 'include' and variable.extra.foo == 'include2',
            extra__foo='include2')


    assert list(ShowQuery().bind(request=req('get', foo='hide')).variables.keys()) == ['foo']


    assert list(ShowQuery().bind(request=req('get', foo='include')).variables.keys()) == ['foo', 'bar']


def test_request_data():
    r = Struct(method='POST', POST='POST', GET='GET')
    assert request_data(r) == 'POST'
    r.method = 'GET'
    assert request_data(r) == 'GET'


def test_empty_string():
    query = MyTestQuery().bind(request=None)
    assert repr(query.parse('')) == repr(Q())


def test_unknown_field():
    query = MyTestQuery().bind(request=None)
    with pytest.raises(QueryException) as e:
        query.parse('unknown_variable=1')

    assert 'Unknown variable "unknown_variable"' in str(e)
    assert isinstance(e.value, QueryException)


def test_freetext():
    query = MyTestQuery().bind(request=None)
    expected = repr(Q(**{'foo__icontains': 'asd'}) | Q(**{'bar__contains': 'asd'}))
    assert repr(query.parse('"asd"')) == expected

    query2 = MyTestQuery().bind(request=req('get', **{'-': '-', 'term': 'asd'}))
    assert repr(query2.to_q()) == expected


def test_or():
    query = MyTestQuery().bind(request=None)
    assert repr(query.parse('foo_name="asd" or bar_name = 7')) == repr(Q(**{'foo__iexact': 'asd'}) | Q(**{'bar__exact': 7}))


def test_and():
    query = MyTestQuery().bind(request=None)
    assert repr(query.parse('foo_name="asd" and bar_name = 7')) == repr(Q(**{'foo__iexact': 'asd'}) & Q(**{'bar__exact': 7}))


def test_negation():
    query = MyTestQuery().bind(request=None)
    assert repr(query.parse('foo_name!:"asd" and bar_name != 7')) == repr(~Q(**{'foo__icontains': 'asd'}) & ~Q(**{'bar__exact': 7}))


def test_precedence():
    query = MyTestQuery().bind(request=None)
    assert repr(query.parse('foo_name="asd" and bar_name = 7 or baz_name = 11')) == repr((Q(**{'foo__iexact': 'asd'}) & Q(**{'bar__exact': 7})) | Q(**{'baz__iexact': 11}))
    assert repr(query.parse('foo_name="asd" or bar_name = 7 and baz_name = 11')) == repr(Q(**{'foo__iexact': 'asd'}) | (Q(**{'bar__exact': 7})) & Q(**{'baz__iexact': 11}))


@pytest.mark.parametrize('op,django_op', [
    ('>', 'gt'),
    ('=>', 'gte'),
    ('>=', 'gte'),
    ('<', 'lt'),
    ('<=', 'lte'),
    ('=<', 'lte'),
    ('=', 'iexact'),
    (':', 'icontains'),
])
def test_ops(op, django_op):
    query = MyTestQuery().bind(request=None)
    assert repr(query.parse('foo_name%sbar' % op)) == repr(Q(**{'foo__%s' % django_op: 'bar'}))


def test_parenthesis():
    query = MyTestQuery().bind(request=None)
    assert repr(query.parse('foo_name="asd" and (bar_name = 7 or baz_name = 11)')) == repr(Q(**{'foo__iexact': 'asd'}) & (Q(**{'bar__exact': 7}) | Q(**{'baz__iexact': 11})))


def test_request_to_q_advanced():

    q = MyTestQuery().bind(request=req('get'))
    query = MyTestQuery().bind(request=req('get', **{q.advanced_query_param(): 'foo_name="asd" and (bar_name = 7 or baz_name = 11)'}))
    assert repr(query.to_q()) == repr(Q(**{'foo__iexact': 'asd'}) & (Q(**{'bar__exact': 7}) | Q(**{'baz__iexact': 11})))


def test_request_to_q_simple():
    class Query2(MyTestQuery):
        bazaar = Variable.boolean(attr='quux__bar__bazaar', form__include=True)


    query2 = Query2().bind(request=req('get', **{'foo_name': "asd", 'bar_name': '7', 'bazaar': 'true'}))
    assert repr(query2.to_q()) == repr(Q(**{'foo__iexact': 'asd'}) & Q(**{'bar__exact': '7'}) & Q(**{'quux__bar__bazaar__iexact': 1}))


    query2 = Query2().bind(request=req('get', **{'foo_name': "asd", 'bar_name': '7', 'bazaar': 'false'}))
    assert repr(query2.to_q()) == repr(Q(**{'foo__iexact': 'asd'}) & Q(**{'bar__exact': '7'}) & Q(**{'quux__bar__bazaar__iexact': 0}))


def test_boolean_parse():
    class MyQuery(Query):
        foo = Variable.boolean()

    assert repr(MyQuery().bind(request=None).parse('foo=false')) == repr(Q(**{'foo__iexact': False}))
    assert repr(MyQuery().bind(request=None).parse('foo=true')) == repr(Q(**{'foo__iexact': True}))


def test_integer_request_to_q_simple():
    class Query2(Query):
        bazaar = Variable.integer(attr='quux__bar__bazaar', form=Struct(include=True))


    query2 = Query2().bind(request=req('get', bazaar='11'))
    assert repr(query2.to_q()) == repr(Q(**{'quux__bar__bazaar__iexact': 11}))


def test_gui_is_not_required():
    class Query2(Query):
        foo = Variable()
    assert Query2.foo.form.required is False


def test_invalid_value():
    q = Query(
        variables__bazaar=Variable.integer(
            value_to_q=lambda variable, op, value_string_or_f: None
        ),
    ).bind(request=req('get'))
    request = req('get', **{q.advanced_query_param(): 'bazaar=asd'})

    query2 = Query(
        variables__bazaar=Variable.integer(
            value_to_q=lambda variable, op, value_string_or_f: None
        ),
    ).bind(request=request)
    with pytest.raises(QueryException) as e:
        query2.to_q()
    assert 'Unknown value "asd" for variable "bazaar"' in str(e)


def test_invalid_variable():
    q = Query(
        variables__bazaar=Variable(),
    ).bind(request=req('get'))

    query2 = Query(
        variables__bazaar=Variable(),
    ).bind(request=req('get', **{q.advanced_query_param():'not_bazaar=asd'}))
    with pytest.raises(QueryException) as e:
        query2.to_q()
    assert 'Unknown variable "not_bazaar"' in str(e)


def test_invalid_form_data():

    query2 = Query(
        variables__bazaar=Variable.integer(attr='quux__bar__bazaar', form__include=True),
    ).bind(request=req('get', bazaar='asds'))
    assert query2.to_query_string() == ''
    assert repr(query2.to_q()) == repr(Q())


def test_none_attr():

    query2 = Query(
        variables__bazaar=Variable(attr=None, form__include=True),
    ).bind(request=req('get', bazaar='foo'))
    assert repr(query2.to_q()) == repr(Q())


def test_request_to_q_freetext():

    query = MyTestQuery().bind(request=req('get', **{FREETEXT_SEARCH_NAME: "asd"}))
    assert repr(query.to_q()) == repr(Q(**{'foo__icontains': 'asd'}) | Q(**{'bar__contains': 'asd'}))


def test_self_reference_with_f_object():
    query = MyTestQuery().bind(request=None)
    assert repr(query.parse('foo_name=bar_name')) == repr(Q(**{'foo__iexact': F('bar')}))


def test_null():
    query = MyTestQuery().bind(request=None)
    assert repr(query.parse('foo_name=null')) == repr(Q(**{'foo': None}))


def test_date():
    query = MyTestQuery().bind(request=None)
    assert repr(query.parse('foo_name=2014-03-07')) == repr(Q(**{'foo__iexact': date(2014, 3, 7)}))


def test_date_out_of_range():
    query = MyTestQuery().bind(request=None)
    with pytest.raises(QueryException) as e:
        query.parse('foo_name=2014-03-37')

    assert 'out of range' in str(e)


def test_invalid_syntax():
    query = MyTestQuery().bind(request=None)
    with pytest.raises(QueryException) as e:
        query.parse('asdadad213124av@$#$#')

    assert 'Invalid syntax for query' in str(e)


@pytest.mark.django_db
def test_choice_queryset():
    foos = [Foo.objects.create(foo=5), Foo.objects.create(foo=7)]

    # make sure we get either 1 or 3 objects later when we choose a random pk
    Bar.objects.create(foo=foos[0])
    Bar.objects.create(foo=foos[1])
    Bar.objects.create(foo=foos[1])
    Bar.objects.create(foo=foos[1])

    class Query2(Query):
        foo = Variable.choice_queryset(
            choices=Foo.objects.all(),
            form__include=True,
            value_to_q_lookup='foo')
        baz = Variable.choice_queryset(
            model=Foo,
            attr=None,
            choices=None,
        )

    random_valid_obj = Foo.objects.all().order_by('?')[0]

    # test GUI
    form = Query2().bind(
        request=req('post', **{'-': '-', 'foo': 'asdasdasdasd'}),
    ).form
    assert not form.is_valid()
    query2 = Query2().bind(request=req('post', **{'-': '-', 'foo': str(random_valid_obj.pk)}))
    form = query2.form
    assert form.is_valid()
    assert set(form.fields['foo'].choices) == set(Foo.objects.all())
    q = query2.to_q()
    assert set(Bar.objects.filter(q)) == set(Bar.objects.filter(foo__pk=random_valid_obj.pk))

    # test query
    query2 = Query2().bind(
        request=req('post', **{'-': '-', query2.advanced_query_param(): 'foo=%s and baz=buzz' % str(random_valid_obj.foo)}),
    )
    q = query2.to_q()
    assert set(Bar.objects.filter(q)) == set(Bar.objects.filter(foo__pk=random_valid_obj.pk))
    assert repr(q) == repr(Q(**{'foo__pk': random_valid_obj.pk}))

    # test searching for something that does not exist
    query2 = Query2().bind(
        request=req('post', **{'-': '-', query2.advanced_query_param(): 'foo=%s' % str(11)}),
    )
    value_that_does_not_exist = 11
    assert Foo.objects.filter(foo=value_that_does_not_exist).count() == 0
    with pytest.raises(QueryException) as e:
        query2.to_q()
    assert ('Unknown value "%s" for variable "foo"' % value_that_does_not_exist) in str(e)

    # test invalid ops
    valid_ops = ['=']
    for invalid_op in [op for op in Q_OP_BY_OP.keys() if op not in valid_ops]:
        query2 = Query2().bind(
            request=req('post', **{'-': '-', query2.advanced_query_param(): 'foo%s%s' % (invalid_op, str(random_valid_obj.foo))}),
        )
        with pytest.raises(QueryException) as e:
            query2.to_q()
        assert('Invalid operator "%s" for variable "foo"' % invalid_op) in str(e)

    # test a string with the contents "null"
    assert repr(query2.parse('foo="null"')) == repr(Q(foo=None))


@pytest.mark.django_db
def test_multi_choice_queryset():
    foos = [Foo.objects.create(foo=5), Foo.objects.create(foo=7)]

    # make sure we get either 1 or 3 objects later when we choose a random pk
    Bar.objects.create(foo=foos[0])
    Bar.objects.create(foo=foos[1])
    Bar.objects.create(foo=foos[1])
    Bar.objects.create(foo=foos[1])
    Bar.objects.create(foo=foos[1])
    Bar.objects.create(foo=foos[1])
    Bar.objects.create(foo=foos[1])

    class Query2(Query):
        foo = Variable.multi_choice_queryset(
            choices=Foo.objects.all(),
            form__include=True,
            value_to_q_lookup='foo')
        baz = Variable.multi_choice_queryset(
            model=Foo,
            attr=None,
            choices=None,
        )

    random_valid_obj, random_valid_obj2 = Foo.objects.all().order_by('?')[:2]

    # test GUI
    form = Query2().bind(request=req('post', **{'-': '-', 'foo': 'asdasdasdasd'})).form
    assert not form.is_valid()
    query2 = Query2().bind(request=req('post', **{'-': '-', 'foo': [str(random_valid_obj.pk), str(random_valid_obj2.pk)]}))
    form = query2.form
    assert form.is_valid()
    assert set(form.fields['foo'].choices) == set(Foo.objects.all())
    q = query2.to_q()
    assert set(Bar.objects.filter(q)) == set(Bar.objects.filter(foo__pk__in=[random_valid_obj.pk, random_valid_obj2.pk]))

    # test query
    query2 = Query2().bind(request=req('post', **{'-': '-', query2.advanced_query_param(): 'foo=%s and baz=buzz' % str(random_valid_obj.foo)}))
    q = query2.to_q()
    assert set(Bar.objects.filter(q)) == set(Bar.objects.filter(foo__pk=random_valid_obj.pk))
    assert repr(q) == repr(Q(**{'foo__pk': random_valid_obj.pk}))

    # test searching for something that does not exist
    query2 = Query2().bind(request=req('post', **{'-': '-', query2.advanced_query_param(): 'foo=%s' % str(11)}))
    value_that_does_not_exist = 11
    assert Foo.objects.filter(foo=value_that_does_not_exist).count() == 0
    with pytest.raises(QueryException) as e:
        query2.to_q()
    assert ('Unknown value "%s" for variable "foo"' % value_that_does_not_exist) in str(e)

    # test invalid ops
    valid_ops = ['=']
    for invalid_op in [op for op in Q_OP_BY_OP.keys() if op not in valid_ops]:
        query2 = Query2().bind(request=req('post', **{'-': '-', query2.advanced_query_param(): 'foo%s%s' % (invalid_op, str(random_valid_obj.foo))}))
        with pytest.raises(QueryException) as e:
            query2.to_q()
        assert('Invalid operator "%s" for variable "foo"' % invalid_op) in str(e)


@pytest.mark.django_db
def test_from_model_with_model_class():
    t = Query.from_model(model=Foo).bind(request=None)
    assert list(t.declared_variables.keys()) == ['id', 'foo']
    assert list(t.variables.keys()) == ['foo']


@pytest.mark.django_db
def test_from_model_with_queryset():
    t = Query.from_model(rows=Foo.objects.all()).bind(request=None)
    assert list(t.declared_variables.keys()) == ['id', 'foo']
    assert list(t.variables.keys()) == ['foo']


def test_from_model_foreign_key():
    class MyQuery(Query):
        class Meta:
            variables = Query.variables_from_model(model=Bar)

    t = MyQuery().bind(request=req('get'))
    assert list(t.declared_variables.keys()) == ['id', 'foo']
    assert isinstance(t.variables['foo'].choices, QuerySet)


@pytest.mark.django_db
def test_endpoint_dispatch():
    EndPointDispatchModel.objects.create(name='foo')
    x = EndPointDispatchModel.objects.create(name='bar')

    class MyQuery(Query):
        foo = Variable.choice_queryset(
            form__include=True,
            form__attr='name',
            choices=EndPointDispatchModel.objects.all().order_by('id'),
        )

    request = req('get')
    query = MyQuery().bind(request=request)

    assert '/foo' == query.form.fields.foo.endpoint_path()
    expected = {
        'results': [
            {'id': x.pk, 'text': str(x)},
        ],
        'pagination': {'more': False},
        'page': 1,
    }
    assert perform_ajax_dispatch(root=query, path='/form/fields/foo', value='ar') == expected
    assert perform_ajax_dispatch(root=query, path='/foo', value='ar') == expected


def test_endpoint_dispatch_errors():
    class MyQuery(Query):
        foo = Variable.choice(
            form__include=True,
            form__attr='name',
            choices=('a', 'b'),
        )

    q = MyQuery().bind(request=req('get'))

    assert perform_ajax_dispatch(
        root=MyQuery().bind(request=req('get', **{q.advanced_query_param(): 'foo=!'})),
        path='/errors',
        value='',
    ) == {'global': ['Invalid syntax for query']}
    assert perform_ajax_dispatch(
        root=MyQuery().bind(request=req('get', **{q.advanced_query_param(): 'foo=a'})),
        path='/errors',
        value='',
    ) == {}
    assert perform_ajax_dispatch(
        root=MyQuery().bind(request=req('get', foo='q')),
        path='/errors',
        value='',
    ) == {'fields': {'foo': ['q not in available choices']}}


def test_variable_repr():
    assert repr(Variable(name='foo')) == '<iommi.query.Variable foo>'


@pytest.mark.django_db
def test_nice_error_message():
    with pytest.raises(AttributeError) as e:
        value_to_query_string_value_string(Variable(value_to_q_lookup='name'), NonStandardName(non_standard_name='foo'))

    assert str(e.value) == "<class 'tests.models.NonStandardName'> object has no attribute name. You can specify another name property with the value_to_q_lookup argument. Maybe one of ['non_standard_name']?"

    with pytest.raises(AttributeError) as e:
        value_to_query_string_value_string(Variable(value_to_q_lookup='name'), Foo(foo=5))

    assert str(e.value) == "<class 'tests.models.Foo'> object has no attribute name. You can specify another name property with the value_to_q_lookup argument."


def test_escape_quote():
    class MyQuery(Query):
        foo = Variable(form__include=True)


    query = MyQuery().bind(request=Struct(method='GET', GET={'foo': '"', '-': '-'}))
    assert query.to_query_string() == 'foo="\\""'
    assert repr(query.to_q()) == repr(Q(**{'foo__iexact': '"'}))


def test_escape_quote_freetext():
    class MyQuery(Query):
        foo = Variable(freetext=True)


    query = MyQuery().bind(request=Struct(method='GET', GET={'term': '"', '-': '-'}))
    assert query.to_query_string() == '(foo:"\\"")'
    assert repr(query.to_q()) == repr(Q(**{'foo__icontains': '"'}))


def test_freetext_combined_with_other_stuff():
    class MyTestQuery(Query):
        foo_name = Variable(attr='foo', freetext=True, form__include=True)
        bar_name = Variable.case_sensitive(attr='bar', freetext=True, form__include=True)

        baz_name = Variable(attr='baz', form__include=True)

    expected = repr(Q(**{'baz__iexact': '123'}) & Q(Q(**{'foo__icontains': 'asd'}) | Q(**{'bar__contains': 'asd'})))

    assert repr(MyTestQuery().bind(request=req('get', **{'-': '-', 'term': 'asd', 'baz_name': '123'})).to_q()) == expected


@pytest.mark.django_db
def test_from_model_with_inheritance():
    was_called = defaultdict(int)

    class MyField(Field):
        @classmethod
        @class_shortcut
        def float(cls, call_target=None, **kwargs):
            was_called['MyField.float'] += 1
            return call_target(**kwargs)

    class MyForm(Form):
        class Meta:
            member_class = MyField

    class MyVariable(Variable):
        @classmethod
        @class_shortcut(
            form__call_target__attribute='float',
        )
        def float(cls, call_target=None, **kwargs):
            was_called['MyVariable.float'] += 1
            return call_target(**kwargs)

    class MyQuery(Query):
        class Meta:
            member_class = MyVariable
            form_class = MyForm

    query = MyQuery.from_model(
        rows=FromModelWithInheritanceTest.objects.all(),
        model=FromModelWithInheritanceTest,
        variables__value__form__include=True,
    )
    query.bind(request=req('get'))

    assert was_called == {
        'MyField.float': 1,
        'MyVariable.float': 1,
    }


@pytest.mark.parametrize('name, shortcut', get_shortcuts_by_name(Variable).items())
def test_shortcuts_map_to_form(name, shortcut):
    if name == 'case_sensitive':  # This has no equivalent in Field
        return

    # TODO: why doesn't this exist in Field?
    if name == 'foreign_key':  # This has no equivalent in Field
        return

    # TODO: why doesn't this exist in Field?
    if name == 'many_to_many':  # This has no equivalent in Field
        return

    assert shortcut.dispatch.form.call_target.attribute == name
