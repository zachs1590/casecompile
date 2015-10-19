#
# conversion functions
#

# because CSV files are often encoded with Latin-1
# which makes Python barf
def sanitize_latin_1(value, codec = 'iso-8859-1'):
    return value.decode(codec).encode('ascii', 'xmlcharrefreplace')
    
def to_integer(field):
    if field == '' or field == None:
        return None
    else:
        return int(field)

def to_decimal(field):
    if field == '' or field == None:
        return None
    else:
        return decimal.Decimal(field)

def to_string(field):
    # ensure a clean string
    field = field.strip()
    if field == '':
        return None
    else:
        return field.decode('iso-8859-1').encode('utf-8', 'replace')

def to_string_allow_empty(field):
    # ensure a clean string
    field = field.strip()
    return field.decode('iso-8859-1').encode('utf-8', 'replace')

def to_boolean(field):
    # ensure a truthy value
    if field.upper() == 'Y' or field == "1":
        # modified this to accept integer booleans 
        # (1 is True, 0 is False) for the customer export
        return True
    elif field.upper() == 'N' or field == "0" or field == ' ' or field == '':
        # we are bending a little to accept a space as False
        return False
    else: 
        raise Exception('invalid truthy value for boolean field')

def to_date(field):
    pass

# apply cleaner functions to data
# assumes you have a row (dict) of data and a list of headings and
# cleaner functions for those fields
def clean_row_data(headings_and_types, row):
    for k,func in headings_and_types:
        # we don't need to iteritems() since we have a list of
        # tuples already
        try:
            row[k] = func(row[k])
        except:
            print '**** failed to clean data for field %s' % k
            raise
            
    return row

