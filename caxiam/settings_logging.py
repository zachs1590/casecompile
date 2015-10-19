# by default, Django behaves differently when running in DEBUG
# mode versus production mode, at least as far as how errors are
# reported. This is the primary setting the DEBUG flag alters.
# (There are others.)
#
# In production mode (DEBUG = False), Django defaults to ONLY
# emailing errors to the ADMINS setting. This works, but often
# it's useful to be able to log in to the server and see a
# backtrace. For this, we configure INFO and above messages to
# be logged to the console. We also flag error emails to use
# the HTML format so they are easier to read and more complete.

# log all data to the console, and email critical stuff
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'django.utils.log.NullHandler',
        },
        'console':{
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'propagate': True,
            'level': 'INFO',
        },
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
    }
}
