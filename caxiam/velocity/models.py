from django.contrib import admin
from django.db import models
from django.utils import timezone
from caxiam.common import Enumeration
from caxiam.hash_generator import ModelHashGenerator
from caxiam.model_mixins import AutoHashModel
from caxiam.redis_shadow import RedisShadow, redis_connection
import datetime
from jsonfield import JSONField
import os
import pytz

# velocity-related and auditing models

# some exception classes related to VelocityTypes
class VelocityException(Exception): pass

class VelocityInvalidTypeException(VelocityException): pass
class VelocityMissingParameterException(VelocityException): pass

# a velocity type: a kind of event that can occur
# and be logged
# NOTE: this is NOT a database model
class VelocityType(RedisShadow, models.Model):

    SYNC_TYPES = Enumeration(
            (0, 'UNSYNCED'),
            (1, 'LOCAL_DAY_SYNCED'),    # events happen at local midnight
        )

    # what type is this?
    tag = models.CharField(max_length = 32, unique = True)

    # and which foreign key(s) does it require?
    # NOTE: these are not mutually-exclusive because most of
    # the time user is required, even when game or gamehistory
    # are also required.
    requires_user = models.BooleanField(default = False)
    requires_game = models.BooleanField(default = False)
    requires_gamehistory = models.BooleanField(default = False)
    requires_unique_id = models.BooleanField(default = False)
    
    # can this be triggered via API call?
    external = models.BooleanField(default = False)

    # should event times be synced (e.g. to a day)?
    sync_date = models.IntegerField(default = 0, choices = SYNC_TYPES.choices)

    # how long (in seconds) should records of this
    # type be kept? helpful numbers:
    #    3600 = 1 hour
    #   86400 = 1 day
    #  604800 = 1 week
    # 2419200 = 4 weeks
    # 2592000 = 30 days
    expunge_after = models.IntegerField(blank = True, null = True)
    
    # what constraints and triggers are applied to
    # this type? this is a list of dicts with the
    # following keys:
    #   timespan    how many seconds the rule covers
    #   limit       the weight that triggers the action
    #   trigger     one of:
    #                   "equal"     do action when sum == limit
    #                   "above"     do action when sum > limit
    #   action      name of action method to call
    #   params      kwargs to pass to that action method
    rules = JSONField()

    # indices for redis
    REDIS_SHADOW_INDEX = [
            ( 'tag', ),
        ]
    
    # a debugging string-cast
    def __unicode__(self):
        # use %s for id instead of %d because id may be None
        return u'[%s:%s] %s: %ds' % (self.__class__.__name__, unicode(self.id), self.tag, self.expunge_after)

    # property to determine the longest timespan (this is
    # the timespan of the entire type)
    @property
    def timespan(self):
        return max([ r['timespan'] for r in self.rules ])

    # test an event
    # this is just a nice wrapper around create_event()
    @classmethod
    def test_event(cls, type_tag, weight = 1, **kwargs):
        return cls.create_event(type_tag, weight, test = True, **kwargs)

    # create an event
    # automatically locks related records if required so that
    # equal triggers can be reliably used
    # NOT TRUE FOR REDIS: NOTE: you MUST use this in isolation level READ_COMMITTED
    @classmethod
    def create_event(cls, type_tag, weight = 1, user = None, game = None, gamehistory = None, unique_id = None, date_created = None, date_ending = None, test = False, test_and_save = False, timezone_offset = 0):

        # validate parameters
        #vt = cls.objects.get(tag = type_tag)   # raises exception if missing
        if isinstance(type_tag, cls):
            # already have the object, don't re-fetch it
            vt = type_tag
        else:
            vt = cls.redis_get_by_index(0, [ type_tag ])
            if vt == None:
                raise VelocityInvalidTypeException('invalid velocity type tag ' + type_tag)
        vt.validate_params(user, game, gamehistory, unique_id)

        # fix the time being used
        if date_created == None:
            date_created = timezone.now()
        if date_ending == None:
            date_ending = date_created

        # if the time is synced, deal with that
        if vt.sync_date == cls.SYNC_TYPES.LOCAL_DAY_SYNCED:
            local_midnight = datetime.datetime(date_created.year, date_created.month, date_created.day, tzinfo = pytz.utc) + datetime.timedelta(seconds = timezone_offset*60)
            date_created = local_midnight

        # lock the required record
        vt.lock_related(user, game, gamehistory, unique_id)

        # create the new event and, if this is not just
        # a test, save it
        ve = VelocityEvent(
                velocity_type = vt,
                user = user,
                game = game,
                gamehistory = gamehistory,
                unique_id = unique_id,
                weight = weight,
                date_created = date_created,
            )
        if not (test or test_and_save):
            # save the record in Redis
            # NOTE: we use redis_set rather than redis_save
            # to force the event to be record right now; this
            # does mean that if the request fails, the event
            # has still been recorded
            print "[pid:%d]" % os.getpid(), "SAVING NEW VELOCITY EVENT %s" % str(ve)
            ve.redis_set()

        # fetch related events (including the new one)
        events = vt.get_events(user = user, game = game, gamehistory = gamehistory, unique_id = unique_id, date_ending = date_created)
        
        # look for triggers and act on them
        if test or test_and_save:
            # when testing, get_events won't include the
            # one we're doing (because it's not saved)
            events.append(ve)

        failure_data = vt.apply_rules(ve, events, do_actions = not (test or test_and_save))
        
        # test_and_save means if we pass the test, go
        # ahead and save--we do not need to apply rules
        # again because we passed them all (failure
        # would mean do NOT save)
        if test_and_save and failure_data == None:
            print "[pid:%d]" % os.getpid(), "SAVING SUCCESSFUL VELOCITY EVENT %s" % str(ve)
            ve.redis_set()
        
        return ve, failure_data

    # validate parameters for a particular velocity type
    def validate_params(self, user, game, gamehistory, unique_id):
        if self.requires_user and user == None:
            raise VelocityMissingParameterException('velocity type requires user')
        if self.requires_game and game == None:
            raise VelocityMissingParameterException('velocity type requires game')
        if self.requires_gamehistory and gamehistory == None:
            raise VelocityMissingParameterException('velocity type requires gamehistory')
        if self.requires_unique_id and unique_id == None:
            raise VelocityMissingParameterException('velocity type requires unique ID')

    # lock the necessary record
    # NOTE: make sure you follow the app-wide locking order
    # NOTE: these functions already use Redis
    def lock_related(self, user, game, gamehistory, unique_id):
        if self.requires_gamehistory:
            from ilarcade.ilgames.models import SATEGameTurnLock
            SATEGameTurnLock.lock_gamehistory(gamehistory)
        if self.requires_user:
            from ilarcade.notifications.models import NotificationLock
            NotificationLock.lock_user_queue(user)

    # fetch any existing events related to a type
    # NOT TRUE FOR REDIS: NOTE: this actually returns a query set with the
    # correct filters rather than actually fetching
    # records
    def get_events(self, user = None, game = None, gamehistory = None, unique_id = None, date_starting = None, date_ending = None, include_removed = False):

        self.validate_params(user, game, gamehistory, unique_id)

        # determine start/end dates
        if date_ending == None:
            date_ending = timezone.now()
        if date_starting == None:
            date_starting = date_ending - datetime.timedelta(0, self.timespan)

        # with Redis, we index by all the keys at once, but
        # we can only retrieve by the date range once the
        # correct index is identified; we have to apply the
        # remaining filters afterwards
        events = VelocityEvent.redis_get_by_zindex(0, [
                self.id,
                user.id if user != None else None,
                game.id if game != None else None,
                gamehistory.id if gamehistory != None else None,
                unique_id,
            ], [ date_starting, date_ending ])
        
        if not include_removed:
            events = [ e for e in events if e.date_removed == None ]
            
        # return the full set of objects; they are already
        # in the correct order
        return events

#        # apply filters
#        qs = self.events.filter(date_created__gt = date_starting, date_created__lte = date_ending)
#
#        if self.requires_user:
#            qs = qs.filter(user_id = user.id)
#        if self.requires_game:
#            qs = qs.filter(game_id = game.id)
#        if self.requires_gamehistory:
#            qs = qs.filter(gamehistory_id = gamehistory.id)
#        if self.requires_unique_id:
#            qs = qs.filter(unique_id = unique_id)
#
#        if not include_removed:
#            qs = qs.filter(date_removed__isnull = True)
#
#        # give back a query set rather than explicit results
#        return qs.order_by('date_created', 'id')

    # given a list of events, walk through the rules and
    # check them for violations
    # NOTE: events MUST include velocity_event
    # NOTE: velocity_event is the one passed to actions
    # NOTE: returns the params of the LAST violated rule
    # that had no action
    def apply_rules(self, velocity_event, events, date_ending = None, do_actions = True):

        # fix up parameters
        if date_ending == None:
            date_ending = velocity_event.date_created

        rv = None
        for r in self.rules:
            # sum the weight of all the events within timespan
            date_starting = date_ending - datetime.timedelta(r['timespan'])
            weight = sum([ ve.weight for ve in events if ve.date_created > date_starting and ve.date_created <= date_ending ])
            
            # see if this violates the constraint
            if ((r['trigger'] == 'equal' and weight == r['limit']) or
                (r['trigger'] == 'above' and weight > r['limit'])):
                
                # do the action
                if r['action'] == None:
                    # this is a straight test
                    rv = r['params']
                    
                elif do_actions:
                    # this is some other action, and we're allowed to do it
                    action = getattr(self, 'action_' + r['action'])
                    if not callable(action):
                        raise Exception('found action attribute but it is not callable')
                    action(velocity_event, weight, **r['params'])

        return rv
    
    # utility to expunge all old records
    # NOTE: we delete the records and their index
    # entries in batch
    def expunge(self):
        now = timezone.now()
        then = now - datetime.timedelta(0, self.expunge_after)
        #**** TODO: find all the indices and expunge them,
        # without having to fetch and parse the records
        #qs = self.events.filter(date_created__lt = then).delete()   # batch delete!

admin.site.register(VelocityType)

# a velocity event: an instance of the type being
# logged
class VelocityEvent(RedisShadow, models.Model):
    class Meta:
        abstract = True

    # what type of event?
    velocity_type = models.ForeignKey('velocity.VelocityType', related_name = 'events')

    # details of the event
    weight = models.IntegerField(default = 1)
    date_created = models.DateTimeField()
    date_removed = models.DateTimeField(blank = True, null = True)

    # these records go in the second shadow database slot
    # (this will make them easy to split off to a second
    # Redis instance)
    REDIS_SHADOW_POOL = 1

    # indices for redis
    # zindexes require the score field first, then the
    # fields used to fetch the set
    REDIS_SHADOW_ZINDEX = [
            ( 'date_created', ( 'velocity_type_id', 'user_id', 'game_id', 'gamehistory_id', 'unique_id' ), ),
        ]

    # other redis settings
    
    # a debugging string-cast
    def __unicode__(self):
        # use %s for id instead of %d because id may be None
        return u'[%(class)s:%s] %s: %d %s %s' % (self.__class__.__name__, unicode(self.id), self.velocity_type.tag, self.weight, self.date_created.isoformat(), '(removed)' if self.date_removed != None else '')

    # generate a unique hash for a given event
    # NOTE: this must be a repeatable operation;
    # it is used to validate event cancellations;
    # the actual value IS NOT saved with the record
    def generate_hash(self):
        SECRET_KEY = 'bvrbv76i4JevtuC&If58ob75nhno$VCDFu53VFHEhcgwetc685$VIOg49obh676'
        encoded_hash = ModelHashGenerator.generate_hash_core(1, SECRET_KEY, self.id, self.date_created.isoformat())
        return encoded_hash

    # given a velocity event, cancel it
    # NOTE: this removes it from the ZINDEX but doesn't
    # delete the actual record
    # NOTE: updates RIGHT AWAY, not at the end of the
    # request; this operation cannot be rolled back
    def cancel(self, date_removed = None):
        if date_removed == None:
            date_removed = timezone.now()
        
        # remove it from the index
        # technically this makes the index inaccurate...
        self.redis_remove_from_zindex(0)
    
        # force immediate save, skipping the indices
        # because we just removed it
        self.date_removed = date_removed
        self.redis_set(update_indices = False)

class VelocityEventAdmin(admin.ModelAdmin):

    # foreign key fields which should NOT be shown as drop-downs
    # (because doing so means populating the drop-down with the
    # complete set of options)
    raw_id_fields = ( 'user', 'gamehistory', )
    
admin.site.register(VelocityEvent, VelocityEventAdmin)

# an audit trail, useful for development or other debugging
class AuditTrail(models.Model):

    # who
    user_id = models.IntegerField(blank = True, null = True)    # not a foreign key; see design doc
    
    # when/where
    source_ip = models.IPAddressField()
    date_created = models.DateTimeField()
    
    # what
    event_type = models.CharField(max_length = 40)
    unique_id = models.CharField(max_length = 40)
    details = JSONField()

admin.site.register(AuditTrail)
