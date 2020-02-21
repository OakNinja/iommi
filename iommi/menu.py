from pathlib import PurePosixPath
from typing import (
    Dict,
    Union,
)
from urllib.parse import (
    unquote,
    urlparse,
)

from tri_declarative import (
    EMPTY,
    Refinable,
    dispatch,
    declarative,
    with_meta,
)
from tri_struct import Struct

from iommi import Part
from iommi._web_compat import (
    Template,
)
from iommi.endpoint import path_join
from iommi.member import (
    collect_members,
    bind_members,
)
from iommi.traversable import (
    EvaluatedRefinable,
)
from iommi.attrs import Attrs
from iommi.page import Fragment


class MenuBase(Part):
    tag: str = EvaluatedRefinable()
    sort: bool = EvaluatedRefinable()  # only applies for submenu items
    sub_menu: Dict = Refinable()
    attrs: Attrs = Refinable()  # attrs is evaluated, but in a special way so gets no EvaluatedRefinable type
    template: Union[str, Template] = EvaluatedRefinable()

    @dispatch(
        sort=True,
        sub_menu=EMPTY,
        attrs=EMPTY,
    )
    def __init__(self, sub_menu, _sub_menu_dict=None, **kwargs):
        super(MenuBase, self).__init__(**kwargs)

        collect_members(
            self,
            name='sub_menu',
            items=sub_menu,
            # TODO: cls=self.get_meta().member_class,
            items_dict=_sub_menu_dict,
            cls=MenuItem,
        )

    def __repr__(self):
        r = '%s -> %s\n' % (self._name, self.url)
        for items in self.sub_menu.values():
            r += '    ' + repr(items)
        return r

    def on_bind(self):
        bind_members(self, name='sub_menu')

        if self.sort:
            self.sub_menu = Struct({
                item._name: item
                for item in sorted(self.sub_menu.values(), key=lambda x: x.display_name)
            })

    def own_evaluate_parameters(self):
        return dict(menu_item=self)


class MenuItem(MenuBase):
    """
    Class that is used for the clickable menu items in a menu.

    See :doc:`Menu` for more complete examples.
    """

    display_name: str = EvaluatedRefinable()
    url: str = EvaluatedRefinable()
    regex: str = EvaluatedRefinable()
    group: str = EvaluatedRefinable()

    @dispatch(
        display_name=lambda menu_item, **_: menu_item._name.title().replace('_', ' '),
        regex=lambda menu_item, **_: '^' + menu_item.url if menu_item.url else None,
        url=lambda menu_item, **_: '/' + path_join(getattr(menu_item._parent, 'url', None), menu_item._name) + '/',
        a__tag='a',
    )
    def __init__(self, *, a, **kwargs):
        super(MenuItem, self).__init__(**kwargs)
        self.fragment = None
        self.a = a

    def on_bind(self):
        super(MenuItem, self).on_bind()

        # If this is a section header, and all sub-parts are hidden, hide myself
        if not self.url and not self.sub_menu:
            self.include = False

        self.a = Fragment(
            self.display_name,
            attrs__href=self.url,
            **self.a,
        ).bind(parent=self)
        self.fragment = Fragment(
            self.a,
            tag=self.tag,
            template=self.template,
            attrs=self.attrs,
            children=self.sub_menu,
        ).bind(parent=self)

    def __html__(self, *, context=None, render=None):
        return self.fragment.__html__()


class MenuException(Exception):
    pass


@with_meta
@declarative(MenuItem, '_sub_menu_dict')
class Menu(MenuBase):
    """
    Class that describes menus.

    Example:

    .. code:: python

        menu = Menu(
            sub_menu=dict(
                root=MenuItem(url='/'),

                albums=MenuItem(url='/albums/'),

                # url defaults to /<name>/ so we
                # don't need to write /musicians/ here
                musicians=MenuItem(),
            ),
        )
    """

    @dispatch(
        sort=False
    )
    def __init__(self, **kwargs):
        super(Menu, self).__init__(**kwargs)
        self.fragment = None

    def __html__(self, *, context=None, render=None):
        return self.fragment.__html__()

    def on_bind(self):
        super(Menu, self).on_bind()
        self.validate_and_set_active(current_path=self.get_request().path)

        self.fragment = Fragment(
            tag=self.tag,
            template=self.template,
            attrs=self.attrs,
            children=self.sub_menu,
        ).bind(parent=self)

    def validate_and_set_active(self, current_path: str):

        # verify there is no ambiguity for the MenuItems
        paths = set()
        for item in self.sub_menu.values():
            if '://' in item.url:
                continue

            path = urlparse(item.url).path
            if path in paths:
                raise MenuException(f'MenuItem paths are ambiguous; several non-external MenuItems have the path: {path}')

            paths.add(path)

        current = None
        current_parts_matching = 0
        path_parts = PurePosixPath(current_path).parts

        items = [(item, urlparse(item.url)) for item in self.sub_menu.values()]
        for (item, parsed_url) in items:
            if '://' in item.url:
                continue

            if current_path.startswith(parsed_url.path):
                parts = PurePosixPath(unquote(parsed_url.path)).parts
                matching_parts = 0
                for i in range(min(len(parts), len(path_parts))):
                    if parts[i] is path_parts[i]:
                        matching_parts += 1

                if matching_parts > current_parts_matching:
                    current = (item, parsed_url)
                    current_parts_matching = matching_parts

        if current:
            current[0].a.attrs.setdefault('class', {})
            current[0].a.attrs['class']['active'] = True