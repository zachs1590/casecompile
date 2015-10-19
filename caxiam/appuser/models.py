from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from caxiam.common import Enumeration
from caxiam.email import AbstractEmail
from caxiam.forms import ISO_COUNTRIES
from caxiam.model_mixins import AutoHashModel, LoginMixin, OverridableChoicesMixin


# AbstractAuthHash
#
# REQUIRED OVERRIDES:
#     - AUTOHASH_SECRET - A Unique string
# OPTIONAL OVERRIDES:
#     - AUTOHASH_FIELDS - The Field values that get hashed together
class AbstractAuthHash(AutoHashModel, models.Model):
    class Meta(object):
        abstract = True

    # Keys used to generate the hash field with unique values.
    AUTOHASH_FIELDS = []
    # Required.  should be unique to project.
    AUTOHASH_SECRET = None
    hash = models.CharField(max_length = 43, unique = True, blank = True, null = True) 


""" SIMPLE APP USER SETUP"""

# Abstract AppUser
#
# REQUIRED OVERRIDES:
#     - AUTOHASH_SECRET - A Unique string
# OPTIONAL OVERRIDES:
#     - AUTOHASH_FIELDS - The Field values that get hashed together
#     - CHECK_PASSWORD_METHOD - the name of the function that your authenticate calls on the user instance
#     - REQUIRED_FIELDS - Set from Abstract Base User, used by /auth/management/commands/createsuperuser.py:Command
# Description:
#     This is to abstract out the most common features of an App User.
#     This class represents the most basic logins, where the only way to come in would be a username and password
class AbstractSimpleAppUser(LoginMixin, AbstractAuthHash, AbstractBaseUser):
    class Meta(AbstractBaseUser.Meta):
        abstract = True

    # Used in the Authenticate function that allows you to say where your check password validation is coming from
    CHECK_PASSWORD_METHOD = 'check_password'

    """ AbstractBaseUser Requirements """
    # Used in get_username inside the AbstractBaseUser parent class. ex: getattr(self, self.USERNAME_FIELD)
    USERNAME_FIELD = 'username'
    # Requiring that these fields exist when being saved.  Only used by /auth/management/commands/createsuperuser.py:Command
    REQUIRED_FIELDS = [ 'username' ]

    """ AutoHashModel Requirements """
    # Keys used to generate the hash field with unique values.
    AUTOHASH_FIELDS = [ 'username' ]

    """ Fields """
    username = models.CharField(max_length = 20)

    # validate a username and password, returning
    # the matched user or None
    # Note, it always filters on the value from USERNAME_FIELD
    @classmethod
    def authenticate(cls, username, password):
        user = cls.objects.filter(**{cls.USERNAME_FIELD: username}).first()
        if user != None and hasattr(user, cls.CHECK_PASSWORD_METHOD) and getattr(user,cls.CHECK_PASSWORD_METHOD)(password):
            return user


""" COMPLEX APP USER SETUP"""

# REQUIRED OVERRIDES:
#     - AUTOHASH_SECRET - A Unique string
# OPTIONAL OVERRIDES:
#     - AUTOHASH_FIELDS - The Field values that get hashed together
# Description:
#     This class is honestly nothing.  Here's Why:  most of the work goes to the Credential class
#     The credentials handle username and password, unlike the simple app user.
#     Because of this change, most actual implementations of AppUser need to be defined uniquely
class AbstractAppUser(LoginMixin, AbstractAuthHash, models.Model):
    class Meta(object):
        abstract = True

    @classmethod
    def authenticate(cls, type, *args, **kwargs):
        """MUST OVERRIDE"""
        raise Exception("this function must be overridden")


# AbstractAppUserCredential
# SUGGESTED CODE IN SUBCLASS:
#     - appuser = models.ForeignKey(<class Child(AbstractAppUser)>, related_name = 'credentials')
# REQUIRED OVERRIDES:
#     - CREDENTIAL_TYPES - Enumeration or Tuple
#     - authenticate() - function - each instance of a credential should be able to authenticate itself to see if it's valid.
#
# DESCRIPTION:
#     We seperated the users' login credentials from the app user themselves.  This means we need to store
#     each individual type of credential and what data is used to log them in.
class AbstractAppUserCredential(OverridableChoicesMixin, models.Model):
    class Meta(object):
        abstract = True

    CREDENTIAL_TYPES = Enumeration() # Expects to be enumeration

    data1 = models.CharField(max_length=255)
    data2 = models.CharField(max_length=255)
    credential_type = models.IntegerField(choices = CREDENTIAL_TYPES.choices)

    # We are running the init function to override the credential type choices
    def __init__(self, *args, **kwargs):
        super(AbstractAppUserCredential, self).__init__(*args, **kwargs)
        self._set_field_choices(field_name = 'credential_type', choices = self.CREDENTIAL_TYPES.choices)

    # This function is used to identify if your current user is permitted to do an action.
    # Most commonly used in login to ensure that a user is allowed to come into the site
    # RETURN Boolean
    def authenticate(self, user):
        """MUST OVERRIDE"""
        raise Exception("this function must be overridden")


# Contact Information
#
# This is a very common pattern, so we set these up once and re-use
# them in multiple apps. Addresses should always be prepared to handle
# international locations.
#
# Generally when you create a concrete implementation of this class
# you will add foreign keys to the things that may have contact info
# associated with them (e.g. something derived from AbstractAppUser).
# However, if you are absolutely certain that a record only needs one
# contact info object, you can construct the relationship from the
# other direction.
#
class AbstractContactInfo(OverridableChoicesMixin, models.Model):
    class Meta(object):
        abstract = True
    
    # does this address have a name or label?
    # (if not, we use the address type)
    title = models.CharField(max_length = 30, blank = True, null = True)

    # by default we will take the country list as the ISO country list
    COUNTRIES = ISO_COUNTRIES
    
    # all fields optional
    address1 = models.CharField(max_length = 100, blank = True, null = True)
    address2 = models.CharField(max_length = 100, blank = True, null = True)
    address3 = models.CharField(max_length = 100, blank = True, null = True)    # primarily international
    city     = models.CharField(max_length = 100, blank = True, null = True)
    state    = models.CharField(max_length =  50, blank = True, null = True)    # or province
    zip      = models.CharField(max_length =  50, blank = True, null = True)    # or postal code
    country  = models.CharField(max_length =   2, blank = True, null = True, choices = COUNTRIES.choices, default = 'US')    # ISO 3166-1-alpha-2; see http://en.wikipedia.org/wiki/ISO_3166-1_alpha-2

    # what type of address is it?
    # NOTE: actual concrete implementations may want to override
    # this list with a subset/superset
    ADDRESS_TYPES = Enumeration(
            (0, 'BILLING', 'Billing'),
            (1, 'SHIPPING', 'Shipping'),
        )
    address_type = models.IntegerField(choices = ADDRESS_TYPES.choices, default = 0)

    # what is the display order/preference?
    # we use this to determine a "best" address for a person
    display_order = models.IntegerField(default = 0)

    # handle overridable enumerations
    def __init__(self, *args, **kwargs):
        super(AbstractContactInfo, self).__init__(*args, **kwargs)
        self._set_field_choices(field_name = 'country', choices = self.COUNTRIES)
        self._set_field_choices(field_name = 'address_type', choices = self.ADDRESS_TYPES)
    
# Phone Number
#
# You will need to add foreign keys when you create a concrete
# implementation. Depending on your data model, you may want to
# create foreign keys to something derived from AbstractContactInfo
# (if phone numbers are associated most closely with an address)
# or something from AbstractAppUser (if phone numbers are associated
# most closely with a person).
#
class AbstractPhoneNumber(OverridableChoicesMixin, models.Model):
    class Meta(object):
        abstract = True

    # does this number have a name or label?
    # (if not, we use the number type)
    title = models.CharField(max_length = 30, blank = True, null = True)
    
    # what is the actual number?
    number = models.CharField(max_length = 30)
    
    # what type of number is it?
    # NOTE: actual concrete implementations may want to override
    # this list with a subset
    NUMBER_TYPES = Enumeration(
            (0, 'UNKNOWN', 'Unknown'),
            (1, 'HOME', 'Home'),
            (2, 'WORK', 'Work'),
            (3, 'CELL', 'Cell/Mobile'),
            (4, 'FAX', 'Fax'),
        )
    number_type = models.IntegerField(choices = NUMBER_TYPES.choices, default = NUMBER_TYPES.UNKNOWN)
    
    # are there additional notes about when this number can
    # be called or special instructions?
    notes = models.CharField(max_length = 100)

    # what is the display order/preference?
    # we use this to determine a "best" number for a person
    display_order = models.IntegerField(default = 0)

    # handle overridable enumerations
    def __init__(self, *args, **kwargs):
        super(AbstractPhoneNumber, self).__init__(*args, **kwargs)
        self._set_field_choices(field_name = 'number_type', choices = self.NUMBER_TYPES)
    
# AbstractMultipleEmail
#
# Although the base AbstractEmail class is designed so that it
# can be used as a one-to-many (multiple email addresses per
# other thing, such as user) there's still an assumption that
# there is probably "one" email address, and we support multiple
# in order to ease the transition. In cases where we have true
# multiple-email-address support we need to have labels and
# preferences for those email addresses, similar to how we have
# them for addresses and phone numbers.
#
class AbstractMultipleEmail(AbstractEmail):
    class Meta(object):
        abstract = True

    # does this number have a name or label?
    title = models.CharField(max_length = 30, blank = True, null = True)
    
    # what is the display order/preference?
    # we use this to determine a "best" address for a person
    display_order = models.IntegerField(default = 0)

# Web Sites
#
# Sometimes we want to associate web site address(es) with
# users or entities. This is a base class for doing so.
#
class AbstractWebSite(models.Model):
    class Meta(object):
        abstract = True

    # does this number have a name or label?
    title = models.CharField(max_length = 30, blank = True, null = True)

    # what is the actual web site?
    # NOTE: we don't make this a Django URLField because
    # we don't want their validation rules.
    url = models.CharField(max_length = 250)
    
    # what is the display order/preference?
    # we use this to determine a "best" address for a person
    display_order = models.IntegerField(default = 0)

