from django.conf import settings
from django.db import connection
import datetime

# debugging middleware which is extremely useful
#
# settings:
#
#   CAXIAM_DUMP_SQL     whether to dump data on all SQL queries made during a request, as well as request timing

class CaxiamDebugMiddleware(object):

    date_request_started = None

    def process_request(self, request):
        self.date_request_started = datetime.datetime.utcnow()

    def process_response(self, request, response):
        if settings.CAXIAM_DUMP_SQL or settings.CAXIAM_DUMP_SESSION or settings.CAXIAM_DUMP_REQUESTS:
            if self.date_request_started != None:
                elapsed_time = (datetime.datetime.utcnow() - self.date_request_started).total_seconds()
                print '==== REQUEST TIME: %s %.3fs %s' % (request.method, elapsed_time, request.META['RAW_URI'])

        if settings.CAXIAM_DUMP_SQL:
            print '==== SQL QUERIES ===='
            for i in range(len(connection.queries)):
                q = connection.queries[i]

                print '%4d %8s %s' % (i+1, q['time'], q['sql'])
                print '--------'

            print '====================='

        if settings.CAXIAM_DUMP_SESSION:
            import json
            print '==== SESSION ========'
            print json.dumps(request.session._session)
            print '====================='

        return response
