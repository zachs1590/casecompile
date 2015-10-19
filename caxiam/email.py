from django.conf import settings
from django.core.mail import send_mail as django_send_mail, EmailMultiAlternatives
from django.db import models
from django.template import Context
from django.template.loader import get_template, select_template

from caxiam.common import Enumeration
from caxiam.model_mixins import OverridableChoicesMixin

import datetime
import re
import os
import os.path

# You will need to define some values in your settings file
# in order to use this, in addition to the regular email
# settings.
#
#   CAXIAM_EMAIL_FROM               sender address for email (not the same as mail server username)
#   CAXIAM_EMAIL_OVERRIDE_TOLIST    if set, replaces ALL email destination addresses with this list (for debugging)
#   CAXIAM_EMAIL_TEMPLATE_BASE      base directory in templates that contains email
#   CAXIAM_EMAIL_FAIL_SILENTLY      whether to ignore errors in email; DO NOT set True for production
#
# Email templates are stored in folders, in this hierarchy:
#
#   <email_template_base>/email/<template_path>/<brand>/subject.txt         subject line of message
#   <email_template_base>/email/<template_path>/<brand>/body.txt            plaintext body of message
#   <email_template_base>/email/<template_path>/<brand>/body.html           HTML body of message (TODO)
#
# The default <brand> is "base".
#
# All templates will be passed the same data, and ONLY
# that data; this is not a RequestContext so will not have
# any template context processors applied to it. You may
# also pass in a Context-derived object and it will be
# passed as-is, so you can pass a RequestContext if you
# like.
#
# NOTE: previous code versions used ILCLOUD_ instead of
# CAXIAM_ as this code originated from Innovative Leisure;
# be sure to update if things are breaking.

# prep and send an email message
def send_mail(template_path, brand, tolist, from_email = None, data = None):
    if from_email == None:
        from_email = settings.CAXIAM_EMAIL_FROM
    if data == None:
        data = {}

    # make sure the path has been lower-cased
    template_path = os.path.join(settings.CAXIAM_EMAIL_TEMPLATE_BASE, 'email', template_path.lower())

    # decide if we're looking for a brand-specific template or not
    if brand == None:
        template_paths = [ os.path.join(template_path, 'base') ]
    else:
        template_paths = [ os.path.join(template_path, brand), os.path.join(template_path, 'base') ]

    body_list = [ os.path.join(p, 'body.txt') for p in template_paths ]
    body_list.extend([ os.path.join(p, 'body.html') for p in template_paths ])
    # fetch the templates
    subject_template = select_template([ os.path.join(p, 'subject.txt') for p in template_paths ])
    body_template = select_template(body_list)
    # If you include the file html_type inside one of the appropriate folders, then it will render out as an HTML email
    # If the templates do not exist they will throw a template not found error
    html_type = False
    if re.match('.*\.html', body_template.name):
        html_type = True

    # fill out the template

    # we'd love to use RequestContext but we don't have request
    # this deep in the call stack; we hope that if someone needs
    # that they will create a RequestContext object and pass it
    # as data
    if not isinstance(data, Context):
        data = Context(data)

    # we have additional data we need to supply, so that all
    # email templates can be rendered appropriately (e.g. HTML
    # templates need to know what external URL to use for any
    # images)
    data.update({
            'from_email': from_email,
            'site_hostname': settings.CAXIAM_EMAIL_SITE_HOSTNAME,
            'site_url': settings.CAXIAM_SITE_PROTOCOL + settings.CAXIAM_EMAIL_SITE_HOSTNAME + '/',
        })

    # use the same context for subject and body
    subject = subject_template.render(data)
    body = body_template.render(data)

    # send the email
    if settings.CAXIAM_EMAIL_OVERRIDE_TOLIST:
        print "[pid:%d]" % os.getpid(), "SENDING EMAIL TO " + repr(settings.CAXIAM_EMAIL_OVERRIDE_TOLIST) + " instead of " + repr(tolist)
        tolist = settings.CAXIAM_EMAIL_OVERRIDE_TOLIST
    else:
        print "[pid:%d]" % os.getpid(), "SENDING EMAIL TO " + repr(tolist)

    # If it's an html type email then it will need to adjusted so that it's sending it out via the Email Mulit Type
    # Zach: **** This may be something we come back to so we can only use 1 instead of using both.
    if html_type:
        msg = EmailMultiAlternatives(subject, body, from_email, tolist)
        msg.content_subtype = "html"  # Main content is no text/html
        msg.send(fail_silently = settings.CAXIAM_EMAIL_FAIL_SILENTLY)
    else:
        django_send_mail(subject, body, from_email, tolist, fail_silently = settings.CAXIAM_EMAIL_FAIL_SILENTLY)


# a base email address class that can track its validation
# state; derive from the class and provide any additional
# foreign keys required for your app
class AbstractEmail(OverridableChoicesMixin, models.Model):
    class Meta(object):
        abstract = True

    VERIFICATION_STATES = Enumeration(
            (-3, 'BLOCKED'),       ## Owner opted out of all emails (**** needs implementing)
            (-2, 'VALID'),         ## Known Good
            (-1, 'INVALID'),       ## Known Bad
            ( 0, 'UNVERIFIED'),    ## link sent, awaiting response
            # ... more in-progress unverified states
        )

    address = models.CharField(max_length = 200, db_index = True)    # intentionally long, but MUST BE INDEXED
    status = models.IntegerField(choices = VERIFICATION_STATES.choices)

    date_created = models.DateTimeField(auto_now = False, auto_now_add = False, default = datetime.datetime.now)
    # This is used to indicate when the current status was made
    date_validated  = models.DateTimeField(auto_now = False, auto_now_add = False, blank=True, null=True)

    # We are running the init function to override the status choices
    def __init__(self, *args, **kwargs):
        super(AbstractEmail, self).__init__(*args, **kwargs)
        self._set_field_choices(field_name = 'status', choices = self.VERIFICATION_STATES)

    # a helper method to automatically mark an email address as
    # verified and mark all other copies of the same address as
    # invalid
    #
    # NOTE: if your derived class overrides VERIFICATION_STATES
    # such that VALID is renamed or renumbered, you will want
    # to override this method; better yet, don't modify VALID
    #
    # NOTE: unless you pass save = False, this will update the
    # database
    #
    def mark_as_valid(self, save = True):
        # first, update ourselves
        self.status = self.VERIFICATION_STATES.VALID
        self.date_validated = datetime.datetime.utcnow()
        if save:
            self.save(update_fields = [ 'status', 'date_validated' ])

        # second, look for other records in UNVERIFIED
        self.__class__.objects.filter(
                address = self.address, status = self.VERIFICATION_STATES.UNVERIFIED,
            ).exclude(
                id = self.id,
            ).update(
                status = self.VERIFICATION_STATES.INVALID,
            )
