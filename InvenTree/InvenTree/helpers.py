"""
Provides helper functions used throughout the InvenTree project
"""

import io
import re
import json
import os.path
from PIL import Image

from decimal import Decimal, InvalidOperation

from wsgiref.util import FileWrapper
from django.http import StreamingHttpResponse
from django.core.exceptions import ValidationError, FieldError
from django.utils.translation import ugettext_lazy as _

from django.contrib.auth.models import Permission

import InvenTree.version

from common.models import InvenTreeSetting
from .settings import MEDIA_URL, STATIC_URL
from common.settings import currency_code_default

from djmoney.money import Money


def getSetting(key, backup_value=None):
    """
    Shortcut for reading a setting value from the database
    """

    return InvenTreeSetting.get_setting(key, backup_value=backup_value)


def generateTestKey(test_name):
    """
    Generate a test 'key' for a given test name.
    This must not have illegal chars as it will be used for dict lookup in a template.

    Tests must be named such that they will have unique keys.
    """

    key = test_name.strip().lower()
    key = key.replace(" ", "")

    # Remove any characters that cannot be used to represent a variable
    key = re.sub(r'[^a-zA-Z0-9]', '', key)

    return key


def getMediaUrl(filename):
    """
    Return the qualified access path for the given file,
    under the media directory.
    """

    return os.path.join(MEDIA_URL, str(filename))


def getStaticUrl(filename):
    """
    Return the qualified access path for the given file,
    under the static media directory.
    """

    return os.path.join(STATIC_URL, str(filename))


def construct_absolute_url(*arg):
    """
    Construct (or attempt to construct) an absolute URL from a relative URL.

    This is useful when (for example) sending an email to a user with a link
    to something in the InvenTree web framework.

    This requires the BASE_URL configuration option to be set!
    """

    base = str(InvenTreeSetting.get_setting('INVENTREE_BASE_URL'))

    url = '/'.join(arg)

    if not base:
        return url

    # Strip trailing slash from base url
    if base.endswith('/'):
        base = base[:-1]

    if url.startswith('/'):
        url = url[1:]

    url = f"{base}/{url}"

    return url


def getBlankImage():
    """
    Return the qualified path for the 'blank image' placeholder.
    """

    return getStaticUrl("img/blank_image.png")


def getBlankThumbnail():
    """
    Return the qualified path for the 'blank image' thumbnail placeholder.
    """

    return getStaticUrl("img/blank_image.thumbnail.png")


def TestIfImage(img):
    """ Test if an image file is indeed an image """
    try:
        Image.open(img).verify()
        return True
    except:
        return False


def TestIfImageURL(url):
    """ Test if an image URL (or filename) looks like a valid image format.

    Simply tests the extension against a set of allowed values
    """
    return os.path.splitext(os.path.basename(url))[-1].lower() in [
        '.jpg', '.jpeg',
        '.png', '.bmp',
        '.tif', '.tiff',
        '.webp', '.gif',
    ]


def str2bool(text, test=True):
    """ Test if a string 'looks' like a boolean value.

    Args:
        text: Input text
        test (default = True): Set which boolean value to look for

    Returns:
        True if the text looks like the selected boolean value
    """
    if test:
        return str(text).lower() in ['1', 'y', 'yes', 't', 'true', 'ok', 'on', ]
    else:
        return str(text).lower() in ['0', 'n', 'no', 'none', 'f', 'false', 'off', ]


def is_bool(text):
    """
    Determine if a string value 'looks' like a boolean.
    """

    if str2bool(text, True):
        return True
    elif str2bool(text, False):
        return True
    else:
        return False


def isNull(text):
    """
    Test if a string 'looks' like a null value.
    This is useful for querying the API against a null key.

    Args:
        text: Input text

    Returns:
        True if the text looks like a null value
    """

    return str(text).strip().lower() in ['top', 'null', 'none', 'empty', 'false', '-1', '']


def normalize(d):
    """
    Normalize a decimal number, and remove exponential formatting.
    """

    if type(d) is not Decimal:
        d = Decimal(d)

    d = d.normalize()

    # Ref: https://docs.python.org/3/library/decimal.html
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()


def increment(n):
    """
    Attempt to increment an integer (or a string that looks like an integer!)

    e.g.

    001 -> 002
    2 -> 3
    AB01 -> AB02
    QQQ -> QQQ

    """

    value = str(n).strip()

    # Ignore empty strings
    if not value:
        return value

    pattern = r"(.*?)(\d+)?$"

    result = re.search(pattern, value)

    # No match!
    if result is None:
        return value

    groups = result.groups()

    # If we cannot match the regex, then simply return the provided value
    if not len(groups) == 2:
        return value

    prefix, number = groups

    # No number extracted? Simply return the prefix (without incrementing!)
    if not number:
        return prefix

    # Record the width of the number
    width = len(number)

    try:
        number = int(number) + 1
        number = str(number)
    except ValueError:
        pass

    number = number.zfill(width)

    return prefix + number


def decimal2string(d):
    """
    Format a Decimal number as a string,
    stripping out any trailing zeroes or decimal points.
    Essentially make it look like a whole number if it is one.

    Args:
        d: A python Decimal object

    Returns:
        A string representation of the input number
    """

    if type(d) is Decimal:
        d = normalize(d)

    try:
        # Ensure that the provided string can actually be converted to a float
        float(d)
    except ValueError:
        # Not a number
        return str(d)

    s = str(d)

    # Return entire number if there is no decimal place
    if '.' not in s:
        return s

    return s.rstrip("0").rstrip(".")


def decimal2money(d, currency=None):
    """
    Format a Decimal number as Money

    Args:
        d: A python Decimal object
        currency: Currency of the input amount, defaults to default currency in settings

    Returns:
        A Money object from the input(s)
    """
    if not currency:
        currency = currency_code_default()
    return Money(d, currency)


def WrapWithQuotes(text, quote='"'):
    """ Wrap the supplied text with quotes

    Args:
        text: Input text to wrap
        quote: Quote character to use for wrapping (default = "")

    Returns:
        Supplied text wrapped in quote char
    """

    if not text.startswith(quote):
        text = quote + text

    if not text.endswith(quote):
        text = text + quote

    return text


def MakeBarcode(object_name, object_pk, object_data=None, **kwargs):
    """ Generate a string for a barcode. Adds some global InvenTree parameters.

    Args:
        object_type: string describing the object type e.g. 'StockItem'
        object_id: ID (Primary Key) of the object in the database
        object_url: url for JSON API detail view of the object
        data: Python dict object containing extra datawhich will be rendered to string (must only contain stringable values)

    Returns:
        json string of the supplied data plus some other data
    """
    if object_data is None:
        object_data = {}

    url = kwargs.get('url', False)
    brief = kwargs.get('brief', True)

    data = {}

    if url:
        request = object_data.get('request', None)
        item_url = object_data.get('item_url', None)
        absolute_url = None

        if request and item_url:
            absolute_url = request.build_absolute_uri(item_url)
            # Return URL (No JSON)
            return absolute_url

        if item_url:
            # Return URL (No JSON)
            return item_url
    elif brief:
        data[object_name] = object_pk
    else:
        data['tool'] = 'InvenTree'
        data['version'] = InvenTree.version.inventreeVersion()
        data['instance'] = InvenTree.version.inventreeInstanceName()

        # Ensure PK is included
        object_data['id'] = object_pk
        data[object_name] = object_data

    return json.dumps(data, sort_keys=True)


def GetExportFormats():
    """ Return a list of allowable file formats for exporting data """

    return [
        'csv',
        'tsv',
        'xls',
        'xlsx',
        'json',
        'yaml',
    ]


def DownloadFile(data, filename, content_type='application/text', inline=False):
    """
    Create a dynamic file for the user to download.

    Args:
        data: Raw file data (string or bytes)
        filename: Filename for the file download
        content_type: Content type for the download
        inline: Download "inline" or as attachment? (Default = attachment)

    Return:
        A StreamingHttpResponse object wrapping the supplied data
    """

    filename = WrapWithQuotes(filename)

    if type(data) == str:
        wrapper = FileWrapper(io.StringIO(data))
    else:
        wrapper = FileWrapper(io.BytesIO(data))

    response = StreamingHttpResponse(wrapper, content_type=content_type)
    response['Content-Length'] = len(data)

    disposition = "inline" if inline else "attachment"

    response['Content-Disposition'] = f'{disposition}; filename={filename}'

    return response


def extract_serial_numbers(serials, expected_quantity, next_number: int):
    """
    Attempt to extract serial numbers from an input string:

    Requirements:
        - Serial numbers can be either strings, or integers
        - Serial numbers can be split by whitespace / newline / commma chars
        - Serial numbers can be supplied as an inclusive range using hyphen char e.g. 10-20
        - Serial numbers can be defined as ~ for getting the next available serial number
        - Serial numbers can be supplied as <start>+ for getting all expecteded numbers starting from <start>
        - Serial numbers can be supplied as <start>+<length> for getting <length> numbers starting from <start>

    Args:
        serials: input string with patterns
        expected_quantity: The number of (unique) serial numbers we expect
        next_number(int): the next possible serial number
    """

    serials = serials.strip()

    # fill in the next serial number into the serial
    while '~' in serials:
        serials = serials.replace('~', str(next_number), 1)
        next_number += 1

    # Split input string by whitespace or comma (,) characters
    groups = re.split("[\s,]+", serials)

    numbers = []
    errors = []

    # Helper function to check for duplicated numbers
    def add_sn(sn):
        # Attempt integer conversion first, so numerical strings are never stored
        try:
            sn = int(sn)
        except ValueError:
            pass

        if sn in numbers:
            errors.append(_('Duplicate serial: {sn}').format(sn=sn))
        else:
            numbers.append(sn)

    try:
        expected_quantity = int(expected_quantity)
    except ValueError:
        raise ValidationError([_("Invalid quantity provided")])

    if len(serials) == 0:
        raise ValidationError([_("Empty serial number string")])

    # If the user has supplied the correct number of serials, don't process them for groups
    # just add them so any duplicates (or future validations) are checked
    if len(groups) == expected_quantity:
        for group in groups:
            add_sn(group)

        if len(errors) > 0:
            raise ValidationError(errors)

        return numbers

    for group in groups:
        group = group.strip()

        # Hyphen indicates a range of numbers
        if '-' in group:
            items = group.split('-')

            if len(items) == 2 and all([i.isnumeric() for i in items]):
                a = items[0].strip()
                b = items[1].strip()

                try:
                    a = int(a)
                    b = int(b)

                    if a < b:
                        for n in range(a, b + 1):
                            add_sn(n)
                    else:
                        errors.append(_("Invalid group range: {g}").format(g=group))

                except ValueError:
                    errors.append(_("Invalid group: {g}").format(g=group))
                    continue
            else:
                # More than 2 hyphens or non-numeric group so add without interpolating
                add_sn(group)

        # plus signals either
        # 1:  'start+':  expected number of serials, starting at start
        # 2:  'start+number': number of serials, starting at start
        elif '+' in group:
            items = group.split('+')

            # case 1, 2
            if len(items) == 2:
                start = int(items[0])

                # case 2
                if bool(items[1]):
                    end = start + int(items[1]) + 1

                # case 1
                else:
                    end = start + (expected_quantity - len(numbers))

                for n in range(start, end):
                    add_sn(n)
            # no case
            else:
                errors.append(_("Invalid group sequence: {g}").format(g=group))

        # At this point, we assume that the "group" is just a single serial value
        elif group:
            add_sn(group)

        # No valid input group detected
        else:
            raise ValidationError(_(f"Invalid/no group {group}"))

    if len(errors) > 0:
        raise ValidationError(errors)

    if len(numbers) == 0:
        raise ValidationError([_("No serial numbers found")])

    # The number of extracted serial numbers must match the expected quantity
    if not expected_quantity == len(numbers):
        raise ValidationError([_("Number of unique serial number ({s}) must match quantity ({q})").format(s=len(numbers), q=expected_quantity)])

    return numbers


def validateFilterString(value, model=None):
    """
    Validate that a provided filter string looks like a list of comma-separated key=value pairs

    These should nominally match to a valid database filter based on the model being filtered.

    e.g. "category=6, IPN=12"
    e.g. "part__name=widget"

    The ReportTemplate class uses the filter string to work out which items a given report applies to.
    For example, an acceptance test report template might only apply to stock items with a given IPN,
    so the string could be set to:

    filters = "IPN = ACME0001"

    Returns a map of key:value pairs
    """

    # Empty results map
    results = {}

    value = str(value).strip()

    if not value or len(value) == 0:
        return results

    groups = value.split(',')

    for group in groups:
        group = group.strip()

        pair = group.split('=')

        if not len(pair) == 2:
            raise ValidationError(
                "Invalid group: {g}".format(g=group)
            )

        k, v = pair

        k = k.strip()
        v = v.strip()

        if not k or not v:
            raise ValidationError(
                "Invalid group: {g}".format(g=group)
            )

        results[k] = v

    # If a model is provided, verify that the provided filters can be used against it
    if model is not None:
        try:
            model.objects.filter(**results)
        except FieldError as e:
            raise ValidationError(
                str(e),
            )

    return results


def addUserPermission(user, permission):
    """
    Shortcut function for adding a certain permission to a user.
    """

    perm = Permission.objects.get(codename=permission)
    user.user_permissions.add(perm)


def addUserPermissions(user, permissions):
    """
    Shortcut function for adding multiple permissions to a user.
    """

    for permission in permissions:
        addUserPermission(user, permission)


def getMigrationFileNames(app):
    """
    Return a list of all migration filenames for provided app
    """

    local_dir = os.path.dirname(os.path.abspath(__file__))

    migration_dir = os.path.join(local_dir, '..', app, 'migrations')

    files = os.listdir(migration_dir)

    # Regex pattern for migration files
    pattern = r"^[\d]+_.*\.py$"

    migration_files = []

    for f in files:
        if re.match(pattern, f):
            migration_files.append(f)

    return migration_files


def getOldestMigrationFile(app, exclude_extension=True, ignore_initial=True):
    """
    Return the filename associated with the oldest migration
    """

    oldest_num = -1
    oldest_file = None

    for f in getMigrationFileNames(app):

        if ignore_initial and f.startswith('0001_initial'):
            continue

        num = int(f.split('_')[0])

        if oldest_file is None or num < oldest_num:
            oldest_num = num
            oldest_file = f

    if exclude_extension:
        oldest_file = oldest_file.replace('.py', '')

    return oldest_file


def getNewestMigrationFile(app, exclude_extension=True):
    """
    Return the filename associated with the newest migration
    """

    newest_file = None
    newest_num = -1

    for f in getMigrationFileNames(app):
        num = int(f.split('_')[0])

        if newest_file is None or num > newest_num:
            newest_num = num
            newest_file = f

    if exclude_extension:
        newest_file = newest_file.replace('.py', '')

    return newest_file


def clean_decimal(number):
    """ Clean-up decimal value """

    # Check if empty
    if number is None or number == '' or number == 0:
        return Decimal(0)

    # Convert to string and remove spaces
    number = str(number).replace(' ', '')

    # Guess what type of decimal and thousands separators are used
    count_comma = number.count(',')
    count_point = number.count('.')

    if count_comma == 1:
        # Comma is used as decimal separator
        if count_point > 0:
            # Points are used as thousands separators: remove them
            number = number.replace('.', '')
        # Replace decimal separator with point
        number = number.replace(',', '.')
    elif count_point == 1:
        # Point is used as decimal separator
        if count_comma > 0:
            # Commas are used as thousands separators: remove them
            number = number.replace(',', '')

    # Convert to Decimal type
    try:
        clean_number = Decimal(number)
    except InvalidOperation:
        # Number cannot be converted to Decimal (eg. a string containing letters)
        return Decimal(0)

    return clean_number.quantize(Decimal(1)) if clean_number == clean_number.to_integral() else clean_number.normalize()


def get_objectreference(obj, type_ref: str = 'content_type', object_ref: str = 'object_id'):
    """lookup method for the GenericForeignKey fields

    Attributes:
    - obj: object that will be resolved
    - type_ref: field name for the contenttype field in the model
    - object_ref: field name for the object id in the model

    Example implementation in the serializer:
    ```
    target = serializers.SerializerMethodField()
    def get_target(self, obj):
        return get_objectreference(obj, 'target_content_type', 'target_object_id')
    ```

    The method name must always be the name of the field prefixed by 'get_'
    """
    model_cls = getattr(obj, type_ref)
    obj_id = getattr(obj, object_ref)

    # check if references are set -> return nothing if not
    if model_cls is None or obj_id is None:
        return None

    # resolve referenced data into objects
    model_cls = model_cls.model_class()
    item = model_cls.objects.get(id=obj_id)
    url_fnc = getattr(item, 'get_absolute_url', None)

    # create output
    ret = {}
    if url_fnc:
        ret['link'] = url_fnc()
    return {
        'name': str(item),
        'model': str(model_cls._meta.verbose_name),
        **ret
    }


def inheritors(cls):
    """
    Return all classes that are subclasses from the supplied cls
    """
    subcls = set()
    work = [cls]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subcls:
                subcls.add(child)
                work.append(child)
    return subcls
