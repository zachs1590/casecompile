from django.conf import settings
from ilarcade import ilcommon
import datetime
import json
import os
import pytz
import random
import redis
from redis.client import StrictPipeline
import time

# exception classes
class RedisShadowException(Exception): pass
class RedisShadowUnknownFieldException(RedisShadowException): pass
class RedisShadowLockException(RedisShadowException): pass

# a debugging wrapper for redis pipelines
class DebugStrictPipeline(StrictPipeline):

    def execute(self, *args, **kwargs):
        print "[pid:%d]" % os.getpid(), 'REDIS PIPELINE END'
        rv = super(DebugStrictPipeline, self).execute(*args, **kwargs)
        #print "[pid:%d]" % os.getpid(), 'REDIS RESULTS:', repr(rv)
        return rv

    def execute_command(self, *args, **kwargs):
        print "[pid:%d]" % os.getpid(), 'REDIS PIPELINE:', repr(args), repr(kwargs)
        rv = super(DebugStrictPipeline, self).execute_command(*args, **kwargs)
        #print "[pid:%d]" % os.getpid(), 'REDIS RESULTS:', repr(rv)
        return rv

# a debugging wrapper for redis clients
class DebugStrictRedis(redis.StrictRedis):

    def execute_command(self, *args, **kwargs):
        print "[pid:%d]" % os.getpid(), 'REDIS COMMAND:', repr(args), repr(kwargs)
        rv = super(DebugStrictRedis, self).execute_command(*args, **kwargs)
        #print "[pid:%d]" % os.getpid(), 'REDIS RESULTS:', repr(rv)
        return rv

    def pipeline(self, transaction = True, shard_hint = None):
        # return debug-wrapped version of pipeline
        print "[pid:%d]" % os.getpid(), 'REDIS PIPELINE START'
        rv = DebugStrictPipeline(self.connection_pool,
            self.response_callbacks,
            transaction,
            shard_hint)
        return rv

# a connection pool to draw connections
# from; note that we do NOT use thread-local
# storage because we are running a prefork
# server model and uwsgi will silently fail
# on threading-related calls
redis_pools = [ redis.ConnectionPool(host = h, port = p, db = db) for h,p,db in settings.ILCLOUD_REDIS_SHADOW ]

# fetch a connection from a pool (mostly for
# code not part of a Model)
def redis_connection(idx):
    if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
        return DebugStrictRedis(connection_pool = redis_pools[idx])
    else:
        return redis.StrictRedis(connection_pool = redis_pools[idx])

# unlocking requires us to inspect the contents
# of the lock to make sure it belongs to our pid,
# and then release the lock, all in a single
# atomic operation; a script is thus required.
# see http://redis.io/commands/set for details
rd = redis.StrictRedis(connection_pool = redis_pools[0])    # doesn't matter if it's debug
lua = '''
if redis.call("get",KEYS[1]) == ARGV[1]
then
    return redis.call("del",KEYS[1])
else
    return 0
end
'''
unlock_script = rd.register_script(lua)

# datetime objects used as indices will be
# converted to a float value of seconds since
# this date (with microsecond accuracy)
ZINDEX_DATETIME_EPOCH = datetime.datetime(2014, 1, 1, tzinfo = pytz.utc)

# helper class to allow a model to be
# more easily shadowed into a redis server,
# on a strictly voluntary basis
#
# NOTE: we now queue up saves to the redis
# server automatically whenever an object's
# save() method is called; when the request
# completes, the middleware will then store
# these records into redis. When using this,
# be advised that other fetches from redis
# will not contain the saved data, just like
# the REPEATABLE_READ SQL isolation level;
# you should probably optimize away such
# additional fetches
#
# NOTE: for the auto-save to work, you must
# set REDIS_SHADOW_AUTOSAVE to True and you
# must list RedisShadow before models.Model
#
class RedisShadow(object):

    # determine if a particular record is only in the
    # redis server or might still be saveable into the
    # SQL database
    @property
    def is_redis_record(self):
        if self.id and self.id < 0:
            return True
        else:
            return False

    # determine the correct shadow pool for this model
    # NOTE: returns the pool index
    @classmethod
    def redis_pool_index(cls):
        return getattr(cls, 'REDIS_SHADOW_POOL', 0)

    # determine the correct shadow pool for this model
    # NOTE: returns the pool itself, not the index
    @classmethod
    def redis_pool(cls):
        return redis_pools[cls.redis_pool_index()]

    # fetch a connection from the right pool
    @classmethod
    def redis_connection(cls):
        if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
            return DebugStrictRedis(connection_pool = cls.redis_pool())
        else:
            return redis.StrictRedis(connection_pool = cls.redis_pool())

    # create a key for the record in redis
    @classmethod
    def redis_key(cls, pk):
        return 'dbshadow:%s:%d' % (cls.__name__, pk)

    # create a key for the ID record of a particular model
    @classmethod
    def redis_id_key(cls):
        return 'dbshadow_id:%s' % (cls.__name__,)

    # create a lock key for the record in redis
    @classmethod
    def redis_lock_key(cls, pk):
        return 'dbshadow_lock:%s:%d' % (cls.__name__, pk)

    # create an index key for the record in redis
    @classmethod
    def redis_index_key(cls, slot):
        return 'dbshadow_index:%s:%d' % (cls.__name__, slot)

    # create a mindex key for the record in redis
    # NOTE: because each mindex is a set, the values
    # being looked up are part of the key, rather
    # than a single hash for the entire index
    @classmethod
    def redis_mindex_key(cls, slot, vals):
        k = 'dbshadow_mindex:%s:%d' % (cls.__name__, slot)
        if vals == None:
            # we want just the base key name
            return k
        return k + ''.join([ ':%s' % str(v) for v in vals ])

    # create a zindex key for the record in redis
    # like mindex, but sorted, so slower, but with
    # extra features
    @classmethod
    def redis_zindex_key(cls, slot, vals):
        k = 'dbshadow_zindex:%s:%d' % (cls.__name__, slot)
        if vals == None:
            # we want just the base key name
            return k
        return k + ''.join([ ':%s' % str(v) for v in vals ])

    # fetch record(s) from the redis server
    # pass in a single pk value to get just one;
    # pass in a list or set to get multiple
    @classmethod
    def redis_get(cls, pk):
        rd = cls.redis_connection()
        if isinstance(pk, (list, set)):
            if len(pk) == 0:
                # don't try mget() with an empty list
                return []
            dlist = rd.mget([ cls.redis_key(int(k)) for k in pk ])       # will take a list
            return [ cls.redis_in(d) for d in dlist if d != None ]
        else:
            d = rd.get(cls.redis_key(pk))
            return cls.redis_in(d)

    # fetch a record from the redis server by index
    #**** this could be improved by using a script that
    # looks up the value in the index and computes the
    # key server-side, only returning the actual value
    @classmethod
    def redis_get_by_index(cls, slot, vals):
        rd = cls.redis_connection()
        k = cls.redis_index_key(slot)
        idx = cls.REDIS_SHADOW_INDEX[slot]
        cls.redis_fix_index_types(idx, vals)        # ensure lookup types are correct
        f = repr(vals)
        pk = rd.hget(k, f)
        if pk == None:
            return None
        d = rd.get(cls.redis_key(int(pk)))
        return cls.redis_in(d)

    # fetch multiple records from the redis server by
    # mindex
    # fetches all the IDs from the mindex and then
    # pulls all the records with those IDs
    @classmethod
    def redis_get_by_mindex(cls, slot, vals):
        ids = cls.redis_get_ids_by_mindex(slot, vals)
        return cls.redis_get(ids)                   # fetch and parse those items

    # fetch multiple records from the redis server by
    # COMBINING multiple mindexes
    @classmethod
    def redis_get_by_mindexes(cls, *args):
        rd = cls.redis_connection()
        ks = []
        for i in range(0,len(args),2):
            slot = args[i]
            vals = args[i+1]
            idx = cls.REDIS_SHADOW_MINDEX[slot]
            cls.redis_fix_index_types(idx, vals)        # ensure lookup types are correct
            ks.append(cls.redis_mindex_key(slot, vals))
        ids = rd.sinter(*ks)                        # merge mindexes directly in redis (faster)
        return cls.redis_get(ids)                   # fetch and parse those items

    # fetch just the IDs of multiple records from the
    # redis server by mindex
    # NOTE: actually returns a Python set, NOT a list!
    @classmethod
    def redis_get_ids_by_mindex(cls, slot, vals):
        rd = cls.redis_connection()
        idx = cls.REDIS_SHADOW_MINDEX[slot]
        cls.redis_fix_index_types(idx, vals)        # ensure lookup types are correct
        k = cls.redis_mindex_key(slot, vals)
        return rd.smembers(k)

    # fetch multiple records from the redis server by
    # zindex
    # fetches all the IDs from the zindex and then
    # pulls all the records with those IDs
    @classmethod
    def redis_get_by_zindex(cls, slot, vals, score_range = None):
        ids = cls.redis_get_ids_by_zindex(slot, vals, score_range)
        return cls.redis_get(ids)                   # fetch and parse those items

    # fetch just the IDs of multiple records from the
    # redis server by zindex
    # NOTE: actually returns a Python set, NOT a list!
    @classmethod
    def redis_get_ids_by_zindex(cls, slot, vals, score_range = None):
        rd = cls.redis_connection()
        idx = cls.REDIS_SHADOW_ZINDEX[slot]
        cls.redis_fix_index_types(idx[1], vals)     # ensure lookup types are correct
        k = cls.redis_zindex_key(slot, vals)
        if score_range == None:
            return rd.zrange(k, 0, -1)              # all of them
        else:
            cls.redis_fix_index_types(None, score_range)    # fix any datetime objects
            return rd.zrangebyscore(k, score_range[0], score_range[1])  # within range

    # fetch related fields
    # these are pipelined and fetched in a single
    # atomic redis request
    # NOTE: this does an awful lot of mucking around
    # with Django internals
    def redis_get_related(self, *args):
        rd = self.redis_connection()

        # first, match up all the related field names
        # with their definitions
        field_list = self.redis_get_field_definitions(*args)

        # now fetch all the data
        pipe = rd.pipeline()
        for field_def in field_list:
            fk = getattr(self, field_def.attname)
            if fk != None:
                #print "[pid:%d]" % os.getpid(), "queueing fetch for", field_def.attname
                pipe.get(field_def.related.parent_model.redis_key(fk))
                
        rvs = pipe.execute()
        #print "[pid:%d]" % os.getpid(), "results:", repr(rvs)
        
        # store it in the right places
        # tricky bit: we didn't fetch related
        # objects whose IDs are set to None, so
        # we need to skip those
        i = 0
        for field_def in field_list:
            fk = getattr(self, field_def.attname)
            if fk != None:
                #print "[pid:%d]" % os.getpid(), "writing", field_def.name, field_def.attname
                o = field_def.related.parent_model.redis_in(rvs[i])
                setattr(self, field_def.name, o)
                setattr(self, field_def.attname, o.id)  # set the ID too, else Django will re-fetch object
                i += 1

    # fetch the related fields for an entire set of
    # records in a single atomic request
    # duplicate records are only fetched once
    # NOTE: this doesn't check that the records are
    # all of the proper class
    @classmethod
    def redis_get_related_multi(cls, records, *args):
        rd = cls.redis_connection()

        # first, match up all the related field names
        # with their definitions
        field_list = cls.redis_get_field_definitions(*args)

        # for each related field, collect up the unique
        # IDs for the entire set of records
        related_items = []
        for field_def in field_list:
            all_ids = [ getattr(r, field_def.attname) for r in records ]
            unique_ids = set([ fk for fk in all_ids if fk != None ])        # removes duplicates
            related_items.append(( field_def.related.parent_model, unique_ids ))
            
        # convert all of these items to their redis keys
        fetchable_items = []
        for ri in related_items:
            fetchable_items.extend([ ri[0].redis_key(fk) for fk in ri[1] ])

        # if there is absolutely nothing to fetch, we can
        # quit now
        if len(fetchable_items) == 0:
            return

        # and fetch them
        # NOTE: we don't need to pipeline because we're
        # using one massive mget
        rvs = rd.mget(*fetchable_items)
        
        # now for each field being processed, sort the
        # responses into a dict and then set up the
        # references in the records
        j = 0
        for i in range(len(field_list)):
            field_def = field_list[i]
            ri = related_items[i]
            
            # extract just the records for this model and
            # stuff them in a dict
            rv_map = {}
            for k in range(j,j+len(ri[1])):
                rv = ri[0].redis_in(rvs[k]) # should never be None
                rv_map[rv.id] = rv
                
            # now process all the records and look up the
            # appropriate related field
            for r in records:
                fk = getattr(r, field_def.attname)
                if fk != None:
                    o = rv_map[fk]
                    setattr(r, field_def.name, o)
                    setattr(r, field_def.attname, o.id) # set the ID too, else Django will re-fetch the object
                    
            # skip over the fetched records for this model
            j += len(ri[1])

    # match up a list of related field names with
    # their definitions
    @classmethod
    def redis_get_field_definitions(cls, *args):
        field_list = []
        for field in args:
            field_def = None
            for f in cls._meta.local_fields:
                if f.name == field:
                    field_def = f
                    break
            if not field_def:
                raise RedisShadowUnknownFieldException("unknown field: " + field)
            field_list.append(field_def)
            #print "[pid:%d]" % os.getpid(), "related:", field, '-->', repr(field_def)

        return field_list

    # write a record to the redis server
    # (also updates any indices)
    # NOTE: if you pass in a redis pipeline it will be used
    # and you are responsible for executing the pipeline
    # (the pipeline itself will be returned)
    def redis_set(self, pipe = None, update_indices = True):
        rd = self.redis_connection()
        if self.id == None:
            # this record hasn't been saved to the SQL database;
            # we need to obtain a primary key (id)
            # NOTE: we use negative values starting at -1 and
            # proceeding down, to indicate the record is only
            # in redis and not SQL
            self.id = rd.decr(self.redis_id_key())

        execute_pipe = False
        if pipe == None:
            pipe = rd.pipeline()
            execute_pipe = True
        pipe.set(self.redis_key(self.id), self.redis_out())
        
        # update any indices, but only if asked; rarely a
        # record will be updated in a way that requires the
        # indices to not be updated
        if update_indices:
            idxs = getattr(self, 'REDIS_SHADOW_INDEX', [])
            for slot in range(len(idxs)):
                self.redis_add_to_index(slot, pipe = pipe)

            idxs = getattr(self, 'REDIS_SHADOW_MINDEX', [])
            for slot in range(len(idxs)):
                self.redis_add_to_mindex(slot, pipe = pipe)

            idxs = getattr(self, 'REDIS_SHADOW_ZINDEX', [])
            for slot in range(len(idxs)):
                self.redis_add_to_zindex(slot, pipe = pipe)
                
        # execute and return the results
        if execute_pipe:
            return pipe.execute()
        else:
            return pipe

    # remove a record from the redis server
    # (also updates any indices)
    # NOTE: you have to have the record before you can
    # delete it because you can't generate the index
    # keys without the values of the data
    def redis_del(self, pipe = None):
        # if there is no id it was never saved
        if self.id == None:
            if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
                print "[pid:%d]" % os.getpid(), "NOT DELETING DUE TO MISSING PK:", unicode(self)
            return None

        execute_pipe = False
        if pipe == None:
            rd = self.redis_connection()
            pipe = rd.pipeline()
            execute_pipe = True
        
        # update any indices
        # each index is a sequence of field names
        idxs = getattr(self, 'REDIS_SHADOW_INDEX', [])
        for slot in range(len(idxs)):
            self.redis_remove_from_index(slot, pipe = pipe)
                
        idxs = getattr(self, 'REDIS_SHADOW_MINDEX', [])
        for slot in range(len(idxs)):
            self.redis_remove_from_mindex(slot, pipe = pipe)

        idxs = getattr(self, 'REDIS_SHADOW_ZINDEX', [])
        for slot in range(len(idxs)):
            self.redis_remove_from_zindex(slot, pipe = pipe)

        # remove the record itself
        pipe.delete(self.redis_key(self.id))
        
        # execute and return the results
        if execute_pipe:
            return pipe.execute()
        else:
            return pipe

    # for a particular index field, look up the value
    # __ separates related field lookups; use these with
    # care as they will force a SQL ORM lookup on each
    # related record for every redis write if the related
    # record is not already cached
    def redis_index_value(self, field):
        if isinstance(field, tuple):
            field = field[0]
        field_list = field.split('__')
        rv = self
        for f in field_list:
            rv = getattr(rv, f)
        return rv

    # for a particular set of values to be used in a
    # redis index, make sure the types are correct;
    # sometimes Django gives us a str instead of unicode,
    # or an int instead of a long, and this will make the
    # index keys not match
    # NOTE: also converts datetime objects to a long
    # value giving microseconds elapsed since the class's
    # epoch start (1/1/2014); mainly used to support
    # ZINDEX by date with extra precision
    # NOTE: modifies the list in-place and returns a
    # reference to it as well
    # NOTE: if the index field is a tuple, the first item
    # is the field name and the rest are transformations
    # to be applied:
    #   "lower"     force value to lowercase
    @classmethod
    def redis_fix_index_types(cls, idx, vals):
        for i in range(len(vals)):
            if isinstance(vals[i], basestring) or vals[i] == None:
                vals[i] = unicode(vals[i])
            elif isinstance(vals[i], datetime.datetime):
                vals[i] = long(((vals[i] - ZINDEX_DATETIME_EPOCH).total_seconds()) * 1000000)
            else:
                vals[i] = long(vals[i])

            # apply transforms, if any
            if idx != None and isinstance(idx[i], tuple):
                for t in idx[i][1:]:
                    if t == 'lower':
                        vals[i] = vals[i].lower()
                    #elif t == 'date':
                    #   would love to do this but you have to know the time zone

    # create a JSON dictionary suitable for
    # serialization into redis
    def redis_out(self):
        d = {}
        for f in self.__class__._meta.local_fields:
            d[f.attname] = getattr(self, f.attname)
        return json.dumps(ilcommon.to_json(d))
        
    # given a JSON dictionary, unpack it
    # into an object the Django will accept
    # NOTE: objects which override the
    # default constructor and do something
    # clever will probably not work well
    @classmethod
    def redis_in(cls, d):
        # don't deserialize if we got nothing
        if d == None:
            return None
        
        # else deserialize the dict
        d = json.loads(d)
        
        # some of the data may need massaging;
        # also, any fields that are missing will
        # be filled in with None, which will make
        # the constructor fail if that isn't
        # permitted
        for f in cls._meta.local_fields:
            #print "[pid:%d]" % os.getpid(), cls.__name__, f.attname, repr(d[f.attname]), '-->',
            if f.attname not in d:
                d[f.attname] = None
            d[f.attname] = f.to_python(d[f.attname])
            #print "[pid:%d]" % os.getpid(), repr(d[f.attname]),
            if isinstance(d[f.attname], datetime.datetime):
                d[f.attname] = pytz.utc.fromutc(d[f.attname])
            #    print 'with TZ:', d[f.attname].isoformat()
            #else:
            #    print
        
        # create the object
        return cls(**d)

    # obtain an exclusive lock in redis,
    # but with an expiration time
    # NOTE: uses the process ID to ensure the
    # lock is recorded as belonging to this
    # process, in case it times out before we
    # get around to unlocking it and another
    # process locks it again
    @classmethod
    def redis_lock(cls, pk, callback = None):
        if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
            print "[pid:%d]" % os.getpid(), "ACQUIRING LOCK: %s:%d" % (cls.__name__, pk)
            if callback != None:
                print "[pid:%d]" % os.getpid(), "  with callback %s" % callback.__name__

        # it's possible we're repeating the lock request
        # after we already have it; in SQL this is no big
        # deal but with redis it will report that the lock
        # has already been granted
        if (cls,pk) in RedisShadowMiddleware.lock_tracker:
            if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
                print "[pid:%d]" % os.getpid(), "  -- already locked"
            if callback != None:
                # we might be adding a callback to an existing lock
                if isinstance(RedisShadowMiddleware.lock_tracker[(cls,pk)], bool):
                    RedisShadowMiddleware.lock_tracker[(cls,pk)] = []
                if callback not in RedisShadowMiddleware.lock_tracker[(cls,pk)]:
                    RedisShadowMiddleware.lock_tracker[(cls,pk)].append(callback)
            return True

        rd = cls.redis_connection()
        k = cls.redis_lock_key(pk)
        
        # there is obviously a chance that the lock may
        # already be acquired; if so, wait a random
        # amount of time and try again
        # NOTE: we expect locks to be yielded very
        # quickly, so our poll frequency is about 100ms
        date_give_up = datetime.datetime.utcnow() + datetime.timedelta(settings.ILCLOUD_REDIS_SHADOW_LOCK_WAIT)
        while datetime.datetime.utcnow() < date_give_up:
            locked = rd.set(k, os.getpid(), settings.ILCLOUD_REDIS_SHADOW_LOCK_DURATION, nx = True)
            if locked:
                RedisShadowMiddleware.lock_tracker[(cls,pk)] = [ callback ] if callback != None else True
                return locked
            time.sleep(random.uniform(0.075, 0.125))
            
        # if we get here, it's because we timed out
        # trying to get a lock
        raise RedisShadowLockException("timed out trying to gain lock " + k)
        
    # release an exclusive lock in redis,
    # if it hasn't already timed out
    # returns 1 if the lock was ours to release,
    # 0 if the lock already belongs to another
    # process
    @classmethod
    def redis_unlock(cls, pk):
        if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
            print "[pid:%d]" % os.getpid(), "RELEASING LOCK: %s:%d" % (cls.__name__, pk)

        rd = cls.redis_connection()
        rv = unlock_script(
                keys = [ cls.redis_lock_key(pk) ],
                args = [ os.getpid() ],
                client = rd,
            )

        # process all callbacks on releasing this lock
        callbacks = RedisShadowMiddleware.lock_tracker[(cls,pk)]
        if not isinstance(callbacks, bool):
            for callback in callbacks:
                callback(pk)

        del RedisShadowMiddleware.lock_tracker[(cls,pk)]
        return rv

    # save a record
    # for the most part, this just passes through to Django,
    # but it does save a reference to the object so that
    # when the request completes, the middleware can write
    # it to redis
    # NOTE: you must enable this auto-saving by setting
    # REDIS_SHADOW_AUTOSAVE to True in the class
    def save(self, *args, **kwargs):
        # in case we get passed positional arguments, convert
        # them to keyword arguments
        for i in range(len(args)):
            kwargs[[ 'force_insert', 'force_update', 'using', 'update_fields' ][i]] = args[i]
                
        # call the original method with (potentially modified)
        # arguments
        rv = super(RedisShadow, self).save(**kwargs)
            
        # by now we should be guaranteed a pk, so we can
        # save this record properly in redis
        self.redis_save()
        
        return rv

    # mark a record as needing to be saved in redis when
    # the request is over; this is useful if you know it
    # has been saved by Django and Django has skipped the
    # save() method, BUT there is still the chance for the
    # transaction to be rolled back later
    def redis_save(self):
        if getattr(self, 'REDIS_SHADOW_AUTOSAVE', False):
            if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
                print "[pid:%d]" % os.getpid(), "AUTO-SAVE PROCESSING for", self.__class__.__name__, self.pk

            # if we have no save tracker, we're not in a
            # request context at all, so we don't have a
            # way to tell when we should commit to redis;
            # just commit now
            if RedisShadowMiddleware.save_tracker == None:
                self.redis_set()
                return

            # else we can log this in the save tracker and
            # finish it later
            record_key = (self.__class__,self.pk)
            if RedisShadowMiddleware.save_tracker[self.redis_pool_index()] == None:
                RedisShadowMiddleware.save_tracker[self.redis_pool_index()] = {}
            RedisShadowMiddleware.save_tracker[self.redis_pool_index()][record_key] = self

    # delete a record
    # for the most part, this just passes through to Django,
    # but it does save a reference to the object so that
    # when the request completes, the middleware can remove
    # it from redis
    # NOTE: you must enable this auto-saving by setting
    # REDIS_SHADOW_AUTOSAVE to True in the class
    def delete(self, *args, **kwargs):
        # Django is annoying: when you delete a record it
        # obliterates the ID of the deleted record, but we
        # need it
        pk = self.pk
        
        # call the original method with (potentially modified)
        # arguments
        rv = super(RedisShadow, self).delete(*args, **kwargs)
            
        # we have a record but its pk was obliterated;
        # restore it and queue the record for deletion
        self.pk = pk
        self.id = pk
        self.redis_delete()
        
        return rv

    # mark a record as needing to be deleted in redis when
    # the request is over; this is useful if you know it
    # has been deleted by Django and Django has skipped the
    # delete() method, BUT there is still the chance for the
    # transaction to be rolled back later
    def redis_delete(self):
        if getattr(self, 'REDIS_SHADOW_AUTOSAVE', False):
            if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
                print "[pid:%d]" % os.getpid(), "AUTO-DELETE PROCESSING for", self.__class__.__name__, self.pk

            # if we have no delete tracker, we're not in a
            # request context at all, so we don't have a
            # way to tell when we should commit to redis;
            # just commit now
            if RedisShadowMiddleware.delete_tracker == None:
                self.redis_del()
                return

            # else we can log this in the delete tracker and
            # finish it later
            record_key = (self.__class__,self.pk)
            if RedisShadowMiddleware.delete_tracker[self.redis_pool_index()] == None:
                RedisShadowMiddleware.delete_tracker[self.redis_pool_index()] = {}
            RedisShadowMiddleware.delete_tracker[self.redis_pool_index()][record_key] = self

    # flush a redis index (because you are about to
    # repopulate it)
    @classmethod
    def redis_flush_index(cls, slot):
        rd = cls.redis_connection()
        k = cls.redis_index_key(slot)
        rd.delete(k)

    # flush a redis mindex (because you are about to
    # repopulate it)
    # NOTE: THIS IS NOT FAST
    @classmethod
    def redis_flush_mindex(cls, slot):
        rd = cls.redis_connection()
        k = cls.redis_mindex_key(slot, None)    # just the base key
        ks = rd.keys(k + ':*')                  # slow operation
        if len(ks):
            rd.delete(ks)

    # flush a redis zindex (because you are about to
    # repopulate it)
    # NOTE: THIS IS NOT FAST
    @classmethod
    def redis_flush_zindex(cls, slot):
        rd = cls.redis_connection()
        k = cls.redis_zindex_key(slot, None)    # just the base key
        ks = rd.keys(k + ':*')                  # slow operation
        if len(ks):
            rd.delete(ks)

    # flush all indices (because you are about to
    # repopulate them)
    @classmethod
    def redis_flush_all_indices(cls):
        rd = cls.redis_connection()
        pipe = rd.pipeline()
        deleted_count = 0

        idxs = getattr(cls, 'REDIS_SHADOW_INDEX', [])
        for slot in range(len(idxs)):
            k = cls.redis_index_key(slot)
            pipe.delete(k)
            deleted_count += 1

        idxs = getattr(cls, 'REDIS_SHADOW_MINDEX', [])
        for slot in range(len(idxs)):
            k = cls.redis_mindex_key(slot, None)    # just the base key
            ks = rd.keys(k + ':*')                  # slow operation
            pipe.delete(*ks)
            deleted_count += len(ks)

        idxs = getattr(cls, 'REDIS_SHADOW_ZINDEX', [])
        for slot in range(len(idxs)):
            k = cls.redis_zindex_key(slot, None)    # just the base key
            ks = rd.keys(k + ':*')                  # slow operation
            pipe.delete(*ks)
            deleted_count += len(ks)

        if deleted_count > 0:
            # don't execute the pipeline if it is empty;
            # StrictPipeline will complain
            pipe.execute()

    # add a specific record to a specific index
    # NOTE: if no pipeline is provided, executes all
    # commands immediately
    def redis_add_to_index(self, slot, pipe = None):
        if pipe == None:
            pipe = self.redis_connection()

        idxs = getattr(self, 'REDIS_SHADOW_INDEX', [])
        idx = idxs[slot]
        # we allow None as an index so we can "remove"
        # certain indices after the fact without
        # having to renumber all the following ones
        if idx != None:
            k = self.redis_index_key(slot)
            vals = [ self.redis_index_value(field) for field in idx ]   # redis hash field is composite of index field values in record
            self.redis_fix_index_types(idx, vals)
            f = repr(vals)
            pipe.hset(k, f, self.id)

    # add a specific record to a specific mindex
    # NOTE: if no pipeline is provided, executes all
    # commands immediately
    def redis_add_to_mindex(self, slot, pipe = None):
        if pipe == None:
            pipe = self.redis_connection()

        idxs = getattr(self, 'REDIS_SHADOW_MINDEX', [])
        idx = idxs[slot]
        # we allow None as an index so we can "remove"
        # certain indices after the fact without
        # having to renumber all the following ones
        if idx != None:
            vals = [ self.redis_index_value(field) for field in idx ]   # redis key is composite of slot and index field values in record
            self.redis_fix_index_types(idx, vals)
            k = self.redis_mindex_key(slot, vals)
            pipe.sadd(k, self.id)
    
    # add a specific record to a specific zindex
    # NOTE: if no pipeline is provided, executes all
    # commands immediately
    def redis_add_to_zindex(self, slot, pipe = None):
        if pipe == None:
            pipe = self.redis_connection()

        idxs = getattr(self, 'REDIS_SHADOW_ZINDEX', [])
        idx = idxs[slot]
        # we allow None as an index so we can "remove"
        # certain indices after the fact without
        # having to renumber all the following ones
        if idx != None:
            vals = [ self.redis_index_value(field) for field in idx[1] ]   # redis key is composite of slot and index field values in record
            self.redis_fix_index_types(idx[1], vals)
            k = self.redis_zindex_key(slot, vals)
            s = [ self.redis_index_value(idx[0]) ]      # score
            self.redis_fix_index_types(None, s)
            pipe.zadd(k, s[0], self.id)
    
    # remove a specific record from a specific index
    # NOTE: if no pipeline is provided, executes all
    # commands immediately
    def redis_remove_from_index(self, slot, pipe = None):    
        if pipe == None:
            pipe = self.redis_connection()

        idxs = getattr(self, 'REDIS_SHADOW_INDEX', [])
        idx = idxs[slot]
        # we allow None as an index so we can "remove"
        # certain indices after the fact without
        # having to renumber all the following ones
        if idx != None:
            k = self.redis_index_key(slot)
            vals = [ self.redis_index_value(field) for field in idx ]   # redis hash field is composite of index field values in record
            self.redis_fix_index_types(idx, vals)
            f = repr(vals)
            pipe.hdel(k, f)

    def redis_remove_from_mindex(self, slot, pipe = None):    
        if pipe == None:
            pipe = self.redis_connection()

        idxs = getattr(self, 'REDIS_SHADOW_MINDEX', [])
        idx = idxs[slot]
        # we allow None as an index so we can "remove"
        # certain indices after the fact without
        # having to renumber all the following ones
        if idx != None:
            vals = [ self.redis_index_value(field) for field in idx ]   # redis hash field is composite of index field values in record
            self.redis_fix_index_types(idx, vals)
            k = self.redis_mindex_key(slot, vals)
            pipe.srem(k, self.id)

    def redis_remove_from_zindex(self, slot, pipe = None):    
        if pipe == None:
            pipe = self.redis_connection()

        idxs = getattr(self, 'REDIS_SHADOW_ZINDEX', [])
        idx = idxs[slot]
        # we allow None as an index so we can "remove"
        # certain indices after the fact without
        # having to renumber all the following ones
        if idx != None:
            vals = [ self.redis_index_value(field) for field in idx[1] ]   # redis hash field is composite of index field values in record
            self.redis_fix_index_types(idx[1], vals)
            k = self.redis_zindex_key(slot, vals)
            pipe.zrem(k, self.id)

class RedisShadowMiddleware(object):

    # request-wide save/delete tracking; when a request
    # completes (successfully), all records are stored
    # in redis
    # keys are (class, id) and the values are the records
    save_tracker = None
    delete_tracker = None

    # request-wide lock tracking; when a request
    # completes (successfully or not), any remaining
    # redis locks will be released
    # NOTE: this is a list of dicts, one per connection;
    # keys are (class, id) and the values are
    # irrelevant
    lock_tracker = None

    # request-wide state message queue; whenever a message
    # is "sent" to a state message queue it is not directly
    # submitted to Redis but instead held here, so that
    # it can be discarded at request end if any exception
    # was raised
    message_queue = None

    def process_request(self, request):
        # make sure these are cleared
        self.__class__.save_tracker = [ None ] * len(settings.ILCLOUD_REDIS_SHADOW) # one per connection
        self.__class__.delete_tracker = [ None ] * len(settings.ILCLOUD_REDIS_SHADOW) # one per connection
        self.__class__.lock_tracker = {}
        self.__class__.message_queue = []
        
    def process_response(self, request, response):
        # if there are any records to save, save them
        # NOTE: we do this before releasing locks
        self.save_all_records()
        self.delete_all_records()

        # if there are any messages to send, send them
        self.send_all_messages()

        # if there are any locks remaining, whether we
        # "succeeded" or not, we need to free them because
        # they're not part of the SQL transaction
        self.release_all_locks()
        return response
        
    def process_exception(self, request, exception):
        # if there are any locks remaining, whether we
        # "succeeded" or not, we need to free them because
        # they're not part of the SQL transaction
        if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
            print "[pid:%d]" % os.getpid(), "REDIS EXCEPTION HANDLING"
        self.release_all_locks()

    def save_all_records(self):
        save_tracker = self.__class__.save_tracker
        if save_tracker == None:
            return
        
        # go ahead and set all the records
        # NOTE: we use a single pipeline for all of these
        for ci in range(len(save_tracker)):
            c = save_tracker[ci]
            if c != None and len(c) > 0:
                if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
                    print "[pid:%d]" % os.getpid(), "SAVING ALL PENDING RECORDS IN CONNECTION", ci
                
                rd = redis_connection(ci)
                pipe = rd.pipeline()
                for k,v in c.iteritems():
                    v.redis_set(pipe)
                pipe.execute()

        # flush the recorded saves, we're done
        # (should not be necessary)
        self.__class__.save_tracker = None

    def delete_all_records(self):
        delete_tracker = self.__class__.delete_tracker
        if delete_tracker == None:
            return
        
        # go ahead and delete all the records
        # NOTE: we use a single pipeline for all of these
        for ci in range(len(delete_tracker)):
            c = delete_tracker[ci]
            if c != None and len(c) > 0:
                if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
                    print "[pid:%d]" % os.getpid(), "DELETING ALL PENDING RECORDS IN CONNECTION", ci
                
                rd = redis_connection(ci)
                pipe = rd.pipeline()
                for k,v in c.iteritems():
                    v.redis_del(pipe)
                pipe.execute()

        # flush the recorded deletes, we're done
        # (should not be necessary)
        self.__class__.delete_tracker = None

    def send_all_messages(self):
        message_queue = self.__class__.message_queue
        if message_queue == None:
            return
            
        if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
            print "[pid:%d]" % os.getpid(), "SENDING ALL STATE MESSAGES"

        if len(message_queue):
            from ilarcade.ilgames.models import GameProgress
            from ilarcade.notifications.models import NotificationMessage
            rd = NotificationMessage.redis_connection()
            
            # Before we submit these messages to the queues,
            # we want to determine which queues already exist.
            # To do this reliably we must lock all of the
            # candidate queues, verify their existence, add
            # the messages if the queue exists, and then
            # release the locks.

            # lock queues
            unique_progress_ids = sorted(set([ m[0].id for m in message_queue ]))
            for progress_id in unique_progress_ids:
                GameProgress.redis_lock(progress_id)

            # determine which queues are valid
            valid_progress_ids = {}
            for progress_id in unique_progress_ids:
                queue_sessions_id = 'notification_session_queue_offset:' + str(progress_id)
                valid_progress_ids[progress_id] = (rd.zcard(queue_sessions_id) > 0)

            # deliver the messages, if the queues exist
            # NOTE: we wait until the very last moment to
            # JSON-serialize so that, if we determine a
            # message doesn't need to be delivered (because
            # no clients are listening for them), we can
            # avoid doing the serialization work
            pipe = rd.pipeline()
            execute_pipeline = False
            for m in message_queue:
                if valid_progress_ids[m[0].id]:
                    queue_id = 'notification_queue:' + str(m[0].id)
                    pipe.rpush(queue_id, json.dumps(m[1]))
                    execute_pipeline = True
            if execute_pipeline:
               pipe.execute()

            # unlock everything
            for progress_id in unique_progress_ids:
                GameProgress.redis_unlock(progress_id)

    def release_all_locks(self):
        lock_tracker = self.__class__.lock_tracker
        if lock_tracker == None:
            return
        if len(lock_tracker) == 0:
            return
            
        if settings.ILCLOUD_REDIS_SHADOW_DUMP_REQUESTS:
            print "[pid:%d]" % os.getpid(), "RELEASING ALL LOCKS"
        
        # use keys() instead of iterkeys() because the
        # latter requires the dict to remain unchanged
        # throughout, and each call to redis_unlock will
        # update the dict
        for k in lock_tracker.keys():
            k[0].redis_unlock(k[1])

        # flush the recorded locks, we're done
        self.__class__.lock_tracker = None

    # in cases where a JSON-RPC APIError or APIParamsError
    # is raised, these are caught and returned as properly-
    # formed JSON responses, which means the exception
    # middleware handler for the request is NOT called; we
    # want to make sure we have a mechanism by which this
    # CAN be caught and all pending records cleared when/
    # before the SQL transaction is rolled back
    @classmethod
    def cancel_pending_operations(cls):
        cls.save_tracker = {}
        cls.delete_tracker = {}
        cls.message_queue = []
        