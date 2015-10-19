import base64
import hashlib
import hmac
import numbers

# Create a Hash given a list of items
class ModelHashGenerator(object):

    @classmethod
    def generate_hash(klass, cls, hashkey, *args):       
        counter = 0
        while True:
            counter += 1
            encoded_hash = klass.generate_hash_core(counter, hashkey, *args)
            if encoded_hash[0] in '-_':
                # we don't want user hashes that start with these
                continue
            if cls.objects.filter(hash = encoded_hash).count() > 0:
                # this hash is already in use
                continue
                
            # otherwise the hash is acceptable
            return encoded_hash

    @classmethod
    def generate_hash_core(cls, counter, hashkey, *args):
        raw_hash = hmac.new(hashkey, repr(args) + str(counter), hashlib.sha256).digest()
        encoded_hash = base64.urlsafe_b64encode(raw_hash)[:43]  # strips always-present trailing =
        return encoded_hash
        