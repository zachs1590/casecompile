from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template, render_to_string
from django.utils.encoding import force_text
from caxiam.common import to_json
import json

# Base AJAX response class. Expects a fully-formatted response
# blob to be present at initialization.
#
class AjaxResponseBase(HttpResponse):

    def __init__(self, response, *args, **kwargs):
        super(AjaxResponseBase, self).__init__(*args, **kwargs)
        self['Content-Type'] = 'application/json'
        self.content = json.dumps(response)

#
# success-ish responses
#

# AJAX success response
#
# this is pretty much specific to each request so it's impossible
# to validate
#
class AjaxSuccessResponse(AjaxResponseBase):

    def __init__(self, response):
        # nothing to verify in the response; as long as it
        # serializes to JSON, that's fine
        super(AjaxSuccessResponse, self).__init__({ 'results' : response })

# AJAX HTML update response
#
# NOTE: response should be a list of dicts with keys 'id' and 'html':
# [ { 'id': 'foo', 'html': '<p>bar</p>' }, ]
# These will be replaced in the order listed without further
# scripting required.
#
class AjaxHTMLResponse(AjaxResponseBase):

    def __init__(self, response):
        for item in response:
            if 'id' not in item or 'html' not in item:
                raise Exception('AJAX HTML response requested but an item is missing either id or html keys')

        super(AjaxHTMLResponse, self).__init__({ 'html' : response })

# AJAX toast response
#
# NOTE: response may be either a single toast dict or a list of
# toast dicts. Each toast dict may contain the following keys:
#
#   class_name  toast subclass name; must have supporting CSS
#   html        the actual HTML to use
#   duration    how long the toast should display for; use 0 to require manual dismissal
#   delay       after the toast is dismissed, how long to wait before showing the next toast
#
# Any items not provided will be filled with defaults client-side,
# but the html value should ALWAYS be given as there's not much
# point otherwise.
#
class AjaxToastResponse(AjaxResponseBase):

    def __init__(self, response = None, **kwargs):
        # this really should verify the required keys are present in the response
        # list items (duration, class_name, html) but they're actually all
        # optional so oh well...
        super(AjaxToastResponse, self).__init__({ 'toast' : response })

# AJAX modal response
#
class AjaxModalResponse(AjaxResponseBase):

    def __init__(self, response = None, **kwargs):
        if not response:
            keys = ['code', 'title', 'message']
            if 'size' in kwargs and kwargs['size'] != None:
                # NOTE: we ignore size if it's None as it confuses the JavaScript
                keys.append('size')
            response = to_json(kwargs, keys)    # extract just the bits that are valid, and make sure they're JSON-able
        super(AjaxModalResponse, self).__init__({ 'modal' : response })

# AJAX mixed response: one or more of results, modal, html, toast
#
class AjaxMixedResponse(AjaxResponseBase):

    def __init__(self, **kwargs):
        valid_response = False
        for k in [ 'results', 'modal', 'html', 'toast' ]:
            if k in kwargs:
                valid_response = True
                break
        if not valid_response:
            raise Exception('AJAX mixed response requested but no recognized response types provided')

        super(AjaxMixedResponse, self).__init__(kwargs)

    # a very, very common pattern is to create a toast
    # or modal response, accompanied by a batch of HTML
    # updates, but to have all of that data configured
    # in urls.py and even to have different responses
    # to the same request based on what happens in the
    # data (e.g. removing an item from the cart instead
    # of updating it because the quantity was set to
    # zero)
    #
    # to faciliate this, we provide this factory method
    # that produces a mixed response, rendering templates
    # with the given context data
    #
    # this expects a response_data dict with the
    # following keys (all optional):
    #
    #   toast_template_name a toast response
    #   toast_duration      how long to leave the toast up
    #   modal_template_name a modal response
    #   modal_title_template_name   modal's title template
    #   modal_title         bare string for modal title (not template)
    #   updates             a list:
    #       html_id         the HTML ID to be updated
    #       template_name   the template to render
    #
    # if a modal is returned, its code will be null
    #
    # as a convenience, you can disable the modal or
    # toast with an additional flag so you don't have
    # to clobber the response configuration
    #
    @classmethod
    def create(cls, context, response_data, show_modal = True, show_toast = True, show_updates = True):
        response = {}

        # do a modal
        if show_modal and 'modal_template_name' in response_data:
            modal_template = get_template(response_data['modal_template_name'])
            modaL_html = modal_template.render(context)
            if 'modal_title' in response_data:
                modal_title = response_data['modal_title']
            else:
                modal_title_template = get_template(response_data['modal_title_template_name'])
                modal_title = modal_title_template.render(context)
            response['modal'] = {
                    'code': None,
                    'title': modal_title,
                    'message': modal_html,
                }

        # do toast
        if show_toast and 'toast_template_name' in response_data:
            toast_template = get_template(response_data['toast_template_name'])
            toast_html = toast_template.render(context)
            response['toast'] = {
                    'duration': response_data.get('toast_duration', settings.ACPRO_DEFAULT_TOAST_DURATION),
                    'html': toast_html,
                }

        # do HTML updates
        # the actual rendering piece is in AjaxView,
        # at least for now; it really should be
        # extracted and put somewhere more sensible
        from caxiam.ajax.views import AjaxView
        
        if show_updates and 'updates' in response_data:
            response['html'] = AjaxView.render_html_templates(context, response_data['updates'])
            
        # now create the response based on what we have
        return AjaxMixedResponse(**response)
        
#
# error-ish responses
#

# AJAX redirect response
#
class AjaxRedirectResponse(AjaxResponseBase):

    def __init__(self, response):
        # this really should verify that the response is a string
        super(AjaxRedirectResponse, self).__init__({ 'location' : response })

# AJAX exception response
# NOTE: this is NOT an Exception, it's a response
#
class AjaxExceptionResponse(AjaxResponseBase):

    def __init__(self, response = None, **kwargs):
        if not response:
            response = to_json(kwargs, ['code', 'title', 'message'])
        # this really should verify the required keys are present in the response
        # (code, title, message)
        super(AjaxExceptionResponse, self).__init__({ 'exception' : response })

# AJAX error response
# NOTE: this is NOT an Exception, it's a response
#
class AjaxErrorResponse(AjaxResponseBase):

    def __init__(self, response = None, **kwargs):
        if not response:
            response = to_json(kwargs, ['code', 'title', 'message'])
        # this really should verify the required keys are present in the response
        # (code, title, message)
        super(AjaxErrorResponse, self).__init__({ 'error' : response })

# AJAX form error response
#
class AjaxFormErrorResponse(AjaxResponseBase):

    def __init__(self, form, last_field = None, focus_field = None):
        # check whether this is a partial validation response
        is_partial = last_field != None
        
        # we shouldn't do this unless we actually have form errors;
        # that would be a programming mistake
        # NOTE: we'll accept a partial-validation error-free state
        if not is_partial and not form._errors:
            raise Exception('attempt to return form errors when there are none')

        # we need to format the errors in the form in a way that
        # is suitable for our AJAX handler on the client
        #
        # NOTE: Django's method is that the ValidationError and
        # ErrorList classes should "know" how to format themselves,
        # but they left very little in the way of ability to
        # intelligently override that. Instead, we act as though
        # errors are collected into a well-defined format, and
        # the layer that returns these errors to the client is
        # responsible for correctly formatting them.

        # we walk the error list in field declaration order
        error_list = []
        for name, field in form.fields.iteritems():
            if name in form._errors:
                field_error_list = []
                for message in form._errors[name]:
                    field_error_list.append(force_text(message))
                # use prefixed name so client side can find it
                error_list.append([ form.add_prefix(name), field.label, field_error_list ])

        # now append the global errors
        name = '__all__'
        if name in form._errors:
            field_error_list = []
            for message in form._errors[name]:
                field_error_list.append(force_text(message))
            error_list.append([ None, None, field_error_list ])

        # now that we have a formatted error list, return it
        results = {
                'form_error': error_list,
            }
        if is_partial:
            results['partial'] = {
                    'last_field': form.add_prefix(last_field),
                    'focus_field': form.add_prefix(focus_field),
                }

        super(AjaxFormErrorResponse, self).__init__(results)

