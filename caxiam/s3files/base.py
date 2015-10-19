from django.conf import settings
from django.contrib import admin
from django.db import models
from django.utils import timezone
from caxiam.common import Enumeration, parameter_proxy
from caxiam.model_mixins import AutoHashModel
from caxiam.s3files.process_images import process_image, RESIZE_MODES, ANCHOR_HORIZONTAL, ANCHOR_VERTICAL
import datetime
import os

# S3 Stored File base model
#
# We need to store many files that we intend to
# serve via Amazon S3 rather than run the web
# site infrastructure ourselves and serve static
# files via nginx. We also want to track metadata
# for these files and be able to create thumbnail
# versions of some of these files. Rather than
# create separate models for each category of
# file, we use a single model with conditionally-
# populated fields.
#
# This is an abstract base class. You must create
# an actual implementation of this class that will
# likely contain a link to the AppUser class so
# uploaded files can be tracked per user.
#
# If you want automatic derived-image processing,
# override the 
#
class AbstractStoredFile(AutoHashModel, models.Model):

    # hash
    # NOTE: you should probably override the secret
    # in your derived class
    AUTOHASH_SECRET = '*O)&45vfv4u6BRG4689vvfg9*&%HN06bnKLgti64uf&*($hnoj6i()%^bn8975H8o&4g5&(g65b*75BH)858b'
    AUTOHASH_FIELDS = [ 'original_filename', 'size', 'mime_type', ]
    hash = models.CharField(max_length = 43, unique = True, blank = True, null = True)  # will be populated prior to save
    
    # file metadata
    original_filename = models.CharField(max_length = 256, blank = True, null = True)   # from the client's system, if available; mainly used for pretty names for the user
    size = models.IntegerField(blank = True, null = True)                               # null only if unknown (rare)
    width = models.IntegerField(blank = True, null = True)                              # if image or video type
    height = models.IntegerField(blank = True, null = True)                             # if image or video type
    duration = models.DecimalField(blank = True, null = True, max_digits = 10, decimal_places = 3)  # if audio or video type; length of time, in seconds
    mime_type = models.CharField(max_length = 128, blank = True, null = True)           # long field because Microsoft uses long MIME types
    # NOTE: mime_type comes from the client and thus we assume is not trustworthy

    # for certain file types, we will attempt to open the
    # file and extract some additional metadata from it
    # (dimensions, duration); if this fails, this flag will
    # be set to False so we know the file is corrupt
    #
    # NOTE: for files which are NOT parsed, this will always
    # remain True
    #
    is_valid = models.BooleanField(default = True)

    # has this been copied to S3 yet?
    REMOTE_STATUS = Enumeration(
            (-1, 'LOCAL_CORRUPT'),      # this file appears to be incorrectly saved on the local server
            ( 0, 'LOCAL_ONLY'),         # this is on the local server and should not be copied (and may or may not be complete)
            ( 1, 'LOCAL_INCOMPLETE'),   # this is still incomplete on the local server (so should not be copied)
            ( 2, 'LOCAL_READY'),        # this is ready to be copied
            ( 3, 'IN_PROGRESS'),        # this is being copied
            ( 4, 'REMOTE_ONLY'),        # this is completed on S3
        )
    remote_status = models.IntegerField(choices = REMOTE_STATUS.choices, default = 0)

    # is this a thumbnail/derived version of another file?
    derived_from = models.ForeignKey('StoredFile', related_name = 'derivations', blank = True, null = True) # null for complete/original file
    
    # possible choices for derived files; we enumerate
    # these so that we can be consistent in how they are
    # applied, and also so that we can automatically
    # create some of these at file upload time
    #
    # for each derivation, provide:
    #   value, label, create_mode, (width,height), resize_mode, anchor_horizontal, anchor_vertical, expand_color
    #
    DERIVATION_MODES = Enumeration(
            (0, 'MANUAL'),      # require manual creation
            (1, 'LAZY'),        # create as soon as it's requested
            (2, 'IMMEDIATELY'), # create when file is uploaded
        )
    DERIVATION_TYPES = Enumeration(
            (0, 'THUMBNAIL', DERIVATION_MODES.LAZY, (50,50), RESIZE_MODES.CROP, ANCHOR_HORIZONTAL.CENTER, ANCHOR_VERTICAL.CENTER, None),
        )
    derivation_type = models.IntegerField(choices = DERIVATION_TYPES.choices, blank = True, null = True)    # null for complete/original file

    # when was this created and/or stored in S3?
    date_created = models.DateTimeField()
    date_stored = models.DateTimeField(blank = True, null = True)
    
    # Files are uploaded and processed before the thing
    # they ultimately belong to is finalized; this means
    # there is a workflow where the user abandons the file
    # part-way through the process. We need to be able to
    # clean up these files in a generic way, so we include
    # the option to mark a file as auto-expiring; when the
    # user commits the action that claims the file, this
    # field can then be cleared and the file preserved.
    #
    # NOTE: this process is independent of whether it is
    # copied to S3 or not; a file may get fully copied
    # to S3 and then discarded.
    #
    date_expires = models.DateTimeField(blank = True, null = True)

    # additional fields are primarily foreign key links
    # to other records; however in many instances you will
    # find that a better pattern is to create an intermediate
    # record that contains additional metadata (title,
    # description, thumbnail processing choices, etc.) that
    # links back to your other models, and contains a link
    # to a StoredFile object
    #
    # user = models.ForeignKey('appuser.AppUser', related_name = 'stored_files', blank = True, null = True)    

    # metadata / restrictions
    class Meta:
        abstract = True

    # a debugging string cast
    # NOTE: ONLY use this for debugging, never in user-
    # facing code
    def __unicode__(self):
        return u"[%(class)s:%(id)s] %(short_hash)s %(size)s %(width)s x %(height)s %(mime_type)s" % {
                'class': self.__class__.__name__,
                'id': unicode(self.id),                             # so that None will not crash
                'short_hash': self.hash[:8] if self.hash else '-',
                'size': unicode(self.size),
                'width': unicode(self.width),
                'height': unicode(self.height),
                'mime_type': unicode(self.mime_type),
            }

    # because the derived class will override the enumeration
    # for derivation_type, we want to update it on creation
    def __init__(self, *args, **kwargs):
        super(AbstractStoredFile, self).__init__(*args, **kwargs)
        self._set_field_choices(field_name = 'derivation_type', choices = self.DERIVATION_TYPES.choices)

    def _set_field_choices(self, field_name, choices):
        self._meta.get_field_by_name(field_name)[0]._choices = choices

    #
    # utility functions
    #
    
    # determine whether a file is ready for access via get_url()
    @property
    def is_ready(self):
        return self.is_valid and self.remote_status in [ REMOTE_STATUS.LOCAL_ONLY, REMOTE_STATUS.REMOTE_ONLY ]

    # file type tests
    #
    # strictly speaking, we could determine these by just checking
    # the first part of the MIME type, but practically we are
    # asking a much narrower question, which is whether the file
    # is of a type within that category that can be processed by
    # our code
    
    @property
    def is_image(self):
        return self.mime_type in [ 'image/gif', 'image/jpeg', 'image/png', ]    # not included: Windows BMP, TIFF
        
    @property
    def is_video(self):
        return self.mime_type in [ 'video/mpeg', 'video/webm', 'video/x-flv', ] # not included: Windows Media
        
    @property
    def is_audio(self):
        return self.mime_type in [ 'audio/mpeg', 'audio/x-wav', ]               # not included: RealAudio, AIFF, Windows Media

    # This will mark the file to not expire because we want to make it the usable workable image
    # if the file you are trying to keep IS A DERIVATION, it will find it's parent and keep all of it's parents derivations
    def keep(self):
        keepable = self
        if self.derivation_type is not None:
            keepable = self.derived_from
        keepable.date_expires = None
        keepable.save(update_fields= ['date_expires']) #saves itself
        keepable.derivations.update(date_expires = None) # saves it's derivations

    # get the URL of a file
    # if the file is remote, returns a remote URL; otherwise returns
    # a URL for the host site
    #
    # NOTE: we don't assume MEDIA_URL for remote files because we
    # may need to set these differently
    #
    def get_url(self):
        if settings.CAXIAM_S3FILES_REMOTE_MODE == 'local':
            return settings.MEDIA_URL + self.get_path()
        else:
            return settings.CAXIAM_S3FILES_REMOTE_URL + self.get_path()

    url = property(get_url)

    # get a local path for this file (assuming the file
    # is actually local, this is where it *should* be)
    def get_local_path(self):
        return os.path.join(settings.MEDIA_ROOT, self.get_path())

    # get a relative path to where the data is stored
    # NOTE: this is just a partial pathname; for a full URL,
    # use the get_url() method instead
    #
    def get_path(self):

        # store the extension of the file. we'll use this to build the hashed file name
        root, ext = os.path.splitext(self.original_filename)

        # we are using the first 2 characters of the hash to make 2 random directories
        # ex. /a/b/abfile.mp4 this is to help s3 disperse the workload of serving many files.
        # grab the first 2 characters of the hash so we can use them as directory names
        a = self.hash[:1]
        b = self.hash[1:2]

        # add the original extension back to the end of the path        
        location = os.path.join(a, b, self.hash + ext)
        if settings.CAXIAM_S3FILES_DIR != None:
            location = os.path.join(settings.CAXIAM_S3FILES_DIR, location)
        return location  

    # ensure the folders required for a file exist
    def ensure_path_exists(self):

        # get the media path for this environment and append the StoredFile's path.
        path = self.get_local_path()

        # look to see if the directory needs to be created first.
        dir_out = os.path.dirname(path) + os.sep
        if not os.path.exists(dir_out):
            os.makedirs(dir_out)            

    # write data to local disk (e.g. while processing an upload)
    def write_to_disk(self, data):

        # get the media path for this environment and append the StoredFile's path.
        path = self.get_local_path()

        # make sure the directory exists
        self.ensure_path_exists()

        # write to local disk
        try:
            with open(path, 'wb+') as destination:
                for chunk in data.chunks():
                    destination.write(chunk)
        except:
            # if we can't write the file, it's corrupted
            # (possibly because of low disk space) so update
            # the metadata record to indicate the file is bad
            self.is_valid = False
            self.remote_status = self.REMOTE_STATUS.LOCAL_CORRUPT
            self.save(update_fields = [ 'is_valid', 'remote_status' ])
            return

        # update status, if necessary
        if settings.CAXIAM_S3FILES_REMOTE_MODE != 'local':
            self.remote_status = self.REMOTE_STATUS.LOCAL_READY
            self.save(update_fields = [ 'remote_status' ])

    # default remote status and expiry times
    @classmethod
    def default_remote_status(cls):
        return cls.REMOTE_STATUS.LOCAL_ONLY if settings.CAXIAM_S3FILES_REMOTE_MODE == 'local' else cls.REMOTE_STATUS.LOCAL_INCOMPLETE

    @classmethod
    def default_date_expires(cls, now):
        return None if settings.CAXIAM_S3FILES_AUTO_EXPIRE_UPLOADS == None else now + datetime.timedelta(settings.CAXIAM_S3FILES_AUTO_EXPIRE_UPLOADS)

    # fetch a derived image, automatically generating it
    # if it's meant to be lazy-generated
    #
    # NOTE: returns None if no image of that particular
    # derivation exists (or if one would, via lazy
    # generation, but process_lazy has been set to False,
    # or if one exists but it's corrupt)
    #
    # NOTE: this result is cached so repeated queries
    # will not incur repeated database hits, especially
    # from templates using the ParameterProxy.
    #
    # NOTE: if you disable lazy generation, the resulting
    # "no image" response will be cached; use force_reload
    # to bypass the cache and allow lazy generation
    #
    _derivation_cache = None
    def _get_derivation(self, derivation_type, process_lazy = True, force_reload = False):
        derivation = self.DERIVATION_TYPES.get_tuple(derivation_type)
        if derivation == None:
            raise Exception('unknown file derivation type')

        # see if we have this derivation
        # check the cache first and return it from there
        if self._derivation_cache == None:
            self._derivation_cache = {}
        if derivation_type not in self._derivation_cache or force_reload:
            self._derivation_cache[derivation_type] = self.derivations.filter(derivation_type = derivation_type).first()
            allow_lazy = True
        else:
            # we already have a "no" answer in the cache, don't 
            allow_lazy = False
        derived_file = self._derivation_cache[derivation_type]

        if derived_file:
            # yes, we have one
            if derived_file.remote_status == self.REMOTE_STATUS.LOCAL_CORRUPT:
                # but it's corrupt; we don't automatically
                # reprocess it, we just act like it's not
                # there (to avoid endlessly redoing the work)
                return None

            # otherwise we'll take this one
            return derived_file

        # split apart the derivation data            
        value, label, create_mode, size, resize_mode, anchor_horizontal, anchor_vertical, expand_color = derivation
        
        # if we're allowed to, generate the missing derivation
        # (this will automatically save the result in the cache)
        if (create_mode == self.DERIVATION_MODES.LAZY or create_mode == self.DERIVATION_MODES.IMMEDIATELY) and process_lazy:
            derived_file = self.generate_derivation(derivation_type)
            
        # return whatever we have
        return derived_file
        
    # a version of get_derivation which does not require a
    # parameter directly and is usable in templates
    get_derivation = property(parameter_proxy('_get_derivation', DERIVATION_TYPES))

    # actually produce a derived file, given a rule
    # NOTE: if you already have the original image available, pass it
    # in to prevent this function from re-reading it
    def generate_derivation(self, derivation_type, original_image = None):
        derivation = self.DERIVATION_TYPES.get_tuple(derivation_type)
        if derivation == None:
            raise Exception('unknown file derivation type')

        #print 'generating derivation:', repr(derivation)

        # we're going to write to the cache no matter what, so
        # make sure it's set up
        if self._derivation_cache == None:
            self._derivation_cache = {}

        if self.remote_status == self.REMOTE_STATUS.LOCAL_CORRUPT or not self.is_valid:
            # we already know this file is corrupt; do not
            # attempt to process it
            
            # update cache as we know we don't have this derivation type
            self._derivation_cache[derivation_type] = None

            # and give back nothing
            return None

        # split apart the derivation data            
        value, label, create_mode, size, resize_mode, anchor_horizontal, anchor_vertical, expand_color = derivation
        
        # if we were not given an original image, we'll need to
        # create one from the disk file
        # NOTE: this won't work if the file isn't local
        # NOTE: we use "is" instead of == because Pillow has a
        # bug, where it attempts to look inside the image, but
        # if the image is invalid, it blows up
        if original_image is None:
            # do the imports here so that we don't depend on PIL just
            # to include caxiam-python
            from PIL import Image

            try:
                original_image = Image.open(self.get_local_path())
            except Exception, e:
                # any problem with fetching the image will result
                # in no derivation being available--and that result
                # is cached
                self._derivation_cache[derivation_type] = None
                #print 'failed to read image:', str(e)
                return None
                
        # we have an image, run the processing rules to create
        # a new image (see caxiam.s3files.process_images for this
        # code)
        try:
            new_image = process_image(original_image, size, resize_mode, anchor_horizontal, anchor_vertical, expand_color)
            
            # we have a new image, construct a new metadata record
            # for it and save it (to generate a hash)
            #
            # We'd rather not save this record until the file is
            # written because if anything goes wrong with that,
            # we have to remove this record, but we need the hash
            # in order to place the file properly, and to generate
            # the hash we need to know the file size, so catch-22.
            # Instead we create the record but mark its status as
            # incomplete so it won't get used.
            #
            now = timezone.now()
            sf = self.__class__.objects.create(
                    original_filename = '_auto_generated.jpg',
                    width = new_image.size[0],          # taken from the image, not the rule, in case some later rule types allow cropped images
                    height = new_image.size[1],
                    mime_type = 'image/jpeg',           # derived images are always JPEG
                    remote_status = self.default_remote_status(),
                    derived_from = self,
                    derivation_type = derivation_type,
                    date_created = now,
                    date_expires = self.date_expires,   # generated files expire when their parent file expires
                )
                
            # write the image
            # NOTE: if this goes wrong, we have to invalidate it
            try:
                sf.ensure_path_exists()
                new_image.save(sf.get_local_path(), quality = 90)
            except Exception, e:
                sf.is_valid = False
                sf.remote_status = self.REMOTE_STATUS.LOCAL_CORRUPT
                sf.save(update_fields = [ 'is_valid', 'remote_status' ])
                #print 'failed to save processed image:', str(e)
                
                # re-raise the exception so we record that we have no
                # derived image
                raise
            
        except Exception, e:
            # any problem with processing the image will result
            # in no derivation being available--and that result
            # is cached
            self._derivation_cache[derivation_type] = None

            # this is how Django logs the exception; see code in
            # django.core.handlers.base
            import logging
            import sys

            logger = logging.getLogger('django.request')
            logger.error('Internal Server Error: %s', 'unknown',
                exc_info=sys.exc_info(),
                extra={
                    'status_code': 500,
                    'request': None
                }
            )

            #print 'failed to process image:', str(e)
            return None

        # otherwise we have a newly-minted derived image, save
        # it in the cache and return it
        self._derivation_cache[derivation_type] = sf
        return sf
