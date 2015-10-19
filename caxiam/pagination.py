from django.conf import settings

import math


# convert to an int, with a default if it's invalid
def safe_int(value, default):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

#Filter Mixin
#This is used as a mixin to a View so that it is easy to build out pagination and a filter for the pagination.
#When you include this mixin you get session management for your pagination immediately.
class FilterMixin(object):
    #Set as a property so that you can override it from the urls.py.
    #This way you can actually share pagination keys throughout different views.
    #consider you have a list view that is using the filter and pagination
    #and also if you have a filter form view that limits which things are shown on the list view
    #you can set up filter_name from urls.py with the same key between them and they will share a filter
    filter_name = ''

    def __init__(self, *args, **kwargs):
        super(FilterMixin, self).__init__(*args, **kwargs)
        self.FILTER_SESSION_KEY = self.filter_name+'_filter'
        self.FILTER_PAGE_KEY = self.filter_name+'_'+settings.PAGINATION_URL_PAGE_KEY_DEFAULT
        self.FILTER_DATA_KEY = self.filter_name+'_data'

    #pull the data from request.session
    def _filter_get_filter(self, request):
        if not self.FILTER_SESSION_KEY in request.session:
            request.session[self.FILTER_SESSION_KEY] = {}
        return request.session[self.FILTER_SESSION_KEY]

    #set one value onto the request.session
    def _filter_set_key(self, request, key, value):
        my_filter = self._filter_get_filter(request)
        my_filter[key] = value
        request.session[self.FILTER_SESSION_KEY] = my_filter
        return my_filter

    #if the value exists in the filter
    def _filter_has_key(self, request, key):
        my_filter = self._filter_get_filter(request)
        return key in my_filter

    #Use this on the page that your pagination is accepting the page key value.
    def filter_set_page(self, request):
        if self.FILTER_PAGE_KEY in request.POST:
            self._filter_set_key(request, self.FILTER_PAGE_KEY, request.POST[self.FILTER_PAGE_KEY])
        elif self.FILTER_PAGE_KEY in request.GET:
            self._filter_set_key(request, self.FILTER_PAGE_KEY, request.GET[self.FILTER_PAGE_KEY])


#Pagination
#Intended to be a drop in replacement for our pagination struct objects.
class Pagination(object):

    paginate_by = settings.PAGINATION_PAGINATE_BY_DEFAULT
    url_page_key = settings.PAGINATION_URL_PAGE_KEY_DEFAULT
    show_page_number_amount = settings.PAGINATION_SHOW_PAGE_NUMBER_AMOUNT_DEFAULT #Represents the total amount of numbers that should be shown

    queryset = None
    count = 0
    pages = 0
    current = 1
    offset = 0
    previous = None
    next = None
    is_paginated = False

    low_page_display = None
    high_page_display = None

    #Expects a prefiltered queryset
    def __init__(self, request, queryset, *args, **kwargs):
        if 'paginate_by' in kwargs:
            self.paginate_by = kwargs['paginate_by']
        if 'url_page_key' in kwargs:
            self.url_page_key = kwargs['url_page_key']
        if 'show_page_number_amount' in kwargs:
            self.show_page_number_amount = kwargs['show_page_number_amount']
        if self.paginate_by == 0:
            self.paginate_by = 1
        if 'current_page' in kwargs:
            current_page = kwargs['current_page']
        else:
            current_page = safe_int(request.REQUEST.get(self.url_page_key))

        self.queryset = queryset.filter()

        if 'count' in kwargs:
            self.count = kwargs['count']
        else:
            self.count = queryset.count()

        self.pages = int((self.count + self.paginate_by-1) / self.paginate_by)
        self.current = min(max(safe_int(current_page, 1), 1), self.pages)
        self.offset = max((self.current-1) * self.paginate_by, 0)
        self.previous = (self.current - 1) if self.current > 1 else None
        self.next = (self.current + 1) if self.current < self.pages else None
        self.is_paginated = (self.pages > 1)

        #This entire block is what calculates the values for page_numbers
        #Just believe me when i tell you this is correct because it's extremely confusing to explain
        if self.is_paginated and self.show_page_number_amount > 0:
            low_display_half = math.floor((self.show_page_number_amount-1)/2.0) #splitting the difference between upper bound and lower bound. lower should have less if an odd number
            high_display_half = math.ceil((self.show_page_number_amount-1)/2.0) #splitting the difference between upper bound and lower bound. higher should have more if an odd number
            self.low_page_display = max(self.current - low_display_half,1) #sets the lower bound by current page minus lower half, but if less than 1, the lower value must be 1
            low_difference = low_display_half - (self.current - self.low_page_display) #in a situation where you are low in the list you want the difference to be added into your high side.
            self.high_page_display = int(min(self.current + high_display_half + low_difference, self.pages)) #sets the higher bound, but if more than pages, the lower value must be pages
            high_difference = max(high_display_half - (self.high_page_display - self.current), 0) #in a situation where you are high in the list you want the difference to be added into your low side.
            self.low_page_display = int(max(self.low_page_display - high_difference,1)) #resets the low page display to take into account the high difference if necessary


    @property
    def items(self):
        return self.queryset[ self.offset : self.offset + self.paginate_by ]

    @property
    def page_numbers(self):
        return xrange(self.low_page_display, self.high_page_display+1)



