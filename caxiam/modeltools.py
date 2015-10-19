from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.manager import Manager, QuerySet
from caxiam.common import Enumeration

# ModelTools
#
# Django's ORM is pretty good but it has some deficiencies.
# We collect here some functions which are often useful but
# which we do not want to add to the model classes as mix-ins.
#
class ModelTools(object):

    # fetch_related
    #
    # Django's object relational mapping (ORM) system has some
    # very nice automatic related-model fetching. For example, if
    # you create a QuerySet of items with a ForeignKey to another
    # model, when you reference the related model by its property
    # name on an object in the query set, it is fetched from the
    # database and stored in a cache on the QuerySet. Further,
    # you can instruct Django to pre-populate this cache using
    # the select_related() method on the QuerySet; this will not
    # even incur an extra query, as it will be done as a JOIN in
    # SQL so that data comes back all at the same time as the
    # main query.
    #
    # However, working in the other direction is not nearly as
    # efficient. If model A has a ForeignKey to model B, there
    # are plenty of use cases for querying model B, and in a
    # nested loop processing all of the A records linked to each
    # instance of model B. Django DOES provide an automatic
    # QuerySet generator on the model B object, so you can issue
    # a B.related_field.all() to get the records, but it has some
    # limitations:
    #
    #   1. It issues a separate query for each B record. While
    #      the difference in raw Python execution time is not
    #      huge, the additional load on the database server is
    #      and the latency of the extra queries is noticeable.
    #   2. The results are not cached AT ALL; the result is a
    #      new QuerySet that isn't connected to its parent in
    #      any way.
    #
    # To address this weak spot we use this method. Given a
    # QuerySet, a related field name, and optional Q object
    # and sort order, the related records are fetched in one
    # query, then collected together into lists for each record
    # in the original QuerySet.
    #
    # If you do not specify a results field to store the lists
    # in, it defaults to related_field + '_list'.
    #
    # NOTE: returns the SAME (modified) QuerySet.
    # NOTE: only basic customization of the QuerySet is possible;
    # at some point we may need to allow a callable to be passed
    # in that will modify the QuerySet, to allow defer() or
    # extra() or other fun things.
    #
    # NOTE: Django as of v1.4 does offer prefetch_related which
    # provides similar functionality, including nested lookups,
    # but does so at the expense of being able to specify a
    # Q object to filter the results. This function now has a
    # select_related method.
    #
    @classmethod
    def fetch_related(cls, qs, related_field, q = None, order_by = None, results_field = None, id_list = None, select_related = None):
        if results_field == None:
            results_field = related_field + '_list'

        # determine which IDs to include in our related record
        # query; exclude None values, which Django uses for
        # records which are unsaved (and thus can't have any
        # related records in the database)
        if id_list == None:
            id_list = [ r.id for r in qs if r.id != None ]

        # Since we might exit early, we go ahead and create the
        # empty lists for each record in the QuerySet now.
        for r in qs:
            setattr(r, results_field, [])

        if len(id_list) == 0:
            # there are no records with IDs to fetch; DO NOT
            # actually issue such a pointless query
            # (more importantly, we can't tell what model to query)
            return qs

        # determine the model name of the related field

        # This is a bit dicey, because we have to look inside the
        # original ForeignKey object on the base class object;
        # in order to do that, we have to get that class object.
        # We can do this in one of two ways:
        #
        #   1. Peek inside the QuerySet and pull it from there.
        #   2. Look at the first object in the QuerySet and
        #      get its class directly.
        #
        # We use #2, for these reasons:
        #
        #   a. We want to muck around with Django internals as
        #      little as possible. They're internal for a reason,
        #      and we run the risk of broken code when we update
        #      Django.
        #   b. We'd like to be able to work with a list, not
        #      just a QuerySet. QuerySets behave like lists in
        #      many contexts and it's very convenient to have
        #      all helper functions work with either.
        #
        # One quirk is that unsaved objects in a list will have
        # an ID of None (this is how Django decides if it is new
        # or not). We can still get the class name, but we don't
        # include these in the list of IDs we query for.

        # take the first object and get the relationship, then
        # extract the model class object and the reverse field
        # name (which we need to find the parent object)
        relationship = getattr(qs[0].__class__, related_field).related
        related_model = relationship.model
        related_model_field_name = relationship.field.name
        related_model_field_id = relationship.field.attname

        # fetch all the related records

        # we can't use Django's in_bulk() here because we want
        # to return records in correct sorted order, and the
        # in_bulk() returns a dict; we just use a normal
        # QuerySet
        # and the odd **{} is idiomatic Python for constructing
        # function parameter names on the fly
        rqs = related_model.objects.filter(**{ related_model_field_name +'_id__in': id_list })

        if q != None:
            rqs = rqs.filter(q)
        if order_by != None:
            rqs = rqs.order_by(*order_by)
        if select_related != None:
            rqs = rqs.select_related(*select_related)

        # place each related record with its proper parent

        # to do this efficiently, we need a map of parent ID
        # to object; this dense bit of idiomatic Python does it
        qs_map = dict([ (r.id,r) for r in qs ])

        # now sift each related record (rr)
        for rr in rqs:
            r = qs_map[getattr(rr, related_model_field_id)] # get parent record
            getattr(r, results_field).append(rr)            # append results to list

        return qs

    # update_or_create
    #
    # Django offers a useful get_or_create method which will
    # either fetch a record or, if it doesn't exist, create it
    # with a given set of defaults. This is good, but there is
    # also a very common pattern of fetch-update-save which can
    # benefit from this create-if-missing behavior.
    #
    # Pass 'defaults' as fields to use when creating missing
    # records. Pass 'updates' as fields to replace when updating
    # (these will automatically be applied on top of defaults).
    # Everything else is assumed to be a field lookup, and if
    # it does not contain __ it will be added to the defaults.
    #
    # Returns (record, created, updated)
    #
    # NOTE: Django 1.7 offers an update_or_create method but it
    # doesn't separate defaults from updates, so there's no way
    # to set default values for new records without forcing an
    # existing record to be reset. This is dumb and short-
    # sighted.
    #
    @classmethod
    def update_or_create(cls, model_or_manager, *args, **kwargs):
        # these parameters can't be listed in the formal list
        # or Python will attempt to fill them with positional
        # parameters, which we DO NOT WANT.
        defaults = kwargs.pop('defaults', {})
        updates = kwargs.pop('updates', {})

        # merge updates onto defaults
        defaults.update(updates)

        # normally we expect a model object as our first parameter,
        # but we might get a manager (e.g. related field manager)
        # to simplify working with related objects
        if isinstance(model_or_manager, Manager):
            manager = model_or_manager
        else:
            manager = model_or_manager.objects  # use default manager

        # fetch or create the record
        record, created = manager.get_or_create(*args, defaults = defaults, **kwargs)

        # if we didn't create it, we need to finish the update
        # NOTE: we don't save the record unless we modify at
        # least one field
        dirty = False
        if not created:
            for k,v in updates.iteritems():
                if getattr(record, k) != v:
                    dirty = True
                    setattr(record, k, v)
            if dirty:
                record.save()

        return (record, created, dirty)

    # set_and_track_dirty
    # 
    # Along with update_or_create, it's also often useful
    # to be able to set fields on a record from a dictionary
    # but keep track of whether any of the fields resulted
    # in a change; later, we can save the record if it's
    # "dirty"
    #
    # We make a few assumptions when we do this. First, we
    # assume that the fields we're setting aren't hidden
    # behind properties, because we're going to compare them
    # directly. Second, we assume that you will reset the
    # dirty field list if you manually save the object.
    #
    # This part of the process, where we just set fields on
    # the record, does NOT touch the database unless you are
    # using deferred fields, in which case we force a fetch
    # of any field we're trying to set.
    #
    # NOTE: we return the record in case you want to save it
    # right away.
    #
    @classmethod
    def set_and_track_dirty(cls, record, attrs):
        # ensure we have a list of dirty fields; note that
        # we don't erase an existing list because it might
        # be dirty fields from a previous invocation
        if not hasattr(record, '_caxiam_dirty_list'):
            record._caxiam_dirty_list = []
        for k,v in attrs.iteritems():
            if not hasattr(record, k):
                raise AttributeError('record type %s does not have attribute %s' % (record.__class__.__name__, k))
            if getattr(record, k) != v:
                setattr(record, k, v)
                record._caxiam_dirty_list.append(k)
        return record

    # save the record, but only the dirty fields
    # NOTE: returns the list of fields updated
    @classmethod
    def save_if_dirty(cls, record):
        if record.id == None:
            # although is_dirty() returns True if the ID is
            # None, we need to special-case our processing
            # to make sure we don't pass an update_fields list
            # for new records
            record.save()
            
            # create an empty dirty list and report we saved
            # everything
            record._caxiam_dirty_list = []
            return [ f.name for f in record._meta.fields ]  # messy Django-internals stuff
            
        if cls.is_dirty(record):
            # we have a dirty list and it's not empty
            record.save(update_fields = record._caxiam_dirty_list)
            
            # preserve the dirty list as we're going to wipe
            # it out
            dirty_list = record._caxiam_dirty_list
            record._caxiam_dirty_list = []
            return dirty_list

        # nothing is dirty, don't save
        return []

    # determine whether a record was marked dirty
    # any record without an ID is automatically dirty (it
    # has never been saved) but if it has an ID, it has to
    # be explicitly marked dirty by set_and_track_dirty
    @classmethod
    def is_dirty(cls, record):
        return record.id == None or (hasattr(record, '_caxiam_dirty_list') and record._caxiam_dirty_list)

    # given a model class and a dictionary of parameters,
    # pass all the ones that are valid field names into the
    # model constructor to create an unsaved record, then
    # set all the unused parameters as additional attributes
    # on the record
    #
    # this is useful when you have a collection of data and
    # you want to create objects with valid parameters, but
    # still have the extra data available on the current
    # request that won't be saved
    #
    # Unfortunately Django's meta-class magic means things
    # assigned to the class don't exist as fields on the
    # class unless they're foreign keys; they're collected
    # up and added to _meta.fields instead. Fetching them
    # from there is a bit dirty.
    #
    @classmethod
    def create_with_extra(cls, model_class, attrs):

        # look up the fieldnames from _meta
        model_fields = frozenset([ unicode(f.name) for f in model_class._meta.fields ])

        # split the attrs into two dicts
        model_kwargs = {}
        extra_attrs = {}
        for k,v in attrs.iteritems():
            k = unicode(k)
            if k in model_fields:
                model_kwargs[k] = v
            else:
                extra_attrs[k] = v
                
        # create the model object
        m = model_class(**model_kwargs)

        # apply the extra attributes
        for k,v in extra_attrs.iteritems():
            setattr(m, k, v)

        # return the result
        return m

# OneToOneReverse
#
# Django offers a OneToOneField which is convenient (it's a
# ForeignKey with a unique constraint) but the two sides of
# the relationship don't behave the same. If you access the
# side where OneToOne is defined, and no related record
# exists, a None value is given. If you access the other
# side and no record exists, an ObjectDoesNotExist exception
# is thrown. Oops.
#
# This method allows you to define a property that works on
# the reverse side as it does on the forward side. On the
# forward side, point the related_name to a private field;
# then on the reverse side, define the public name with this
# method pointed at the private field.
#
# Under the hood, this returns a customized function.
#
# NOTE: this now CACHES the reverse lookup. You can clear
# the cache by deleting the attribute, which has _cache
# appended to the fieldname.
#
# EXAMPLE USAGE:
# class A():
#   models.OneToOneField(B, related_name="_a")
#
# class B():
#   a = property(OneToOneReverse('_a'))
#
def OneToOneReverse(fieldname):
    def inner(self):
        cachename = fieldname + '_cache'
        if not hasattr(self, cachename):
            # no cached lookup
            try:
                f = getattr(self, fieldname)
            except ObjectDoesNotExist:
                f = None
            setattr(self, cachename, f)
        return getattr(self, cachename)
    return inner

# FastSave
#
# Django is quite flexible in that it will generate the
# primary key value automatically, or allow the application
# to set it explicitly prior to saving. However, this means
# the ORM MUST do a SELECT prior to saving, in order to
# determine whether an INSERT or UPDATE is required. This
# is inefficient in situations where the application NEVER
# sets the primary key value directly. Therefore, we write
# this mix-in class which overrides the save() method,
# looks at the primary key value, and calls the original
# save() method with either force_insert or force_update.
#
# NOTE: you must include this before models.Model so that
# its save() will be called before the regular save()
#
# NOTE: you do not need this for any class which never sees
# updates, as those records will always have an empty id
# and Django automatically knows it must insert them.
#
# NOTE: you must not use this with any class for which you
# will load a fixture, because the fixture will (obviously)
# contain preset primary key values. If you desperately
# must load a fixture for such a class, you can temporarily
# disable fast saves by changing settings.CAXIAM_FAST_SAVE
# to False.
#
# NOTE: if you even PASS IN values for force_insert,
# force_update, or update_fields, even if they result in
# a no-op, the optimization will disable itself and you
# will get the default behavior.
#
class FastSave(object):

    def save(self, *args, **kwargs):
        # in case we get passed positional arguments, convert
        # them to keyword arguments
        for i in range(len(args)):
            kwargs[[ 'force_insert', 'force_update', 'using', 'update_fields' ][i]] = args[i]
            
        # if none of the override flags are set, go ahead and
        # try to guess at the right force_ setting
        if settings.CAXIAM_FASTSAVE:
            if settings.CAXIAM_FASTSAVE_DUMP_INFO:
                print "[pid:%d]" % os.getpid(), "FAST SAVE PROCESSING for", self.__class__.__name__,
            if 'force_insert' not in kwargs and 'force_update' not in kwargs and 'update_fields' not in kwargs:
                if self.pk == None:
                    kwargs['force_insert'] = True
                    if settings.CAXIAM_FASTSAVE_DUMP_INFO:
                        print 'forcing insert'
                else:
                    kwargs['force_update'] = True
                    if settings.CAXIAM_FASTSAVE_DUMP_INFO:
                        print 'forcing update'
            else:
                if settings.CAXIAM_FASTSAVE_DUMP_INFO:
                    print 'skipped due to parameters', repr(kwargs)
                
        # call the original method with (potentially modified)
        # arguments
        return super(FastSave, self).save(**kwargs)

# set database transaction isolation modes
#
# NOTE: this is the low-level function, not the view
# decorator. See caxiam.decorators.set_isolation_mode
# for that.
#
# Django offers no support for setting the database
# transaction isolation mode, defaulting to whatever the
# database is configured for. The default for MySQL is
# repeatable read, which effectively freezes the visible
# data to its state at the start of the transaction; this
# is reasonable for most situations. However when dealing
# with concurrent updates of data where thresholds are
# important, race conditions apply. Use this function to
# set the isolation mode for the next transaction.
#
# Consider this example. Two players, A and B, are playing
# a turn-based game with simultaneous moves. Each submits
# their move at roughly the same time.
#
#       A                       B
# 1     begin txn
# 2                             begin txn
# 3     attempt game lock
# 4     receive game lock
# 5                             attempt game lock
# 6     write move
# 7     count moves
# 8     1 move: turn not over
# 9     end txn / release lock
# 10                            receive game lock
# 11                            write move
# 12                            count moves
# 13                            1 move: turn not over
# 14                            end txn / release lock
#
# The answer at step 13 is 1, not 2, because B's transaction
# started at 2, freezing B's view of the database to that
# point, due to repeatable read. B can't see the write at
# step 8 until both A's transaction completes (committing it
# to the database for other processes to read) and B's
# transaction completes (allowing it to start a new
# transaction with an updated snapshot).
#
# In this circumstance, the process needs to use the
# READ_COMMITTED to force each read to fetch a more current
# snapshot, or break the process into multiple transactions.
#
ISOLATION_MODES = Enumeration(
        (0, 'REPEATABLE_READ'),
        (1, 'READ_COMMITTED'),
        (2, 'READ_UNCOMMITTED'),
        (3, 'SERIALIZABLE'),
    )

def set_isolation_mode(isolation_mode):
    # So Django is messed up. Python says new queries should
    # open a transaction and LEAVE IT OPEN for the app to
    # commit or roll back. Django interprets this as "commit
    # on write or at request end" because manually committing
    # every transaction is not friendly to devs. Adding true
    # autocommit support would be better because the way it is
    # now, any innocent read will leave an open transaction.
    #
    # This has major problems for setting isolation modes,
    # which can only be done OUTSIDE of a transaction unless
    # you're going to set it for the whole session. We don't
    # want to set it for the whole session as we want it to
    # revert after the next transaction to its app-configured
    # default. And, if our app is using sessions, Django has
    # automatically performed a read, leaving an open
    # transaction.
    #
    # To work around this, we go ahead and COMMIT any open
    # transaction. This is grossly inelegant and if our
    # assumptions about why there is an open transaction are
    # wrong, this code will fail. Worse, when Django gets
    # around to fixing their quirky transaction behavior
    # (which looks like it will be in 1.6) this fix may then
    # break because there is no open transaction.
    
    # NOTE: we do not use Django's parameter quoting because
    # we are inserting SQL keywords, not values, into the
    # statement and we don't want Django/MySQLdb quoting them
    from django.db import connection
    cursor = connection.cursor()
    if settings.CAXIAM_DUMP_SQL:
        print "[pid:%d]" % os.getpid(), 'SETTING ISOLATION MODE', ISOLATION_MODES.get_label(isolation_mode)
    cursor.execute(
            'commit; set transaction isolation level ' + ISOLATION_MODES.get_label(isolation_mode).replace('_', ' '),
            []
        )
    cursor.fetchone()

