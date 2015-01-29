#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest
from bs4 import BeautifulSoup
from django.test import RequestFactory
from tri.tables import render_table_to_response, Struct, Table, Column


def _check_html(table, expected_html):
    """
    Verify that the table renders to the expected markup, modulo formatting
    """
    actual_html = str(render_table_to_response(request=RequestFactory().request(), table=table))

    prettified_actual = BeautifulSoup(actual_html).find('table').prettify().strip()
    prettified_expected = BeautifulSoup(expected_html).find('table').prettify().strip()

    assert prettified_expected == prettified_actual


def data():
    return [
        Struct(foo="Hello", bar=17),
        Struct(foo="world!", bar=42)
    ]


def explicit_table():

    columns = [
        Column(name="foo"),
        Column.number(name="bar"),
    ]

    return Table(data(), columns, attrs=dict(id='table_id'))


def declarative_table():

    class TestTable(Table):

        class Meta:
            attrs = dict(id='table_id')

        foo = Column()
        bar = Column.number()

    return TestTable(data())


@pytest.mark.parametrize('table', [
    explicit_table(),
    declarative_table()
])
def test_render(table):

    _check_html(table, """\
<table class="listview" id="table_id">
 <thead>
  <tr>
   <th class="subheader first_column first_column">
    <a href="?order=foo"> Foo </a>
   </th>
   <th class="subheader first_column ">
    <a href="?order=bar"> Bar </a>
   </th>
  </tr>
 </thead>
 <tr class="row1 ">
  <td> Hello </td>
  <td class="rj"> 17 </td>
 </tr>
 <tr class="row2 ">
  <td> world! </td>
  <td class="rj"> 42 </td>
 </tr>
</table>""")


def test_output():

    is_report = False

    class TestTable(Table):

        class Meta:
            attrs = dict(id='table_id')

        foo = Column()
        bar = Column.number()
        icon = Column.icon('history', is_report, group="group")
        edit = Column.edit(is_report, group="group")
        delete = Column.delete(is_report)

    data = [
        Struct(foo="Hello räksmörgås ><&>",
               bar=17,
               get_absolute_url=lambda: '/somewhere/'),
    ]

    _check_html(TestTable(data), """\
<table class="listview" id="table_id">
 <thead>
 <tr>
   <th class="superheader first_column" colspan="1"> </th>
   <th class="superheader " colspan="1"> </th>
   <th class="superheader " colspan="2"> group </th>
   <th class="superheader " colspan="1"> </th>
  </tr>
  <tr>
   <th class="subheader first_column first_column">
    <a href="?order=foo"> Foo </a>
   </th>
   <th class="subheader first_column ">
    <a href="?order=bar"> Bar </a>
   </th>
   <th class="subheader first_column first_column"> </th>
   <th class="subheader " title="Edit"> </th>
   <th class="subheader first_column first_column" title="Delete"> </th>
  </tr>
 </thead>
 <tr class="row1 ">
  <td> Hello räksmörgås &gt;&lt;&amp;&gt; </td>
  <td class="rj"> 17 </td>
  <td> <i class="fa fa-lg fa-history"> </i> </td>
  <td> <a href="/somewhere/edit/"> <i class="fa fa-lg fa-pencil-square-o" title="Edit"> </i> </a> </td>
  <td> <a href="/somewhere/delete/"> <i class="fa fa-lg fa-trash-o" title="Delete"> </i> </a> </td>
 </tr>
</table>
""")
