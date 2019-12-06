import hashlib


def hash_id(salt, text):
    text = ((salt or '') + (text or '')).encode()
    sha = hashlib.sha3_512(text)
    return sha.hexdigest()[:24]


def get_obj(clss, **kwargs):
    '''
    Get an object from the database

    Return None if not found, the object if found one, raise error if found more than one
    '''
    try:
        obj = clss.objects.get(**kwargs)
    except clss.DoesNotExist:
        obj = None

    return obj
