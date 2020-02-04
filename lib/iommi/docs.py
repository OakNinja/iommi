from tri_declarative import (
    Namespace,
    get_declared,
    flatten_items,
    get_shortcuts_by_name,
)


def generate_rst_docs(directory, classes, missing_objects=None):  # pragma: no coverage
    """
    Generate documentation for tri.declarative APIs

    :param directory: directory to write the .rst files into
    :param classes: list of classes to generate documentation for
    :param missing_objects: tuple of objects to count as missing markers, if applicable
    """

    doc_by_filename = _generate_rst_docs(classes=classes, missing_objects=missing_objects)  # pragma: no mutate
    for filename, doc in doc_by_filename:  # pragma: no mutate
        with open(directory + filename, 'w') as f2:  # pragma: no mutate
            f2.write(doc)  # pragma: no mutate


def get_docs_callable_description(c):
    if getattr(c, '__name__', None) == '<lambda>':
        import inspect
        try:
            return inspect.getsource(c).strip()
        except OSError:
            pass
    return c.__module__ + '.' + c.__name__


def _generate_rst_docs(classes, missing_objects=None):
    if missing_objects is None:
        missing_objects = tuple()

    import re

    def docstring_param_dict(obj):
        doc = obj.__doc__
        if doc is None:
            return dict(text=None, params={})
        return dict(
            text=doc[:doc.find(':param')].strip() if ':param' in doc else doc.strip(),
            params=dict(re.findall(r":param (?P<name>\w+): (?P<text>.*)", doc))
        )

    def indent(levels, s):
        return (' ' * levels * 4) + s.strip()

    def get_namespace(c):
        return Namespace(
            {k: c.__init__.dispatch.get(k) for k, v in get_declared(c, 'refinable_members').items()})

    for c in classes:
        from io import StringIO
        f = StringIO()

        def w(levels, s):
            f.write(indent(levels, s))
            f.write('\n')

        def section(level, title):
            underline = {
                0: '=',
                1: '-',
                2: '^',
            }[level] * len(title)
            w(0, title)
            w(0, underline)
            w(0, '')

        section(0, c.__name__)

        class_doc = docstring_param_dict(c)
        constructor_doc = docstring_param_dict(c.__init__)

        if class_doc['text']:
            f.write(class_doc['text'])
            w(0, '')

        if constructor_doc['text']:
            if class_doc['text']:
                w(0, '')

            f.write(constructor_doc['text'])
            w(0, '')

        w(0, '')

        section(1, 'Refinable members')
        for refinable, value in sorted(dict.items(get_namespace(c))):
            w(0, '* `' + refinable + '`')

            if constructor_doc['params'].get(refinable):
                w(1, constructor_doc['params'][refinable])
                w(0, '')
        w(0, '')

        defaults = Namespace()
        for refinable, value in sorted(get_namespace(c).items()):
            if value not in (None,) + missing_objects:
                defaults[refinable] = value

        if defaults:
            section(2, 'Defaults')

            for k, v in sorted(flatten_items(defaults)):
                if v != {}:
                    if callable(v):
                        v = get_docs_callable_description(v)

                        if 'lambda' in v:
                            v = v[v.find('lambda'):]
                            v = v.strip().strip(',')

                    if v == '':
                        v = '""'

                    w(0, '* `%s`' % k)
                    w(1, '* `%s`' % v)
            w(0, '')

        shortcuts = get_shortcuts_by_name(c)
        if shortcuts:
            section(1, 'Shortcuts')

            for name, shortcut in sorted(shortcuts.items()):
                section(2, f'`{name}`')

                if shortcut.__doc__:
                    doc = shortcut.__doc__
                    f.write(doc.strip())
                    w(0, '')
                    w(0, '')

        yield '/%s.rst' % c.__name__, f.getvalue()
