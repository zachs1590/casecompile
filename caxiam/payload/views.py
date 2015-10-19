from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _
from caxiam.payload.models import PayloadLinkInvalidHashException, PayloadLinkExpiredException, PayloadLinkAlreadyConsumedException, PayloadLinkDisabledException
import datetime
import json

@transaction.commit_on_success
def process_link(request, linkhash, payload_class, **kwargs):

    # fetch the payload and make sure it's valid
    payload = fetch_link_or_redirect(request, linkhash, payload_class,  **kwargs)

    if isinstance(payload, payload_class):
        # valid link; process it and return the results
        # (should be a redirect)
        return payload.process(request)

    else:
        # invalid link; we already have the correct
        # redirect
        return payload

# helper which returns either the payload object or a
# redirect
def fetch_link_or_redirect(request, linkhash, payload_class, **kwargs):
    try:
        payload = payload_class.get_by_hash(linkhash)
        return payload
    except PayloadLinkInvalidHashException:
        return HttpResponseRedirect(kwargs.get('redirect_invalid_hash','/error/link/not-valid/') )
    except PayloadLinkExpiredException:
        return HttpResponseRedirect(kwargs.get('redirect_expired','/error/link/expired/'))
    except PayloadLinkAlreadyConsumedException:
        return HttpResponseRedirect(kwargs.get('redirect_already_consumed','/error/link/consumed/'))
    except PayloadLinkDisabledException:
        return HttpResponseRedirect(kwargs.get('redirect_disabled','/error/link/disabled/'))
