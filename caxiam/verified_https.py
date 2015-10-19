from django.conf import settings
from backports.ssl_match_hostname import match_hostname, CertificateError
import httplib
import socket
import ssl
import urllib2

# Python's urllib2 HTTPS implementation will wrap sockets in SSL but it
# won't, by default, validate the certificate sent by the server. While
# this raises the bar on an attacker to require them to do an active
# man-in-the-middle (MITM) attack in order to even read the data, it
# doesn't make such an attack impossible, and we know the NSA is more
# than happy to perform this kind of attack without a ton of oversight.
# Whatever the NSA can do, others can do too, so we want to validate
# that certificate.
#
# To use this module, import url_opener from it and use it instead of
# the bare urllib2 to actually open URLs.
#
# More information on the backports.ssl_match_hostname can be gleaned
# from there:
#
# http://stackoverflow.com/questions/1087227/validate-ssl-certificates-with-python
# 
class VerifiedHTTPSConnection(httplib.HTTPSConnection):
    def connect(self):
        # overrides the version in httplib so that we do
        #    certificate verification
        sock = socket.create_connection((self.host, self.port), self.timeout)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
        # wrap the socket using verification with the root
        # certs in trusted_root_certs
        # (raises exception on failure, including validation)
        self.sock = ssl.wrap_socket(
                sock,
                # if we actually had a client certificate, this would
                # be where we apply it
#                self.key_file,
#                self.cert_file,
                cert_reqs = ssl.CERT_REQUIRED,
                ca_certs = settings.CAXIAM_CACERTS_FILE,
                ssl_version = ssl.PROTOCOL_TLSv1,
            )
        # make sure the server's certificate matches the
        # hostname we thought we were connecting to
        # (raises exception on failure)
        match_hostname(self.sock.getpeercert(), self.host)

# wraps https connections with ssl certificate verification
class VerifiedHTTPSHandler(urllib2.HTTPSHandler):
    def __init__(self, connection_class = VerifiedHTTPSConnection):
        self.specialized_conn_class = connection_class
        urllib2.HTTPSHandler.__init__(self)
    def https_open(self, req):
        return self.do_open(self.specialized_conn_class, req)

# create an OpenerDirector that includes the new handler
https_handler = VerifiedHTTPSHandler()
url_opener = urllib2.build_opener(https_handler)
#url_opener = urllib2.build_opener()
