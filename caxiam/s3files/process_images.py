from caxiam.common import Enumeration

# tools for processing images

# how to describe a transformation
RESIZE_MODES = Enumeration(
        (0, 'CROP'),
        (1, 'EXPAND'),
    )
ANCHOR_HORIZONTAL = Enumeration(
        (0, 'LEFT'),
        (1, 'CENTER'),
        (2, 'RIGHT'),
    )
ANCHOR_VERTICAL = Enumeration(
        (0, 'TOP'),
        (1, 'CENTER'),
        (2, 'BOTTOM'),
    )

# actually process the image; returns new thumbnail
# (which must be saved separately)
#
# NOTE: this is non-destructive on source_image so that
# multiple derived images can be made without reloading
# the source
#
def process_image(source_image, target_size, resize_mode, anchor_horizontal, anchor_vertical, expand_color):
    # do the imports here so that we don't depend on PIL just to
    # include caxiam-python
    from PIL import Image, ImageFile

    # apply the resize_mode and determine the source dimensions;
    # for cropping, too wide means we use the height to set size,
    # but for expanding, too wide means we use the width to set size
    # (it reverses the rule)
    #
    # NOTE: although we call it crop_size, it's really going to be
    # the final image size
    #
    aspect_ratio = float(target_size[0]) / float(target_size[1])
    is_too_wide = float(source_image.size[0]) / float(source_image.size[1]) > aspect_ratio
    if (resize_mode == RESIZE_MODES.CROP and is_too_wide) or (resize_mode == RESIZE_MODES.EXPAND and not is_too_wide):
        # determine the size by the height
        crop_size = ( int(source_image.size[1] * aspect_ratio), source_image.size[1] )
    else:
        # determine the size by the width
        crop_size = ( source_image.size[0], int(source_image.size[0] / aspect_ratio) )

    # determine the anchor point for the crop
    if anchor_horizontal == ANCHOR_HORIZONTAL.LEFT:
        x = 0
    elif anchor_horizontal == ANCHOR_HORIZONTAL.CENTER:
        x = int((source_image.size[0] - crop_size[0]) / 2)
    elif anchor_horizontal == ANCHOR_HORIZONTAL.RIGHT:
        x = source_image.size[0] - crop_size[0]

    if anchor_vertical == ANCHOR_VERTICAL.TOP:
        y = 0
    elif anchor_vertical == ANCHOR_VERTICAL.CENTER:
        y = int((source_image.size[1] - crop_size[1]) / 2)
    elif anchor_vertical == ANCHOR_VERTICAL.BOTTOM:
        y = source_image.size[1] - crop_size[1]

    if resize_mode == RESIZE_MODES.CROP:
        # perform the crop
        # NOTE: since each size can have a different aspect ratio,
        # we re-do this crop for each size; not only that, but the
        # thumbnail() method modifies the image in-place, so we
        # operate on a copy
        crop_box = ( x, y, x+crop_size[0], y+crop_size[1] )
        cropped_region = source_image.crop(crop_box)

    else:
        # perform the expand
        # Pillow doesn't have a native method for doing this that
        # allows us to expand different amounts on each axis so
        # we do it the hard way
        # NOTE: because of the way our anchors are calculated, the
        # offsets x,y will be negative when we are expanding rather
        # than cropping
        paste_box = ( -x, -y, -x+source_image.size[0], -y+source_image.size[1] )
        cropped_region = Image.new('RGB', crop_size, expand_color)
        cropped_region.paste(source_image, paste_box)

    # shrink the cropped/expanded image
    cropped_region.thumbnail(target_size, Image.ANTIALIAS)

    # done
    return cropped_region
