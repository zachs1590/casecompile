from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.http import HttpResponseRedirect
from django.utils import timezone

from caxiam.common import Enumeration
from caxiam.email import send_mail
from caxiam.hash_generator import ModelHashGenerator
from caxiam.modeltools import FastSave
from jsonfield import JSONField

import datetime

# some exception classes related to PayloadLinks
class PayloadLinkException(Exception): pass

class PayloadLinkPrimaryEmailRequiredException(PayloadLinkException): pass

class PayloadLinkInvalidHashException(PayloadLinkException): pass
class PayloadLinkExpiredException(PayloadLinkException): pass
class PayloadLinkAlreadyConsumedException(PayloadLinkException): pass
class PayloadLinkDisabledException(PayloadLinkException): pass

# AbstractPayloadLink
# This could be updated to use AutoHash.
# REQUIRED OVERRIDES:
#     - LINK_TYPES - Enumeration.  SPECIAL ENUMERATION: It is required to have 4 arguments passed into it's tuple (int, string, display_string, [(field, class),(field, class)] OR (field,class))
#     - SECRET_KEY - Unique String - used in hash
class AbstractPayloadLink(FastSave, models.Model):
    class Meta(object):
        abstract = True

    LINK_TYPES = Enumeration()
    SITE_PROTOCOL = settings.CAXIAM_SITE_PROTOCOL   # http:// or https:// depending on site configuration
    SITE_BASE_URL = ''              # base URL for payload links; in your derived class, typically settings.SITE_BASE_URL which should be set to settings.ALLOWED_HOSTS[0]
    PAYLOAD_BASE_DIR = 'payload/'   # base path for templates (NOT URLs)
    LINK_BASE_URL = 'link/'         # base URL path for all links
    SECRET_KEY = ''                 # MUST OVERRIDE to prevent link hashes from being guessable

    # what link is this?
    hash = models.CharField(max_length = 43, unique = True)

    # what kind of link is it?
    type = models.IntegerField(choices = LINK_TYPES.choices)

    # when was it created and when does it expire?
    date_created = models.DateTimeField()
    date_expires = models.DateTimeField(blank = True, null = True)  # non-expiring is dangerous
    date_consumed = models.DateTimeField(blank = True, null = True) # when this was used

    # has it already been used?
    # this covers both expiry and consumption
    is_valid = models.BooleanField(default = True)

    # is this a single-use item?
    is_single_use = models.BooleanField(default = True)

    # what other details do we have?
    details = JSONField(blank = True, null = True)

    # a debugging string-cast
    def __unicode__(self):
        # use %s for id instead of %d because id may be None
        """
        if self.email:
            target = unicode(self.email)
        elif self.credentials:
            target = unicode(self.credentials)
        elif self.user:
            target = unicode(self.user)
        else:
        """
        target = repr(self.details)
        return u'[%s:%s] %s %s %s %s' % (self.__class__.__name__, unicode(self.id), self.hash, self.LINK_TYPES.get_label(self.type), target, self.date_created.isoformat())

    # return the full URL of the payload link,
    # including the protocol
    @property
    def address(self):
        return self.SITE_PROTOCOL + self.SITE_BASE_URL + self.LINK_BASE_URL + self.hash + '/'


    # Example
    """
        ModelHashGenerator.generate_hash(cls, cls.SECRET_KEY, cls.LINK_TYPES.get_label(link_type), unicode(email), unicode(credentials), repr(details))
    """
    @classmethod
    def generate_hash(cls, link_type, **kwargs):
        raise Exception('Must Override Method: generate_hash.  common use: return ModelHashGenerator.generate_hash(cls, cls.SECRET_KEY, cls.LINK_TYPES.get_label(link_type), ... )')


    # Validate_link_type takes the chunk of validation out of the create method so that someone doesn't have to
    # rewrite create everytime. instead, they just need to write the small parts to make the big piece work
    # Example
    """
        if link_type == cls.LINK_TYPES.VALIDATE_EMAIL and not isinstance(email, Email):
            raise Exception('email not provided for validate email link')
        if link_type == cls.LINK_TYPES.RESET_PASSWORD and not isinstance(credentials, Credentials):
            raise Exception('credentials not provided for reset password link')
        if link_type == cls.LINK_TYPES.REMOTE_LOGIN and not isinstance(user, ILUser):
            raise Exception('user not provided for remote login link')
    """
    @classmethod
    def validate_link_type(cls, link_type, **kwargs):
        raise Exception('Must Override Method: validate_link_type.  See documentation for example')



    #Used to add additional data to the kwargs before it creates the payload.
    """
    # set up type-specific parameters
    if link_type == cls.LINK_TYPES.VALIDATE_EMAIL:
        create_payload_kwargs.update({
                'email': email,
                'date_expires': now + datetime.timedelta(1),    # good for 24 hours
                'is_single_use': True,
            })

    elif link_type == cls.LINK_TYPES.RESET_PASSWORD:
        create_payload_kwargs.update({
                'credentials': credentials,
                'date_expires': now + datetime.timedelta(1),    # good for 24 hours
                'is_single_use': True,
            })

    elif link_type == cls.LINK_TYPES.REMOTE_LOGIN:
        create_payload_kwargs.update({
                'user': user,
                'date_expires': now + datetime.timedelta(0,60), # good for 1 minute
                'is_single_use': True,
            })
    """
    @classmethod
    def decorate_create_payload_kwargs(cls, link_type, create_payload_kwargs, **kwargs):
        raise Exception('Must Override Method: decorate_create_payload_kwargs.  See documentation for example')

    # This is so you are able to decorate what goes onto the template per email type
    @classmethod
    def decorate_email_data(cls, link_type, data, **kwargs):
        pass


    # we usually need an address to send this to
    # The email address is really supposed to be determined by which object it is using
    """
    if link_type == cls.LINK_TYPES.VALIDATE_EMAIL:
        email_address = email.address

    elif link_type == cls.LINK_TYPES.RESET_PASSWORD:
        email = credentials.user.master_bank.primary_email      # resets go to primary email
        if email == None:
            raise PayloadLinkPrimaryEmailRequiredException()
        email_address = email.address
    else:
        email_address = None
    return email_address
    """
    @classmethod
    def get_email_address_by_type(cls, link_type, **kwargs):
        raise Exception('Must Override Method: get_email_address_by_type.  See documentation for example')


    # create a payload
    # Django provides a useful .objects.create method but in this
    # case, we want .hash filled in on the first save, and we want
    # to be able to regenerate the hash if it turns out to be in
    # use already (through random collision).
    @classmethod
    def create(cls, link_type, **kwargs):

        # validate parameters
        if cls.LINK_TYPES.get_label(link_type) == None:
            raise Exception('invalid link type')

        cls.validate_link_type(link_type, **kwargs)

        # go ahead and generate the hash now
        encoded_hash = cls.generate_hash(link_type, **kwargs)

        # set up core parameters
        now = timezone.now()
        create_payload_kwargs = {
                'hash': encoded_hash,
                'type': link_type,
                'date_created': now,
                'is_valid': True,
                'details': kwargs.get('details'),
            }

        # give the derived class a chance to manipulate the creation parameters
        cls.decorate_create_payload_kwargs(link_type, create_payload_kwargs, **kwargs)

        # fetch the email address (via derived-class implementation)
        email_address = cls.get_email_address_by_type(link_type, **kwargs)

        # create the PayloadLink object itself
        created_payload = cls.objects.create(**create_payload_kwargs)

        # and send out the email (using our wrapper)
        # NOTE: only if an actual email address is given; some
        # payload links are consumed in other ways, such as
        # showing them on the screen for the user to copy &
        # paste manually
        if email_address != None:
            email_data = {
                    'payload': created_payload,
                    'email_address': email_address,
                }
            cls.decorate_email_data(link_type = link_type, data = email_data, **kwargs)

            email_template_path = cls.get_email_template_path(
                created_payload = created_payload,
                link_type = link_type,
                **kwargs
                )

            send_mail(email_template_path, cls.__name__, [ email_address ], data = email_data)

        return created_payload


    #This was added so that if you create a specific type of a payload with an argument,
    #you can use a different payload template.
    @classmethod
    def get_email_template_path(cls, created_payload, link_type, *args, **kwargs):
        return cls.PAYLOAD_BASE_DIR + cls.LINK_TYPES.get_label(link_type)


    # determine whether a payload is valid
    # ...raises a PayloadLinkException subclass if not, returns
    # payload link if it is
    @classmethod
    def get_by_hash(cls, hash):
        # fetch payload link
        # WAS CHANGED FROM one_or_none(cls.objects.filter(hash = hash)) to first() because django 1.6
        payload = cls.objects.filter(hash = hash).first()
        if payload == None:
            raise PayloadLinkInvalidHashException()

        # determine if it can be used
        now = timezone.now()
        if payload.date_expires and now > payload.date_expires:
            raise PayloadLinkExpiredException()

        if payload.is_single_use and payload.date_consumed != None:
            raise PayloadLinkAlreadyConsumedException()

        if payload.is_valid == False:
            raise PayloadLinkDisabledException()

        # looks good
        return payload

    # This is the default processing action.
    # If you can get a more generic version of process then this is where you should place that code
    # NOTE: NOT SEPARATED BY DOUBLE UNDERSCORE
    def process_default(self, request, *args, **kwargs):
        raise Exception('Must Override Method OR You have a process type incorrectly handled')

    # act on a payload
    # NOTE: this does NOT validate the payload, it assumes
    # the payload is already valid
    # NOTE: processing is always done in the context of a request
    # and the return value is always a redirect
    def process(self, request, *args, **kwargs):

        # So let me explain why I abstracted it out the way I did:
        # I have no way to determine which way each of the types need to be processed,
        # but instead of just leaving this function to be overridden,
        # I made it so process__ + the type is how you do a process a type.
        # If that type doesn't have a function then it just doesn't do anything.

        lower_link_type = self.LINK_TYPES.get_label(self.type).lower()
        if hasattr(self, 'process__'+lower_link_type):
            return getattr(self, 'process__'+lower_link_type)(request, *args,**kwargs)
        return process_default(request, *args,**kwargs)


        # if self.type == self.LINK_TYPES.VALIDATE_EMAIL:
        #     # the email address is now validated
        #     # we do two things: upgrade this email to a known-valid
        #     # state, and find any other unvalidated entries with
        #     # the same address and mark them known-invalid

        #     from caxiam.email import AbstractEmail
        #     self.email.status = AbstractEmail.VERIFICATION_STATES.VALID
        #     self.email.save()

        #     others = AbstractEmail.objects.filter(address = self.email.address, status = Email.VERIFICATION_STATES.UNVERIFIED).update(status = Email.VERIFICATION_STATES.INVALID)

        #     # if this is the only known-valid email address for
        #     # its master bank, set it as the primary
        #     if self.email.master_bank.primary_email == None:
        #         self.email.master_bank.primary_email = self.email
        #         self.email.master_bank.save()

        #     # mark this as consumed
        #     self.consume()

        #     # redirect to success page
        #     return HttpResponseRedirect('/message/link/email-validated/')

        # elif self.type == self.LINK_TYPES.RESET_PASSWORD:

        #     # before the password is fully reset the user will
        #     # have to enter a password, so they are in a half-auth
        #     # state; we will flush any logged-in session they may
        #     # have up to this point
        #     request.session.flush()
        #     self.credentials.user.login(request, source = 'reset')
        #     request.session['reset_payload_hash'] = self.hash

        #     # NOTE: we do not mark the payload as consumed at
        #     # this time; that will be done when the password
        #     # is actually entered

        #     # redirect to success page
        #     return HttpResponseRedirect('/reset/')

        # elif self.type == self.LINK_TYPES.REMOTE_LOGIN:

        #     # we assume the link is completely sufficient to
        #     # authenticate the user (it exchanges an API session
        #     # for a web session)
        #     request.session.flush()
        #     self.user.login(request, source = 'web')

        #     # mark this as consumed
        #     self.consume()

        #     # redirect to success page
        #     return HttpResponseRedirect('/home/')




    # mark a payload as consumed
    def consume(self):
        self.date_consumed = timezone.now()
        self.is_valid = False
        self.save(update_fields = ['is_valid', 'date_consumed'])




