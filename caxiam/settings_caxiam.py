import os.path

# Django doesn't explicitly provide this and assumes it can
# be derived on-demand from the request data, but this isn't
# always true with load-balanced setups and it needs to be
# a configuration setting. PRODUCTION WILL PROBABLY USE
# https:// BUT THIS WILL DEPEND ON THE SITE. We keep this as
# a separate field so we don't have to update all the
# hostname variables as well.
CAXIAM_SITE_PROTOCOL = 'http://'

# if this is set to True, then attempts to send email that
# fail will be quietly ignored; this should NEVER be set to
# True as a default, but it may be useful to do this during
# development until email credentials are properly set
CAXIAM_EMAIL_FAIL_SILENTLY = False

# set this to a list of email addresses to capture all
# outbound email and direct it to the list instead (for
# debugging)
CAXIAM_EMAIL_OVERRIDE_TOLIST = None

# by default email will appear to originate from a single
# (typically non-replyable) address; YOU MUST SET THIS
# as it's totally app-specific
#CAXIAM_EMAIL_FROM = 'noreply@my_site.com'

# we need to know where email templates (in an 'email'
# folder) are stored, since we don't want to put 'email'
# in the base templates directory (which should be reserved
# for project/module names)
# NOTE: YOU MUST DEFINE THIS as it's completely app-specific
#CAXIAM_EMAIL_TEMPLATE_BASE = 'my_app'

# Email messages often need to refer to the site; this will
# require the hostname and the protocol. The default for
# this should be ALLOWED_HOSTS[0] but that's not available
# when this module is imported, so you MUST set it in your
# main settings.py instead.
#CAXIAM_EMAIL_SITE_HOSTNAME = ALLOWED_HOSTS[0]

# When processing forms we want to keep all the actual
# error messages in a centralized file to make them easier
# to find, but we also need to be able to override and
# extend the error messages with app-specific ones.
# This list should be redefined in settings.py to include
# the app's error messages file in addition to the core
# Caxiam one.
CAXIAM_AJAX_FORM_ERROR_MESSAGES = (
        'caxiam.ajax.form_errors',
    )

# FastSave optimizes record saving to avoid extra queries,
# but assumes we never create records in the database with
# pre-defined IDs; if you are using FastSave and loading
# fixtures, you will need to disable this temporarily
#
# This should always default to True so that including
# FastSave in the inheritance path will result in the
# expected performance gains.
#
CAXIAM_FASTSAVE = True
CAXIAM_FASTSAVE_DUMP_INFO = False   # spew debugging information

# global defaults about login requirements
LOGIN_REQUIRED_DEFAULT = False
LOGIN_REDIRECT_LOCATION_DEFAULT = "/"
LOGIN_SESSION_KEY_DEFAULT = 'appuser_id'

# pagination defaults
PAGINATION_URL_PAGE_KEY_DEFAULT = 'page'
PAGINATION_PAGINATE_BY_DEFAULT = 24
PAGINATION_SHOW_PAGE_NUMBER_AMOUNT_DEFAULT = 0

# s3files.StoredFile defaults
CAXIAM_S3FILES_REMOTE_MODE = 'local'        # one of 'local', 's3'
CAXIAM_S3FILES_BUCKET = None                # S3 bucket name
CAXIAM_S3FILES_AUTO_EXPIRE_UPLOADS = 1.0    # default time, in days, before uploads auto-expire; use None to disable
CAXIAM_S3FILES_CHECK_IMAGES = True          # whether to extract image metadata at upload time
CAXIAM_S3FILES_DIR = None                   # if not None, contains a path fragment where uploads will go
CAXIAM_S3FILES_REMOTE_URL = '/media/'       # URL base path for remote media

# revert to always using the temporary file upload handler
# as we always need to have the file on disk
#FILE_UPLOAD_HANDLERS = ( "django.core.files.uploadhandler.TemporaryFileUploadHandler", )

#
# debug-related settings
# NOTE: the defaults should ALWAYS BE OFF
#

# set this to True to report each request and its time;
# also enabled implicitly if DUMP_SQL or DUMP_SESSION
# are enabled
CAXIAM_DUMP_REQUESTS = False

# set this to True to report all SQL queries with times
# after each request
CAXIAM_DUMP_SQL = False

# set this to True to dump all session data at the end of
# each request
CAXIAM_DUMP_SESSION = False

# set this to True to echo all AJAX requests/responses to
# the console
CAXIAM_AJAX_DUMP_INFO = False

# if you want to use the standard error handlers, you will
# need to define the base directories for the message
# classes; 403, 404, and 500 especially rely on the "error"
# class
#CAXIAM_MESSAGE_TEMPLATES = {
#        'error': 'appname/error',
#        'message': 'appname/message',
#    }
