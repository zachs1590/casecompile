from django.contrib.auth.hashers import check_password, make_password, is_password_usable
from django.db import models
from caxiam.common import Enumeration
from caxiam.hash_generator import ModelHashGenerator
import datetime

# Useful things to include in Model definitions

# AUTO-GENERATED HASH ID MODEL
#
# Often we want to expose a record ID to end users
# but doing so using Django's built-in id field has
# some disadvantages:
#
#   1. It exposes how many of a thing were present
#      in the system prior to that object's creation
#      (a business intelligence leak)
#
#   2. It is enumerable: it is trivial to write a
#      script that checks every possible ID, looking
#      for things that were inadequately protected
#      or are otherwise interesting (a privacy leak)
#
# The solution is to generate a unique hash, spreading
# the sequential id values "randomly" over a 256-bit
# hash space. This can then be returned to the user,
# as even with four billion entries in the system
# (2^32) there is only a 1 in 6.277e57 chance of any
# randomly-chosen hash matching a record in the system.
# (Roughly.)
#
# Some problems arise:
#
#   1. The hash must be unique, but the ID value is
#      typically not available when the hash needs to
#      be generated because it's a new record. This
#      means the hash MUST be generated from other
#      data, typically from the object, as well as the
#      datetime.
#
#   2. Generated hashes must be checked against the
#      database for uniqueness prior to being written;
#      this means there is a race condition where two
#      concurrent inserts of identical data may clash
#      and cause one to fail, even with the additional
#      checks.
#
#   3. Since hash generation data comes from outside
#      the field itself, this is a MODEL mix-in and not
#      just a simple field.
#
# You will need to define some additional values in the
# model in order for this to work:
#
#   AUTOHASH_SECRET - a string with unique data so that
#       hashes from different models aren't the same
#       (required)
#
#   AUTOHASH_FIELDS - a list of field names which will
#       be converted to strings, concatenated, and hashed
#       as one (required)
#
#   AUTOHASH_NO_DATETIME - if set to True, the current
#       datetime will not automatically be included in
#       the hash generation (default: False)
#
#   AUTOHASH_ALLOW_EMPTY - if set to False, empty or null
#       hash values will be populated before saving;
#       otherwise, they will only be generated when
#       generate_hash is specifically called (default: False)
#
class AutoHashModel(object):
    
    # a convenient wrapper around the base ModelHashGenerator,
    # which automatically fetches all the input fields and
    # hands them off to be incorporated into the hash
    def generate_hash(self):
    
        # collect all the arguments together
        args = [ getattr(self, field) for field in self.AUTOHASH_FIELDS ]

        # include current timestamp unless we're directed not to
        if not getattr(self, 'AUTOHASH_NO_DATETIME', False):
            args.append(datetime.datetime.utcnow())

        # generate the hash and record it            
        self.hash = ModelHashGenerator.generate_hash(self.__class__, self.AUTOHASH_SECRET, *args)
        
    # override the model save method
    def save(self, *args, **kwargs):
    
        # if we're not allowing empty hashes, and this object
        # has an empty hash, fill it in right now
        if not getattr(self, 'AUTOHASH_ALLOW_EMPTY', False) and (self.hash == None or self.hash == ''):
            self.generate_hash()
            
        # pass through to the regular save method
        return super(AutoHashModel, self).save(**kwargs)


# LoginMixin
#
# Logging in doesn't have anything to do with authentication
# (determining who the user is) or authorization (determing
# whether a user is allowed to log in). Those steps should
# already be complete before logging in occurs. Logging in
# is all about recording an "active" user for a particular
# browser session, and logging out is all about breaking that
# association and scrubbing the session of any personalized
# data.
#
# Add this to a model to give it helper functions to work
# with request and session objects to manage the login
# process.
#
# OPTIONAL OVERRIDES:
#   LOGIN_ID_KEY - string - Key used to store the ID of the app user into session
#   LOGIN_REQUEST_KEY - string - Key used to store the App User instance onto the request
#
class LoginMixin(object):
    
    LOGIN_ID_KEY = 'app_user_id'
    LOGIN_REQUEST_KEY = 'app_user'

    # Sets the appropriate values in the session to stay logged in.
    def login(self, request):
        # DJango Bug Fix #
        # This is to force session_cache to load if it's not already on the session object. #
        request.session._get_session()
        # Enforce that you start at a clean slate
        request.session.cycle_key()
        request.session[self.LOGIN_ID_KEY] = self.pk
        # Cache the logged-in user object in the request (for the remainder of this request)
        setattr(request, self.LOGIN_REQUEST_KEY, self)


    # In our login we are setting a key onto the request object itself,
    # and we need to clear that out, then call the super which should get rid of the session
    @classmethod
    def logout(cls, request):
        setattr(request, cls.LOGIN_REQUEST_KEY, None)
        request.session.flush()


    # determine whether a session is logged in without
    # making an additional database request
    @classmethod
    def is_logged_in(cls, request):
        value = False
        if cls.LOGIN_ID_KEY in request.session and cls.get_login_user_id(request) != None:
            value = True
        return value


    # fetch the currently-active user for a request
    #
    # This is checked first in the request object itself (in case
    # the user has already been fetched) and then, if an ID is
    # present in session but no user has been fetched, fetch it
    # from a database.
    #
    # NOTE: we use the default REQUEST and ID keys (attribute
    # names) to make life simple, but if you have an application
    # with multiple user classes (e.g. app user, back office user)
    # you will want to have different keys for these so that they
    # do not have any chance of overlapping. This allows you to
    # do easy checks (if Appuser.get_login_user(request) == None)
    # instead of constantly having to check the type of a returned
    # user, and allows you to add new non-overlapping classes of
    # users without revisiting existing code.
    #
    @classmethod
    def get_login_user(cls, request):
        # if we've already written the app_user to the request,
        # go ahead and return it without requiring an additional
        # database fetch
        if hasattr(request, cls.LOGIN_REQUEST_KEY):
            return getattr(request, cls.LOGIN_REQUEST_KEY)

        # Default the app_user to None if you are not logged in. The
        # following test could fail (because the session got flushed
        # but the request object's user was not removed) so we are
        # paranoid. Our own logout code DOES remove the object but
        # we'd rather be sure.
        setattr(request, cls.LOGIN_REQUEST_KEY, None)
        if cls.is_logged_in(request = request):
            # get the user if it exists, otherwise it's None;
            # cache the result in the request object
            setattr(request, cls.LOGIN_REQUEST_KEY, cls._get_login_user_queryset(request).first())
            return getattr(request, cls.LOGIN_REQUEST_KEY)

    # This function is not intended for common use cases so i kept it "private"
    # This function was added for 2 purposes.
    # 1) If you ALWAYS need to fetch related EVERY SINGLE TIME,
    # you can override THIS function instead of having to rewrite all the validation for get_login_user
    # In a subclass, you might always need a one to one field so you select related after the filter and return it
    # 2) If you know the login user is valid (if you are using some form of login validation on request)
    # then you can use this function to make one off querysets to get extra data.  
    # For example: In Shop2Care, There is a request that requires the sum of all transactions for the current logged in user
    # I only want this value on this one page that is in the my account, (which is being checked for login on every request)
    # So i can use this function to get the queryset and expand upon it.
    @classmethod
    def _get_login_user_queryset(cls, request):
        return cls.objects.filter(pk = cls.get_login_user_id(request))

    # Want to pull out just the login_user_id to use elsewhere?  HERE YOU GO!
    # NOTE: if the user is not logged in, this returns None rather
    # than raising a KeyError
    @classmethod
    def get_login_user_id(cls, request):
        return request.session.get(cls.LOGIN_ID_KEY)

# PasswordMixin
#
# Includes functions that are useful in managing passwords
# that are stored locally as one-way hashes. This is
# intended for use in models derived from AbstractSimpleAppUser
# or AbstractAppUserCredential.
#
# Liberally cribbed from django.contrib.auth.models.AbstractBaseUser
#
# OPTIONAL OVERRIDES:
#   PASSWORD_FIELD - field name that contains the password hash;
#       defaults to "password" but should be overridden to "data2"
#       for AbstractAppUserCredential-derived classes.
#
# NOTE: From time to time Django updates the hashing functions used
# for passwords to make them stronger whenever weaknesses are found.
# However, since passwords are hashed it's not possible to upgrade
# the strength of all the password hashes at once, because the
# plaintext version of the password is not available. Django thus
# uses an opportunistic approach: whenever a password is tested,
# and a confirmed match is found, it will be updated in the database
# if it needs to be upgraded to a stronger algorithm. For this
# reason the check_password method MAY update the record behind the
# scenes. The set_password method, however, NEVER does this; you
# must explicitly save() the record after setting the password.
#
class PasswordMixin(object):

    PASSWORD_FIELD = 'password'

    def set_password(self, raw_password):
        setattr(self, self.PASSWORD_FIELD, make_password(raw_password))

    def check_password(self, raw_password):
        """
        Returns a boolean of whether the raw_password was correct. Handles
        hashing formats behind the scenes.
        """
        def setter(raw_password):
            self.set_password(raw_password)
            self.save(update_fields=[self.PASSWORD_FIELD])
        return check_password(raw_password, getattr(self, self.PASSWORD_FIELD), setter)

    def set_unusable_password(self):
        # Sets a value that will never be a valid hash
        setattr(self, self.PASSWORD_FIELD, make_password(None))

    def has_usable_password(self):
        return is_password_usable(getattr(self, self.PASSWORD_FIELD))

# OverridableChoices
#
# Often in abstract base classes we need to provide an Enumeration
# of choices for a particular field, but we expect or require the
# concrete implementation to override this with an app-specific
# list. Django gets a bit confused by this because of how it builds
# fields incrementally from base classes on up, so we need to
# override the constructor for all such classes and have them reset
# the choice list for the affected fields:
#
#    def __init__(self, *args, **kwargs):
#        super(SomeAbstractClass, self).__init__(*args, **kwargs)
#        self._set_field_choices(field_name = 'my_customized_field', choices = self.ENUMERATION_NAME)
#
# We call _set_field_choices for each affected field. The function
# itself is included in this mix-in.
#
class OverridableChoicesMixin(object):

    # This is a magical function.  In Django's internals, 
    # you can pull out a field and set various amount of data on it.
    # One use case would be to overrride the set choices from this 
    # abstract class with the values in the concrete class.
    # 
    # self will be your instance, a subclass of this class
    # self._meta is a piece of django's underbelly that 
    #     keeps the fields for a model
    # self.meta.get_field_by_name is a function that pulls out a tuple
    #     that looks like (<field>, None, Yes, No), which is why we ask 
    #     for [0] to get the field
    # self._meta.get_field_by_name(field_name)[0]._choices is the field 
    #     we want to override.  It has the values that the field is going
    #     to validate against when asked to clean.
    #
    # NOTE: we accept the actual choices OR an Enumeration.
    #
    def _set_field_choices(self, field_name, choices):
        if isinstance(choices, Enumeration):
            choices = choices.choices
        self._meta.get_field_by_name(field_name)[0]._choices = choices

