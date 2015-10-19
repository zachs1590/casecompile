from django.db.models.manager import QuerySet
from django.utils.text import slugify
import datetime
import importlib
import numbers
import os
import re
import string
import types

# shared code

# there are some configuration options which should be set for
# some of these tools and classes:
#
#   CAXIAM_FASTSAVE             acts as a master switch to disable FastSave without editing lots of code
#   CAXIAM_FASTSAVE_DUMP_INFO   display debugging data on FastSave optimizations

# compare version strings
#
# A version string is compared character-by-character,
# except that whenever digits are encountered, all consecutive
# digits are converted to an integer and compared. Therefore:
#   1.1 < 1.2
#   1.2 < 1.10
#   1.2a < 1.2q
#   1.1.15 < 1.2.9
#   1.103b < 1.1011c    !! 103 < 1011
#   1.1.b < 1.01.c      !! b < c
#   1.01 < 1.1          !! lexical compare if no difference
#
# NOTE: this does not deal with Unicode digits other than 0-9.
# Don't try to do cute things with version numbers.
#
digit_extractor = re.compile(r'[0-9]+')

def compare_versions(a, b):
    # null cases
    if a == None and b == None:
        return 0
    elif a == None:
        return -1
    elif b == None:
        return 1
        
    # non-null cases
    pos_a = 0
    pos_b = 0
    while pos_a < len(a) and pos_b < len(b):
        if a[pos_a] in string.digits and b[pos_b] in string.digits:
            # number-to-number comparison
            pa = digit_extractor.match(a, pos_a).group()
            pb = digit_extractor.match(b, pos_b).group()
            na = int(pa, 10)
            nb = int(pb, 10)
            r = cmp(na, nb)
            if r != 0:
                return r
                
            pos_a += len(pa)
            pos_b += len(pb)
            
        else:
            # simple character comparison
            r = cmp(a[pos_a], b[pos_b])
            if r != 0:
                return r
            pos_a += 1
            pos_b += 1

    # no differences using above algorithm; use regular
    # string comparison
    return cmp(a,b)

# useful conversion edge case handlers

# empty_if_none
# returns the original string, or '' if it's None
# (this is useful shorthand when s is a complicated expression)
def empty_if_none(s):
    return s if s != None else ''

# Enumeration
#
# Django's support for enumerated types is... quirky. As in,
# you define a list of (value, label) pairs and pass it to an
# integer/char field, and in the admin it restricts the set.
# It does NOT create an actual ENUM field type, nor does it
# create a foreign-key type, nor does it enforce the choices
# on direct assignment. And referencing the values by label
# in your code isn't possible.
#
# What we would LIKE is to be able to reference
# classname.ENUM_LABEL directly AND have that automatically
# used for the choices on the field. We'd really like it to
# be enforced, but we'll settle for not.
#
# Use this way:
#
# class MyModel(model.Model):
#
#     MY_ENUMS = Enumeration(
#             (0, 'FOO'),
#             (1, 'BAR'),
#         )
#     enum_field = models.IntegerField(choices = MY_ENUMS.choices)
#
# print MyModel.MY_ENUMS.FOO
# >>> 0
#
# NOTE: if your list of enumerated values is longer than 254,
# you won't be able to pass it directly as parameters because
# Python function parameters are actually tuples and tuples are
# capped at 254 entries. Instead, pass choices = [ <tuples> ]
#
# NOTE: if you pass a third element in each tuple, it will be
# stored as a "display" value, a human-readable form. Use the
# get_display() method to retrieve these.
#
class Enumeration(object):
    
    _enumerated_list = None
    _enumerated_dict = None
    _enumerated_display = None
    _enumerated_display_list = None
    
    def __init__(self, *args, **kwargs):
        self._enumerated_list = kwargs.get('choices', args)
        
        # choices must be a list of 2-tuples to keep South happy
        self.choices = [ (t[0], t[1]) for t in self._enumerated_list ]
        
        # reverse each of the tuples and use them to build a dict,
        # indexed by name
        self._enumerated_dict = dict([ (t[1], t[0]) for t in self._enumerated_list ])
        
        # and store the display labels indexed by value, using
        # the label if no human-readable label is availble
        self._enumerated_display_list = [ (t[0], t[2] if len(t) > 2 else t[1]) for t in self._enumerated_list ]
        self._enumerated_display = dict(self._enumerated_display_list)

    # gets a list suitable for a human-readable drop-down menu,
    # in enumeration order
    @property
    def display_choices(self):
        return self._enumerated_display_list

    # look up an attribute, if it is not found
    # elsewhere (we look up the name in our set
    # of enumerations)
    def __getattr__(self, attr):
        if attr not in self._enumerated_dict:
            # pretend we're a real attribute, and throw a similar exception,
            # instead of KeyError from a dict lookup
            raise AttributeError()
        return self._enumerated_dict[attr]

    # look up a value to get the name
    # values are given as (value, str) pairs
    # NOTE: returns None if no match is found
    def get_label(self, value):
        for t in self._enumerated_list:
            if t[0] == value:
                return t[1]
        return None

    # look up a value to get the display label
    # NOTE: returns None if no match is found
    def get_display(self, value):
        return self._enumerated_display.get(value, None)

    # in a JSON parameter string we accept either the
    # name or the number, but we need a consistent way
    # to get back to the number
    # NOTE: does NOT validate the data; numbers not part
    # of the enumeration will not be rejected and names
    # not part of the enumeration will raise KeyError
    def get_value(self, label):
        if isinstance(label, basestring):
            return self._enumerated_dict[label]
        else:
            # already a value
            return label

    # get_value() always looks at the programmatic label,
    # but we may have additional values in each tuple
    # that we need to look up against
    # NOTE: returns None if no match is found
    # NOTE: returns the VALUE, not the LABEL
    def get_value_by_tuple_entry(self, value, tuple_index):
        for t in self._enumerated_list:
            if t[tuple_index] == value:
                return t[0]
        return None

    # fetch the entire tuple for a particular value
    def get_tuple(self, value):
        for t in self._enumerated_list:
            if t[0] == value:
                return t
        return None

    # get_<field>_tuple
    #
    # Django automatically creates a get_<field>_display
    # function for each IntegerField using enumerated
    # choices. The problem is that it uses element 1 from
    # the tuple, which is the programmatic label (shame on
    # the Django dev team for not using better enumerations).
    # We want to return the nicer label at element 2, but
    # also make it possible to access the rest of the
    # enumeration's data in case it has been provided.
    #
    # To accommodate this, we create a wrapper that makes
    # a property that returns the tuple from the enumerated
    # type. It requires the field name.
    #
    # NOTE: this is a function generator
    #
    def get_tuple_method(self, field_name):

        # this is the one-off function we need
        def _inner(inner_self):
            return self.get_tuple(getattr(inner_self, field_name))

        # return that function
        return _inner

    # methods to make the class iterable
    def __len__(self):
        return len(self._enumerated_list)
        
    def __iter__(self):
        return self._enumerated_list.__iter__()
        
    def __getitem__(self, key):
        return self._enumerated_list[key]
        
    def __setitem__(self, key, value):
        raise TypeError("'Enumeration' object does not support item assignment")
        
    def __delitem__(self, key):
        raise TypeError("'Enumeration' object does not support item assignment")

    # without this, 'in' tests by iterating, which isn't useful;
    # we want to test if a label is in the enumeration
    def __contains__(self, key):
        return key in self._enumerated_dict

# ParameterProxy
#
# Django's template language is deliberately hobbled
# to make it extremely simple, but one of its limitations
# is that it's not possible to invoke methods on an object
# unless they require no parameters or they are properties.
# This makes certain kinds of functions cumbersome and is
# why Django creates get_<field>_display methods. To work
# around this, we create a "parameter proxy" method which
# returns a new object, which Django will then pass the
# next token to as a field lookup, which we catch and give
# to the original requested method as a parameter.
#
# To use this, you must define your method first and then
# your proxy method:
#
# class Foo(object):
#     def bar(self, param):
#         ...
#     bar_proxy = property(parameter_proxy('bar', enumeration = MY_ENUM))
#
# This is because we want bar to exist as a named method
# on the object, and if we simply wrap bar in a decorator,
# the only way to access it will be through the proxy,
# which we don't want to do if we don't have to.
#
# You could also apply ParameterProxy to an existing
# function directly and place a reference to the proxy in
# a context passed into a template, to give a template
# access to a function. That would be unusual.
#
class ParameterProxy(object):

    # construction requires a reference to the proxied method
    # and whether it is an enumeration
    def __init__(self, proxy_method, enumeration = None):
        self.proxy_method = proxy_method
        self.enumeration = enumeration

    # any time we get a request for a particular attribute
    # on the object, call the method with the attribute
    # as the first parameter; if the parameter is meant
    # to be an enumeration, look up the enumeration first
    # and validate it
    def __getattr__(self, attr):
        if self.enumeration:
            attr = self.enumeration.get_value(attr)  # raises KeyError if it's invalid
        return self.proxy_method(attr)

# the property generator, required since we need
# access to self; this allows the proxy to be
# generated just once (for the class) but still
# invoked properly per object
def parameter_proxy(proxy_method_name, enumeration = None):
    
    def inner(self):
        cachename = proxy_method_name + '_proxy'
        if not hasattr(self, cachename):
            proxy_method = getattr(self, proxy_method_name)
            setattr(self, cachename, ParameterProxy(proxy_method, enumeration))
        return getattr(self, cachename)

    return inner

# to_json
#
# extract object attributes into a dict, given an explicit
# list of attributes; this is primarily used to allow an
# object to control its own JSON serialization by identifying
# the list of (public) fields, without doing the boring work
# of actually extracting those fields into a dict and then
# recursively checking each of the fields for further to_json
# methods
#
# NOTE: if an extracted field also has a to_json
# method, it will be used
#
# NOTE: if a field is a callable instead of a
# literal, it will be invoked as a function and
# the return should be (key, value)
#
# NOTE: some of the tweaks are to accomodate C#, since the
# original code was developed for Innovative Leisure and their
# Unity C# projects
#
def to_json(obj, attrlist = None, **kwargs):
    if isinstance(obj, datetime.datetime):
        # Tricky bit: .isoformat() will include a time zone
        # offset if one is known, even if that time zone is
        # UTC (this is rational). However, C# doesn't have
        # a format that conditionally accepts this, so we
        # define our API as always passing UTC and we strip
        # any timezone from the result if one is provided
        #print "[pid:%d]" % os.getpid(), 'datetime'
        return obj.isoformat()[:19]

    elif isinstance(obj, (str, unicode, tuple, numbers.Number, types.NoneType)):
        # "scalar" type, can be converted to a single JSON element
        # (no conversion required)
        #print "[pid:%d]" % os.getpid(), 'direct type', obj.__class__.__name__
        return obj
        
    elif isinstance(obj, (list, QuerySet)):
        # given a bare list or QuerySet; JSONify each element
        # NOTE: callables are NOT supported since they return (k,v)
        # and we don't use keys in lists
        #print "[pid:%d]" % os.getpid(), 'list type', obj.__class__.__name__, repr(obj)
        d = []
        for o in obj:
            if hasattr(o, 'to_json'):
                d.append(o.to_json())
            else:
                d.append(to_json(o))    # hope that it can be serialized automatically
            
        return d
    
    elif isinstance(obj, dict):
        # a dict; process all the elements to JSONify them
        # (we do not assume they are already JSON-ready)
        #print "[pid:%d]" % os.getpid(), 'dict type', obj.__class__.__name__, repr(obj)
        d = {}
        if attrlist == None:
            attrlist = obj.keys()       # attrlist is optional for dicts and defaults to all of it
        for a in attrlist:
            if callable(a):
                #print "[pid:%d]" % os.getpid(), 'fn:', a.__name__
                a, v = a(obj)           # get key, value pair from a function
            elif isinstance(a, tuple):
                #print "[pid:%d]" % os.getpid(), 'tuple:', a.__name__
                a, v = a                # use the provided value rather than looking it up by name
            else:
                #print "[pid:%d]" % os.getpid(), 'attr:', repr(a)
                v = obj[a]              # have key, get value (and raise KeyError if missing)
    
            #print "[pid:%d]" % os.getpid(), 'value:', v.__class__.__name__, repr(v)
            if hasattr(v, 'to_json'):
                d[a] = v.to_json()
            else:
                # something else; recursively JSONify it
                # NOTE: this is a bit of a performance hit and it
                # creates copies of all the nested data, even if
                # they are already in JSON-compatible form, but
                # it makes it MUCH easier to convert data coming
                # out of Django QuerySets
                d[a] = to_json(v)

        return d

    else:
        # an object; convert to a dict that can be JSON-serialized
        d = {}
        if attrlist == None:
            raise Exception('attrlist cannot be none for objects of type ' + obj.__class__.__name__)
        for a in attrlist:
            if callable(a):
                #print "[pid:%d]" % os.getpid(), 'fn:', a.__name__
                a, v = a(obj)           # get key, value pair from a function
            elif isinstance(a, tuple):
                #print "[pid:%d]" % os.getpid(), 'tuple:', a.__name__
                a, v = a                # use the provided value rather than looking it up by name
            else:
                #print "[pid:%d]" % os.getpid(), 'attr:', repr(a)
                v = getattr(obj, a)     # have key, get value (and raise AttributeError if missing)

            #print "[pid:%d]" % os.getpid(), 'value:', v.__class__.__name__, repr(v)
            if hasattr(v, 'to_json'):
                d[a] = v.to_json()
            else:
                # something else; recursively JSONify it
                # NOTE: this is a bit of a performance hit and it
                # creates copies of all the nested data, even if
                # they are already in JSON-compatible form, but
                # it makes it MUCH easier to convert data coming
                # out of Django QuerySets
                d[a] = to_json(v)

        return d

# given a particular string, attempt to parse it as an
# ISO-format datetime and return that; return None if
# not valid
def parse_datetime(v):
    try:
        return datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        return None

# for a particular module, find all the sub-modules and import them
# (first-level crawl only)
#
# pass in the parent module name (typically globals()['__name__']) and
# the file path list (typically globals()['__path__'])
#
# NOTE: __path__ will NOT be defined if you recursively import, so
# don't do that
#
# This is primarily useful for the cron modules, which need to invoke
# the sub-modules one by one, but do so in a predictable (alphabetical)
# order, with exception-catching for each one. A boolean is returned
# indicating whether any of the sub-modules failed to import properly.
# 
def import_all_submodules(mod, path, catch_errors = False):
    had_error = False
    path = path[0]
    files = os.listdir(path)
    files.sort()                                            # sort them to ensure a consistent order
    for f in files:
        if f != '__init__.py' and f.endswith('.py'):        # a Python script, not our __init__ module
            try:
                importlib.import_module(mod + '.' + f[:-3]) # go ahead and import it
            except Exception, e:
                had_error = True
                if not catch_errors:
                    # we actually didn't want to trap these, re-raise it
                    raise
                    
                # otherwise we need to record this exception; we assume
                # we're running in an environment where STDOUT is logged
                # NOTE: we do this whether we're in DEBUG mode or not

                # sys.exc_info() returns a tuple (type, exception object, stack trace)
                # traceback.format_exception() formats the result in plain text, as a list of strings
                import sys
                import traceback
                backtrace_text = ''.join(traceback.format_exception(*sys.exc_info()))
                print '!!!! exception detected while importing submodules'
                print backtrace_text
                
                # and now we swallow the exception and move on to the
                # next one

    return had_error

# Python doesn't have an easy way to recursively merge
# dicts. So we recursively crawl the damn things and do
# it ourselves.
#
# http://stackoverflow.com/questions/7204805/dictionaries-of-dictionaries-merge/24837438#24837438
#
# NOTE: modifies dict1 in place as well as returns it.
# If you need to preserve it, use copy.deepcopy() on it
# first.
#
def merge_dicts(dict1, dict2):
    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        return dict2
    for k in dict2:
        if k in dict1:
            dict1[k] = merge_dicts(dict1[k], dict2[k])
        else:
            dict1[k] = dict2[k]
    return dict1

# slugify extension
#
# Django's slugify() is nice and robust, except that it
# demands unicode input on Python 2 and it drops / instead
# of replacing it with -
#
# NOTE: we call it caxiam_slugify instead of just slugify
# so that wherever it appears in code, it's crystal clear
# that it's NOT Django's slugify; this helps prevent subtle
# bugs due to bad import directives
#
def caxiam_slugify(value):
    return slugify(unicode(value.replace('/','-')))
