from django import forms
from django.conf import settings
from django.utils import timezone
from caxiam.ajax import AjaxForm, AjaxFormView, AjaxSuccessResponse
from crispy_forms.layout import Layout, Row, Div, Submit, HTML
import datetime
from PIL import Image

# form classes

# base class that contains just the upload field
class AjaxFileUploadForm(AjaxForm):

    uploaded_file = forms.FileField(label = 'Uploaded File', required = True)

    def __init__(self, *args, **kwargs):
        super(AjaxFileUploadForm, self).__init__(*args, **kwargs)
        self.helper.form_class = '_ajax_upload'

# test class that includes a submit button and
# bypasses the AJAX processing
class TestFileUploadForm(AjaxFileUploadForm):

    def __init__(self, *args, **kwargs):
        super(TestFileUploadForm, self).__init__(*args, **kwargs)
        self.helper.add_input(Submit('submit', 'Submit'))
        self.helper.form_class = '_manual_submit'

# a single-file upload form; when the first
# file is uploaded, the upload field gets hidden
class SingleFileUploadForm(AjaxFileUploadForm):
    
    def setup_target_field(self, target_form_id, target_field_id):
        self.helper.attrs['data-target-form-id'] = target_form_id
        self.helper.attrs['data-target-field-id'] = target_field_id
    
    def setup_form_helper(self, helper):
        helper.attrs = {
                'data-max-files': '1',
            }
        helper.layout = Layout(
                'uploaded_file',
                HTML('{% include "caxiam/upload_single.html" %}'),
            )

# by default, we just accept the uploaded form, create
# a storage record for it, and move the file to the
# appropriate place; extend this class to add more
# restrictions, such as per-user quotas
#
class AjaxFileUpload(AjaxFormView):
    form_class = AjaxFileUploadForm     # by default
    file_class = None                   # must be an app-specific AbstractStoredFile-derived class

    # assuming we're not just uploading for fun,
    # the host page script for managing uploads
    # will want to know what form/field should
    # be modified to have the file ID
    target_form_id = ''
    target_field_id = ''

    def prepare_form(self, request, form):
        form.setup_target_field(self.target_form_id, self.target_field_id)

    def process_form(self, request, form):
        # the form is valid and the file is either in RAM or
        # stored in a temporary disk file, but either way,
        # we are going to store it

        # quick reference to uploaded file object
        uf = request.FILES['uploaded_file']
        
        # before we can store it in a permanent place we need
        # a guaranteed-unique filename for it, so we need to
        # create and save the StoredFile record
        sf_attributes = self.get_stored_file_attributes(request, form)
        sf = self.file_class(**sf_attributes)

        #if hasattr(uf, 'temporary_file_path'):
        #    print uf.temporary_file_path()
        #else:
        #    print 'memory file'

        # before we save the record, see if it's an image type
        # that Pillow understands; if so, extract the metadata
        original_image = None
        if settings.CAXIAM_S3FILES_CHECK_IMAGES and sf.is_image:
            try:
                if not hasattr(uf, 'temporary_file_path'):
                    # entire file is in memory already
                    original_image = Image.open(uf)
                    
                else:
                    # file is multiple chunks, so written to
                    # disk
                    original_image = Image.open(uf.temporary_file_path())

                # valid image, extract metadata            
                sf.width = original_image.size[0]
                sf.height = original_image.size[1]
            
            except:
                # the file seems to be invalid
                sf.is_valid = False
            
        # we're done parsing the file; save the meta data
        # record to generate its hash
        sf.save()
        
        # write or move the file
        # NOTE: if anything goes wrong, the stored file
        # will be marked as invalid
        sf.write_to_disk(uf)
        
        # see if we need to create any derived images
        if sf.is_valid and original_image:

            for derivation in self.file_class.DERIVATION_TYPES:
                # split up the processing data
                value, label, create_mode, size, resize_mode, anchor_horizontal, anchor_vertical, expand_color = derivation

                if create_mode == self.file_class.DERIVATION_MODES.IMMEDIATELY:
                    # this is a process we need to do now, but pass the
                    # original image we have so it won't be re-created
                    sf.generate_derivation(value, original_image)

        # we save this in the local object so that if we need
        # to extend this class we can get at the results
        # without having to hack it up
        self.stored_file = sf
        
        # return a default result set
        return AjaxSuccessResponse(self.generate_results(sf))

    # invoked when the form is processed; override this to
    # customize the creation of the StoredFile-derived
    # metadata record, such as if it requires links to its
    # owner or other records
    #
    # NOTE: the record isn't actually created here, just the
    # parameters used to create it
    #
    def get_stored_file_attributes(self, request, form):
        now = timezone.now()
        uf = request.FILES['uploaded_file']
        return {
                'original_filename': uf.name,
                'size': uf.size,
                'mime_type': uf.content_type,
                'remote_status': self.file_class.default_remote_status(),
                'date_created': now,
                'date_expires': self.file_class.default_date_expires(now),
            }

    # generate result data, given a stored file record
    # override this if you need to customize results
    def generate_results(self, sf):
        results = {
                'file': {
                        'hash': sf.hash,
                        'size': sf.size,
                        'url': sf.get_url(),
                        'width': sf.width,
                        'height': sf.height,
                        'is_image': sf.is_image,
                        'is_video': sf.is_video,
                        'is_audio': sf.is_audio,
                    }
            }

        # add in the thumbnail data, if it was immediately
        # generated and is in the cache
        if 'THUMBNAIL' in sf.DERIVATION_TYPES and sf.DERIVATION_TYPES.THUMBNAIL in sf._derivation_cache:
            thumb = sf._get_derivation(sf.DERIVATION_TYPES.THUMBNAIL)   # _get_derivation to bypass ParameterProxy
            results['thumbnail'] = {
                    'hash': thumb.hash,
                    'size': thumb.size,
                    'url': thumb.get_url(),
                    'width': thumb.width,
                    'height': thumb.height,
                    'is_image': thumb.is_image,
                    'is_video': thumb.is_video,
                    'is_audio': thumb.is_audio,
                }

        return results
