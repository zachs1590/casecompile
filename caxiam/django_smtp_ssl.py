# this code comes from the net, as part of an explanation of how to
# get SMTP working with Amazon (which requires SSL)... oddly enough
# our own SMTP providers also require SSL

import smtplib

from django.core.mail.utils import DNS_NAME
from django.core.mail.backends.smtp import EmailBackend

class SSLEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False
        try:
            self.connection = smtplib.SMTP_SSL(self.host, self.port,
                                               local_hostname = DNS_NAME.get_fqdn())
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except:
            if not self.fail_silently:
                raise