from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.template.loader import find_template, TemplateDoesNotExist
from django.views.generic import TemplateView

from caxiam.view_mixins import LoginRequiredMixin

import os.path


# TemplateView to allow custom context
#------------------------------
class ContextTemplateView(LoginRequiredMixin, TemplateView):

    def custom_context_data(self, request, **kwargs):
        return kwargs

    def get(self, request, **kwargs):
        # This version is more correct than the one in rjr because it includes the original get_context_data from the template view.
        context = self.custom_context_data(request = request, **super(ContextTemplateView, self).get_context_data(**kwargs))
        return self.render_to_response(context)

# generic message template view, suitable for errors
# or confirmation pages
#
# NOTE: make sure you require a valid part1; do not map
# only the base path to this view
#
# NOTE: MAKE DOUBLY-SURE YOU HAVE FILTERED BOTH PARTS
# TO BE SLUG-ONLY CHARACTERS, OR YOU OPEN UP A SECURITY
# HOLE!
#
class MessageDisplayView(TemplateView):
    base_folder = None      # to define an explicit path
    base_folder_tag = None  # to look up the tag in settings.CAXIAM_MESSAGE_TEMPLATES
    status_code = None      # in case specific URLs need to return specific error codes
    
    def get(self, request, part1, part2 = None, status_code = None):
    
        # fill in status code
        if status_code == None:
            status_code = self.status_code
        if status_code == None:
            status_code = 200
    
        # make sure the view is configured correctly
        if self.base_folder_tag != None:
            self.base_folder = settings.CAXIAM_MESSAGE_TEMPLATES[self.base_folder_tag]      # raises KeyError if the tag is bad, which is more helpful than falling into the next exception case
        if self.base_folder == None:
            raise Exception('base folder for message not configured; edit urls.py to fix this')
    
        # render and return the result, or raise an exception
        return self.render_html_message(request, self.base_folder, part1, part2, status_code = status_code)

    # raw message renderer, abstracted out because it may be
    # called from outside this view
    @classmethod
    def render_html_message(cls, request, base_folder, part1, part2 = None, context = None, status_code = 200, raise404 = True):

        # make sure context is a dictionary
        if context == None:
            context = {}
    
        # determine the correct template path
        if part2 == None:
            template_path = os.path.join(base_folder, part1)
        else:
            template_path = os.path.join(base_folder, part1, part2)
        
        template_path += '.html'
        print '>>>> rendering message template:', template_path
        
        # see if that template exists
        try:
            template_file = find_template(template_path)
        except TemplateDoesNotExist, e:
            # it's possible this function may be invoked from inside
            # a 404 handler; in that case we do not want to re-raise
            # a 404 as that would create an exception loop; instead,
            # just re-raise the original exception
            if raise404:
                raise Http404
            else:
                raise
        
        # when we pass this off to render, it will actually
        # search for the template again, which is inefficient;
        # however, if the template has already been cached,
        # both "searches" hit the cache instead of the file
        # system, so they are essentially free
        return render(request, template_path, context, status = status_code)

#
# these replacement error handlers are used because they will
# return HTML and correct status codes WITHOUT changing the URL;
# if we returned a redirect the user would get the wrong URL
# and (perhaps) the wrong status code
#
        
# a replacement 403 error handler, that invokes our renderer
def caxiam_403(request):

    return MessageDisplayView.render_html_message(
            request,
            settings.CAXIAM_MESSAGE_TEMPLATES['error'],
            'not-allowed',
            context = { 'request_path': request.path },
            status_code = 403,
            raise404 = False
        )
        
# a replacement 404 error handler, that invokes our renderer
def caxiam_404(request):

    return MessageDisplayView.render_html_message(
            request,
            settings.CAXIAM_MESSAGE_TEMPLATES['error'],
            'not-found',
            context = { 'request_path': request.path },
            status_code = 404,
            raise404 = False
        )
        
# a replacement 500 error handler, that invokes our renderer
def caxiam_500(request):

    return MessageDisplayView.render_html_message(
            request,
            settings.CAXIAM_MESSAGE_TEMPLATES['error'],
            'server-hiccup',
            context = { 'request_path': request.path },
            status_code = 500,
            raise404 = False
        )
