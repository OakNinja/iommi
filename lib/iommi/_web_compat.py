try:
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email, URLValidator
    from django.http import HttpResponse
    from django.template import RequestContext
    from django.template.loader import render_to_string
    from django.utils.html import format_html
    from django.utils.text import slugify
    from django.http import HttpResponseRedirect
    from django.template import Template
    from django.shortcuts import render
    from django.utils.encoding import smart_str
    from django.template.context_processors import csrf as csrf_
    from django.utils.safestring import mark_safe

    def csrf(request):
        return {} if request is None else csrf_(request)

    try:
        from django.template.loader import get_template_from_string
    except ImportError:  # pragma: no cover
        # Django 1.8+
        # noinspection PyUnresolvedReferences
        from django.template import engines

        def get_template_from_string(template_code, origin=None, name=None):
            del origin, name  # the origin and name parameters seems not to be implemented in django 1.8
            return engines['django'].from_string(template_code)

    def render_template(request, template, context):
        """
        @type request: django.http.HttpRequest
        @type template: str|django.template.Template|django.template.backends.django.Template
        @type context: dict
        """
        import six
        from iommi._web_compat import Template
        if template is None:
            return ''
        elif isinstance(template, six.string_types):
            # positional arguments here to get compatibility with django 1.8+
            return render_to_string(template, context, request=request)
        elif isinstance(template, Template):
            return template.render(RequestContext(request, context))
        else:
            return template.render(context, request)

except ImportError:
    from jinja2 import Markup
    from jinja2 import Template as _Template
    from flask import render_template as render
    from flask import Response as _Response
    from flask import Request as _Request

    csrf = None

    class HttpResponse:
        def __init__(self, content, content_type=None):
            self.r = _Response(content, content_type=content_type)

        @property
        def content(self):
            return self.r.get_rows()

        @property
        def _headers(self):
            return {k.lower(): [v] for k, v in self.r.headers._list}

    class HttpRequest:

        def __init__(self, environ):
            self.r = _Request(environ)

        @property
        def POST(self):
            return self.r.form

        @property
        def GET(self):
            return self.r.args

        @property
        def method(self):
            return self.r.method

        @property
        def META(self):
            return self.r.environ

        def is_ajax(self):
            return self.r.environ.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    def format_html(format_string, *args, **kwargs):
        return Markup(format_string).format(*args, **kwargs)

    class ValidationError(Exception):
        def __init__(self, messages):
            if isinstance(messages, list):
                self.messages = messages
            else:
                self.messages = [messages]

    def HttpResponseRedirect(url, code=302):
        from flask import redirect
        return redirect(url, code=code)

    def smart_str(s):
        return str(s)

    def render_template(request, template, context):
        if template is None:
            return ''

        if isinstance(template, str):
            return Markup(render(template, **(context or {})))
        else:
            return Markup(template.render(context=context, request=request))

    def validate_email(s):
        if '@' not in s:
            raise ValidationError(messages=['Enter a valid email address.'])

        return s

    class URLValidator:
        def __call__(self, string_value):
            if '://' not in string_value:
                raise ValidationError('Enter a valid URL.')

    def get_template_from_string(s, origin=None, name=None):
        return Template(s)

    def render_to_string(template_name, context, request=None):
        return format_html(render(template_name, request=request, **context))

    class Template:
        def __init__(self, template_string, **kwargs):
            self.template = _Template(template_string, **kwargs)

        def render(self, context, request=None):
            return self.template.render(**context)

    def slugify(s):
        return s.lower().replace(' ', '-')

    def mark_safe(s):
        return Markup(s)


smart_text = smart_str
