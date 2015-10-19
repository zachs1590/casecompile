from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from caxiam.common import Enumeration
from caxiam.model_mixins import AutoHashModel

# placeholder package to support legacy implementations
# DO NOT DELETE THESE
from caxiam.appuser.models import AbstractAuthHash, AbstractSimpleAppUser, AbstractAppUser, AbstractAppUserCredential




# AbstractSoftDelete
#
# If you inherit from this instead of (or in addition to)
# models.Model, regular .delete() actions will be intercepted
# and will instead update a date_deleted field.
#
# THIS WILL NOT PREVENT RECORDS FROM BEING DELETED. They
# can still be deleted via QuerySet.delete(), by foreign key
# cascade delete, or by a database trigger (horrors). To
# fully prevent records in a specific table from being deleted,
# delete permission must be revoked from the database user
# that the web app uses.
#
# The primary purpose of this is to simplify soft-delete
# management.
#
class AbstractSoftDelete(models.Model):
    class Meta(object):
        abstract = True

    date_deleted = models.DateTimeField(blank = True, null = True, db_index = True)

    def delete(self):
        raise Exception('This model requires a soft delete.')

    def soft_delete(self):
        self.date_deleted = timezone.now()
        self.save(update_fields = ['date_deleted'])

    @property
    def is_deleted(self):
        return self.date_deleted != None


