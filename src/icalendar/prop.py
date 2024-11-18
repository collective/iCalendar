"""This module contains the parser/generators (or coders/encoders if you
prefer) for the classes/datatypes that are used in iCalendar:

###########################################################################

# This module defines these property value data types and property parameters

4.2 Defined property parameters are:

     ALTREP, CN, CUTYPE, DELEGATED-FROM, DELEGATED-TO, DIR, ENCODING, FMTTYPE,
     FBTYPE, LANGUAGE, MEMBER, PARTSTAT, RANGE, RELATED, RELTYPE, ROLE, RSVP,
     SENT-BY, TZID, VALUE

4.3 Defined value data types are:

    BINARY, BOOLEAN, CAL-ADDRESS, DATE, DATE-TIME, DURATION, FLOAT, INTEGER,
    PERIOD, RECUR, TEXT, TIME, URI, UTC-OFFSET

###########################################################################

iCalendar properties have values. The values are strongly typed. This module
defines these types, calling val.to_ical() on them will render them as defined
in rfc5545.

If you pass any of these classes a Python primitive, you will have an object
that can render itself as iCalendar formatted date.

Property Value Data Types start with a 'v'. they all have an to_ical() and
from_ical() method. The to_ical() method generates a text string in the
iCalendar format. The from_ical() method can parse this format and return a
primitive Python datatype. So it should always be true that:

    x == vDataType.from_ical(VDataType(x).to_ical())

These types are mainly used for parsing and file generation. But you can set
them directly.
"""
import base64
import binascii
import re
import time as _time
from datetime import date, datetime, time, timedelta, tzinfo
from enum import Enum, auto
from typing import Optional, Union

from icalendar.caselessdict import CaselessDict
from icalendar.parser import Parameters, escape_char, unescape_char
from icalendar.parser_tools import (
    DEFAULT_ENCODING,
    ICAL_TYPE,
    SEQUENCE_TYPES,
    from_unicode,
    to_unicode,
)

from . import timezone as _timezone

DURATION_REGEX = re.compile(r'([-+]?)P(?:(\d+)W)?(?:(\d+)D)?'
                            r'(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$')

WEEKDAY_RULE = re.compile(r'(?P<signal>[+-]?)(?P<relative>[\d]{0,2})'
                          r'(?P<weekday>[\w]{2})$')


def tzid_from_dt(dt: datetime) -> Optional[str]:
    """Retrieve the timezone id from the datetime object."""
    tzid = None
    if hasattr(dt.tzinfo, 'zone'):
        tzid = dt.tzinfo.zone  # pytz implementation
    elif hasattr(dt.tzinfo, 'key'):
        tzid = dt.tzinfo.key  # ZoneInfo implementation
    elif hasattr(dt.tzinfo, 'tzname'):
        # dateutil implementation, but this is broken
        # See https://github.com/collective/icalendar/issues/333 for details
        tzid = dt.tzinfo.tzname(dt)
    return tzid


class vBinary:
    """Binary property values are base 64 encoded.
    """

    def __init__(self, obj):
        self.obj = to_unicode(obj)
        self.params = Parameters(encoding='BASE64', value="BINARY")

    def __repr__(self):
        return f"vBinary({self.to_ical()})"

    def to_ical(self):
        return binascii.b2a_base64(self.obj.encode('utf-8'))[:-1]

    @staticmethod
    def from_ical(ical):
        try:
            return base64.b64decode(ical)
        except (ValueError, UnicodeError):
            raise ValueError('Not valid base 64 encoding.')

    def __eq__(self, other):
        """self == other"""
        return isinstance(other, vBinary) and self.obj == other.obj


class vBoolean(int):
    """Boolean
    Value Name:  BOOLEAN

    Purpose:  This value type is used to identify properties that contain
      either a "TRUE" or "FALSE" Boolean value.

    Format Definition:  This value type is defined by the following
      notation:

       boolean    = "TRUE" / "FALSE"

    Description:  These values are case-insensitive text.  No additional
      content value encoding is defined for this value type.

    Example:  The following is an example of a hypothetical property that
      has a BOOLEAN value type:

        TRUE
        
        >>> from icalendar.prop import vBoolean
        >>> boolean = vBoolean.from_ical('TRUE')
        >>> boolean
        True
        >>> boolean = vBoolean.from_ical('FALSE')
        >>> boolean
        False
        >>> boolean = vBoolean.from_ical('True')
        >>> boolean
        True

            
    """
    
    BOOL_MAP = CaselessDict({'true': True, 'false': False})

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls, *args, **kwargs)
        self.params = Parameters()
        return self

    def to_ical(self):
        return b'TRUE' if self else b'FALSE'

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls.BOOL_MAP[ical]
        except Exception:
            raise ValueError(f"Expected 'TRUE' or 'FALSE'. Got {ical}")


class vText(str):
    """Simple text.
    """

    def __new__(cls, value, encoding=DEFAULT_ENCODING):
        value = to_unicode(value, encoding=encoding)
        self = super().__new__(cls, value)
        self.encoding = encoding
        self.params = Parameters()
        return self

    def __repr__(self) -> str:
        return f"vText({self.to_ical()!r})"

    def to_ical(self) -> bytes:
        return escape_char(self).encode(self.encoding)

    @classmethod
    def from_ical(cls, ical:ICAL_TYPE):
        ical_unesc = unescape_char(ical)
        return cls(ical_unesc)


class vCalAddress(str):
    """Calendar User Address
    Value Name:  CAL-ADDRESS

    Purpose:  This value type is used to identify properties that contain
      a calendar user address.

    Format Definition:  This value type is defined by the following
      notation:

       cal-address        = uri

    Description:  The value is a URI as defined by [RFC3986] or any other
      IANA-registered form for a URI.  When used to address an Internet 
      email transport address for a calendar user, the value MUST be a
      mailto URI, as defined by [RFC2368].
      
    Example:

        mailto:jane_doe@example.com 
        
        >>> from icalendar.prop import vCalAddress
        >>> cal_address = vCalAddress.from_ical('mailto:jane_doe@example.com')
        >>> cal_address
        vCalAddress('mailto:jane_doe@example.com')

      
    """

    def __new__(cls, value, encoding=DEFAULT_ENCODING):
        value = to_unicode(value, encoding=encoding)
        self = super().__new__(cls, value)
        self.params = Parameters()
        return self

    def __repr__(self):
        return f"vCalAddress('{self}')"

    def to_ical(self):
        return self.encode(DEFAULT_ENCODING)

    @classmethod
    def from_ical(cls, ical):
        return cls(ical)


class vFloat(float):
    """Float
    Value Name:  FLOAT

    Purpose:  This value type is used to identify properties that contain
      a real-number value.

    Format Definition:  This value type is defined by the following
      notation:

       float      = (["+"] / "-") 1*DIGIT ["." 1*DIGIT]

    Description:  If the property permits, multiple "float" values are
      specified by a COMMA-separated list of values.

    Example:

        1000000.0000001
        1.333
        -3.14
        
        >>> from icalendar.prop import vFloat
        >>> float = vFloat.from_ical('1000000.0000001')
        >>> float
        1000000.0000001
        >>> float = vFloat.from_ical('1.333')
        >>> float
        1.333
        >>> float = vFloat.from_ical('+1.333')
        >>> float
        1.333
        >>> float = vFloat.from_ical('-3.14')
        >>> float
        -3.14

    """

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls, *args, **kwargs)
        self.params = Parameters()
        return self

    def to_ical(self):
        return str(self).encode('utf-8')

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(ical)
        except Exception:
            raise ValueError(f'Expected float value, got: {ical}')


class vInt(int):
    """Integer
    Value Name:  INTEGER

    Purpose:  This value type is used to identify properties that contain
      a signed integer value.

    Format Definition:  This value type is defined by the following
      notation:

       integer    = (["+"] / "-") 1*DIGIT

    Description:  If the property permits, multiple "integer" values are
      specified by a COMMA-separated list of values.  The valid range
      for "integer" is -2147483648 to 2147483647.  If the sign is not
      specified, then the value is assumed to be positive.

    Example:

        1234567890
        -1234567890
        +1234567890
        432109876
        
        >>> from icalendar.prop import vInt
        >>> integer = vInt.from_ical('1234567890')
        >>> integer
        1234567890
        >>> integer = vInt.from_ical('-1234567890')
        >>> integer
        -1234567890
        >>> integer = vInt.from_ical('+1234567890')
        >>> integer
        1234567890
        >>> integer = vInt.from_ical('432109876')
        >>> integer
        432109876
        
    """

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls, *args, **kwargs)
        self.params = Parameters()
        return self

    def to_ical(self) -> bytes:
        return str(self).encode('utf-8')

    @classmethod
    def from_ical(cls, ical:ICAL_TYPE):
        try:
            return cls(ical)
        except Exception:
            raise ValueError(f'Expected int, got: {ical}')


class vDDDLists:
    """A list of vDDDTypes values.
    """

    def __init__(self, dt_list):
        if not hasattr(dt_list, '__iter__'):
            dt_list = [dt_list]
        vDDD = []
        tzid = None
        for dt in dt_list:
            dt = vDDDTypes(dt)
            vDDD.append(dt)
            if 'TZID' in dt.params:
                tzid = dt.params['TZID']

        if tzid:
            # NOTE: no support for multiple timezones here!
            self.params = Parameters({'TZID': tzid})
        self.dts = vDDD

    def to_ical(self):
        dts_ical = (from_unicode(dt.to_ical()) for dt in self.dts)
        return b",".join(dts_ical)

    @staticmethod
    def from_ical(ical, timezone=None):
        out = []
        ical_dates = ical.split(",")
        for ical_dt in ical_dates:
            out.append(vDDDTypes.from_ical(ical_dt, timezone=timezone))
        return out

    def __eq__(self, other):
        if not isinstance(other, vDDDLists):
            return False
        return self.dts == other.dts


class vCategory:

    def __init__(self, c_list):
        if not hasattr(c_list, '__iter__') or isinstance(c_list, str):
            c_list = [c_list]
        self.cats = [vText(c) for c in c_list]
        self.params = Parameters()

    def __iter__(self):
        return iter(vCategory.from_ical(self.to_ical()))

    def to_ical(self):
        return b",".join([c.to_ical() for c in self.cats])

    @staticmethod
    def from_ical(ical):
        ical = to_unicode(ical)
        out = unescape_char(ical).split(',')
        return out

    def __eq__(self, other):
        """self == other"""
        return isinstance(other, vCategory) and self.cats == other.cats


class TimeBase:
    """Make classes with a datetime/date comparable."""

    def __eq__(self, other):
        """self == other"""
        if isinstance(other, TimeBase):
            return self.params == other.params and self.dt == other.dt
        return False

    def __hash__(self):
        return hash(self.dt)


class vDDDTypes(TimeBase):
    """A combined Datetime, Date or Duration parser/generator. Their format
    cannot be confused, and often values can be of either types.
    So this is practical.
    """

    def __init__(self, dt):
        if not isinstance(dt, (datetime, date, timedelta, time, tuple)):
            raise ValueError('You must use datetime, date, timedelta, '
                             'time or tuple (for periods)')
        if isinstance(dt, (datetime, timedelta)):
            self.params = Parameters()
        elif isinstance(dt, date):
            self.params = Parameters({'value': 'DATE'})
        elif isinstance(dt, time):
            self.params = Parameters({'value': 'TIME'})
        elif isinstance(dt, tuple):
            self.params = Parameters({'value': 'PERIOD'})

        tzid = tzid_from_dt(dt) if isinstance(dt, (datetime, time)) else None
        if tzid is not None and tzid != 'UTC':
            self.params.update({'TZID': tzid})

        self.dt = dt

    def to_ical(self):
        dt = self.dt
        if isinstance(dt, datetime):
            return vDatetime(dt).to_ical()
        elif isinstance(dt, date):
            return vDate(dt).to_ical()
        elif isinstance(dt, timedelta):
            return vDuration(dt).to_ical()
        elif isinstance(dt, time):
            return vTime(dt).to_ical()
        elif isinstance(dt, tuple) and len(dt) == 2:
            return vPeriod(dt).to_ical()
        else:
            raise ValueError(f'Unknown date type: {type(dt)}')

    @classmethod
    def from_ical(cls, ical, timezone=None):
        if isinstance(ical, cls):
            return ical.dt
        u = ical.upper()
        if u.startswith(('P', '-P', '+P')):
            return vDuration.from_ical(ical)
        if '/' in u:
            return vPeriod.from_ical(ical, timezone=timezone)

        if len(ical) in (15, 16):
            return vDatetime.from_ical(ical, timezone=timezone)
        elif len(ical) == 8:
            return vDate.from_ical(ical)
        elif len(ical) in (6, 7):
            return vTime.from_ical(ical)
        else:
            raise ValueError(
                f"Expected datetime, date, or time, got: '{ical}'"
            )

    def __repr__(self):
        """repr(self)"""
        return f"{self.__class__.__name__}({self.dt}, {self.params})"


class vDate(TimeBase):
    """Date
    Value Name:  DATE
    
    Purpose:  This value type is used to identify values that contain a
      calendar date.
      
    Format Definition:  This value type is defined by the following
      notation:

       date               = date-value

       date-value         = date-fullyear date-month date-mday
       date-fullyear      = 4DIGIT
       date-month         = 2DIGIT        ;01-12
       date-mday          = 2DIGIT        ;01-28, 01-29, 01-30, 01-31
                                          ;based on month/year
                                          
    Description:  If the property permits, multiple "date" values are
      specified as a COMMA-separated list of values.  The format for the
      value type is based on the [ISO.8601.2004] complete
      representation, basic format for a calendar date.  The textual
      format specifies a four-digit year, two-digit month, and two-digit
      day of the month.  There are no separator characters between the
      year, month, and day component text.
    
    Example:  The following represents July 14, 1997:

       19970714
       
       >>> from icalendar.prop import vDate
       >>> date = vDate.from_ical('19970714')
       >>> date.year
       1997
       >>> date.month
       7
       >>> date.day
       14
    """

    def __init__(self, dt):
        if not isinstance(dt, date):
            raise ValueError('Value MUST be a date instance')
        self.dt = dt
        self.params = Parameters({'value': 'DATE'})

    def to_ical(self):
        s = f"{self.dt.year:04}{self.dt.month:02}{self.dt.day:02}"
        return s.encode('utf-8')

    @staticmethod
    def from_ical(ical):
        try:
            timetuple = (
                int(ical[:4]),  # year
                int(ical[4:6]),  # month
                int(ical[6:8]),  # day
            )
            return date(*timetuple)
        except Exception:
            raise ValueError(f'Wrong date format {ical}')


class vDatetime(TimeBase):
    """Render and generates icalendar datetime format.

    vDatetime is timezone aware and uses a timezone library.
    When a vDatetime object is created from an
    ical string, you can pass a valid timezone identifier. When a
    vDatetime object is created from a python datetime object, it uses the
    tzinfo component, if present. Otherwise an timezone-naive object is
    created. Be aware that there are certain limitations with timezone naive
    DATE-TIME components in the icalendar standard.
    """

    def __init__(self, dt):
        self.dt = dt
        self.params = Parameters()

    def to_ical(self):
        dt = self.dt
        tzid = tzid_from_dt(dt)

        s = f"{dt.year:04}{dt.month:02}{dt.day:02}T{dt.hour:02}{dt.minute:02}{dt.second:02}"
        if tzid == 'UTC':
            s += "Z"
        elif tzid:
            self.params.update({'TZID': tzid})
        return s.encode('utf-8')

    @staticmethod
    def from_ical(ical, timezone=None):
        """Create a datetime from the RFC string.

        Format: YYYYMMDDTHHMMSS

        >>> from icalendar import vDatetime
        >>> vDatetime.from_ical("20210302T101500")
        datetime.datetime(2021, 3, 2, 10, 15)

        >>> vDatetime.from_ical("20210302T101500", "America/New_York")
        datetime.datetime(2021, 3, 2, 10, 15, tzinfo=ZoneInfo(key='America/New_York'))

        >>> from zoneinfo import ZoneInfo
        >>> timezone = ZoneInfo("Europe/Berlin")
        >>> vDatetime.from_ical("20210302T101500", timezone)
        datetime.datetime(2021, 3, 2, 10, 15, tzinfo=ZoneInfo(key='Europe/Berlin'))

        """
        tzinfo = None
        if isinstance(timezone, str):
            tzinfo = _timezone.tzp.timezone(timezone)
        elif timezone is not None:
            tzinfo = timezone

        try:
            timetuple = (
                int(ical[:4]),  # year
                int(ical[4:6]),  # month
                int(ical[6:8]),  # day
                int(ical[9:11]),  # hour
                int(ical[11:13]),  # minute
                int(ical[13:15]),  # second
            )
            if tzinfo:
                return _timezone.tzp.localize(datetime(*timetuple), tzinfo)
            elif not ical[15:]:
                return datetime(*timetuple)
            elif ical[15:16] == 'Z':
                return _timezone.tzp.localize_utc(datetime(*timetuple))
            else:
                raise ValueError(ical)
        except Exception as e:
            raise ValueError(f'Wrong datetime format: {ical}') from e


class vDuration(TimeBase):
    """Duration
    Value Name:  DURATION

    Purpose:  This value type is used to identify properties that contain
      a duration of time.

    Format Definition:  This value type is defined by the following
      notation:

       dur-value  = (["+"] / "-") "P" (dur-date / dur-time / dur-week)

       dur-date   = dur-day [dur-time]
       dur-time   = "T" (dur-hour / dur-minute / dur-second)
       dur-week   = 1*DIGIT "W"
       dur-hour   = 1*DIGIT "H" [dur-minute]
       dur-minute = 1*DIGIT "M" [dur-second]
       dur-second = 1*DIGIT "S"
       dur-day    = 1*DIGIT "D"

    Description:  If the property permits, multiple "duration" values are
      specified by a COMMA-separated list of values.  The format is
      based on the [ISO.8601.2004] complete representation basic format
      with designators for the duration of time.  The format can
      represent nominal durations (weeks and days) and accurate
      durations (hours, minutes, and seconds).  Note that unlike
      [ISO.8601.2004], this value type doesn't support the "Y" and "M"
      designators to specify durations in terms of years and months.
      The duration of a week or a day depends on its position in the
      calendar.  In the case of discontinuities in the time scale, such
      as the change from standard time to daylight time and back, the
      computation of the exact duration requires the subtraction or
      addition of the change of duration of the discontinuity.  Leap
      seconds MUST NOT be considered when computing an exact duration.
      When computing an exact duration, the greatest order time
      components MUST be added first, that is, the number of days MUST
      be added first, followed by the number of hours, number of
      minutes, and number of seconds.
      
    Example:  A duration of 15 days, 5 hours, and 20 seconds would be:

        P15DT5H0M20S

      A duration of 7 weeks would be:

        P7W
        
        >>> from icalendar.prop import vDuration
        >>> duration = vDuration.from_ical('P15DT5H0M20S')
        >>> duration
        datetime.timedelta(days=15, seconds=18020)
        >>> duration = vDuration.from_ical('P7W')
        >>> duration
        datetime.timedelta(days=49)

       
     
    """

    def __init__(self, td):
        if not isinstance(td, timedelta):
            raise ValueError('Value MUST be a timedelta instance')
        self.td = td
        self.params = Parameters()

    def to_ical(self):
        sign = ""
        td = self.td
        if td.days < 0:
            sign = "-"
            td = -td
        timepart = ""
        if td.seconds:
            timepart = "T"
            hours = td.seconds // 3600
            minutes = td.seconds % 3600 // 60
            seconds = td.seconds % 60
            if hours:
                timepart += f"{hours}H"
            if minutes or (hours and seconds):
                timepart += f"{minutes}M"
            if seconds:
                timepart += f"{seconds}S"
        if td.days == 0 and timepart:
            return (str(sign).encode('utf-8') + b'P'
                    + str(timepart).encode('utf-8'))
        else:
            return (str(sign).encode('utf-8') + b'P'
                    + str(abs(td.days)).encode('utf-8')
                    + b'D' + str(timepart).encode('utf-8'))

    @staticmethod
    def from_ical(ical):
        match = DURATION_REGEX.match(ical)
        if not match:
            raise ValueError(f'Invalid iCalendar duration: {ical}')

        sign, weeks, days, hours, minutes, seconds = match.groups()
        value = timedelta(
            weeks=int(weeks or 0),
            days=int(days or 0),
            hours=int(hours or 0),
            minutes=int(minutes or 0),
            seconds=int(seconds or 0)
        )

        if sign == '-':
            value = -value

        return value

    @property
    def dt(self):
        """The time delta for compatibility."""
        return self.td


class vPeriod(TimeBase):
    """Period of Time
    Value Name:  PERIOD

    Purpose:  This value type is used to identify values that contain a
      precise period of time.

    Format Definition:  This value type is defined by the following
      notation:

       period     = period-explicit / period-start

       period-explicit = date-time "/" date-time
       ; [ISO.8601.2004] complete representation basic format for a
       ; period of time consisting of a start and end.  The start MUST
       ; be before the end.

       period-start = date-time "/" dur-value
       ; [ISO.8601.2004] complete representation basic format for a
       ; period of time consisting of a start and positive duration
       ; of time.
       
    Description:  If the property permits, multiple "period" values are
      specified by a COMMA-separated list of values.  There are two
      forms of a period of time.  First, a period of time is identified
      by its start and its end.  This format is based on the
      [ISO.8601.2004] complete representation, basic format for "DATE-
      TIME" start of the period, followed by a SOLIDUS character
      followed by the "DATE-TIME" of the end of the period.  The start
      of the period MUST be before the end of the period.  Second, a
      period of time can also be defined by a start and a positive
      duration of time.  The format is based on the [ISO.8601.2004]
      complete representation, basic format for the "DATE-TIME" start of
      the period, followed by a SOLIDUS character, followed by the
      [ISO.8601.2004] basic format for "DURATION" of the period.

    Example:  The period starting at 18:00:00 UTC, on January 1, 1997 and
    ending at 07:00:00 UTC on January 2, 1997 would be:

        19970101T180000Z/19970102T070000Z

        The period start at 18:00:00 on January 1, 1997 and lasting 5
        hours and 30 minutes would be:

        19970101T180000Z/PT5H30M
       
        >>> from icalendar.prop import vPeriod
        >>> period = vPeriod.from_ical('19970101T180000Z/19970102T070000Z')
        >>> period
        (datetime.datetime(1997, 1, 1, 18, 0, tzinfo=backports.zoneinfo.ZoneInfo(key='UTC')), datetime.datetime(1997, 1, 2, 7, 0, tzinfo=backports.zoneinfo.ZoneInfo(key='UTC')))
        >>> period = vPeriod.from_ical('19970101T180000Z/PT5H30M')
        >>> period
        (datetime.datetime(1997, 1, 1, 18, 0, tzinfo=backports.zoneinfo.ZoneInfo(key='UTC')), datetime.timedelta(seconds=19800))

    """

    def __init__(self, per):
        start, end_or_duration = per
        if not (isinstance(start, datetime) or isinstance(start, date)):
            raise ValueError('Start value MUST be a datetime or date instance')
        if not (isinstance(end_or_duration, datetime)
                or isinstance(end_or_duration, date)
                or isinstance(end_or_duration, timedelta)):
            raise ValueError('end_or_duration MUST be a datetime, '
                             'date or timedelta instance')
        by_duration = 0
        if isinstance(end_or_duration, timedelta):
            by_duration = 1
            duration = end_or_duration
            end = start + duration
        else:
            end = end_or_duration
            duration = end - start
        if start > end:
            raise ValueError("Start time is greater than end time")

        self.params = Parameters({'value': 'PERIOD'})
        # set the timezone identifier
        # does not support different timezones for start and end
        tzid = tzid_from_dt(start)
        if tzid:
            self.params['TZID'] = tzid

        self.start = start
        self.end = end
        self.by_duration = by_duration
        self.duration = duration

    def overlaps(self, other):
        if self.start > other.start:
            return other.overlaps(self)
        if self.start <= other.start < self.end:
            return True
        return False

    def to_ical(self):
        if self.by_duration:
            return (vDatetime(self.start).to_ical() + b'/'
                    + vDuration(self.duration).to_ical())
        return (vDatetime(self.start).to_ical() + b'/'
                + vDatetime(self.end).to_ical())

    @staticmethod
    def from_ical(ical, timezone=None):
        try:
            start, end_or_duration = ical.split('/')
            start = vDDDTypes.from_ical(start, timezone=timezone)
            end_or_duration = vDDDTypes.from_ical(end_or_duration, timezone=timezone)
            return (start, end_or_duration)
        except Exception:
            raise ValueError(f'Expected period format, got: {ical}')

    def __repr__(self):
        if self.by_duration:
            p = (self.start, self.duration)
        else:
            p = (self.start, self.end)
        return f'vPeriod({p!r})'

    @property
    def dt(self):
        """Make this cooperate with the other vDDDTypes."""
        return (self.start, (self.duration if self.by_duration else self.end))


class vWeekday(str):
    """This returns an unquoted weekday abbrevation.
    """
    week_days = CaselessDict({
        "SU": 0, "MO": 1, "TU": 2, "WE": 3, "TH": 4, "FR": 5, "SA": 6,
    })

    def __new__(cls, value, encoding=DEFAULT_ENCODING):
        value = to_unicode(value, encoding=encoding)
        self = super().__new__(cls, value)
        match = WEEKDAY_RULE.match(self)
        if match is None:
            raise ValueError(f'Expected weekday abbrevation, got: {self}')
        match = match.groupdict()
        sign = match['signal']
        weekday = match['weekday']
        relative = match['relative']
        if weekday not in vWeekday.week_days or sign not in '+-':
            raise ValueError(f'Expected weekday abbrevation, got: {self}')
        self.relative = relative and int(relative) or None
        self.params = Parameters()
        return self

    def to_ical(self):
        return self.encode(DEFAULT_ENCODING).upper()

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(ical.upper())
        except Exception:
            raise ValueError(f'Expected weekday abbrevation, got: {ical}')


class vFrequency(str):
    """A simple class that catches illegal values.
    """

    frequencies = CaselessDict({
        "SECONDLY": "SECONDLY",
        "MINUTELY": "MINUTELY",
        "HOURLY": "HOURLY",
        "DAILY": "DAILY",
        "WEEKLY": "WEEKLY",
        "MONTHLY": "MONTHLY",
        "YEARLY": "YEARLY",
    })

    def __new__(cls, value, encoding=DEFAULT_ENCODING):
        value = to_unicode(value, encoding=encoding)
        self = super().__new__(cls, value)
        if self not in vFrequency.frequencies:
            raise ValueError(f'Expected frequency, got: {self}')
        self.params = Parameters()
        return self

    def to_ical(self):
        return self.encode(DEFAULT_ENCODING).upper()

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(ical.upper())
        except Exception:
            raise ValueError(f'Expected frequency, got: {ical}')


class vMonth(int):
    """The number of the month for recurrence.

    In :rfc:`5545`, this is just an int.
    In :rfc:`7529`, this can be followed by `L` to indicate a leap month.

        >>> from icalendar import vMonth
        >>> vMonth(1) # first month January
        vMonth('1')
        >>> vMonth("5L") # leap month in Hebrew calendar
        vMonth('5L')
        >>> vMonth(1).leap
        False
        >>> vMonth("5L").leap
        True

    Definition from RFC::

        type-bymonth = element bymonth {
           xsd:positiveInteger |
           xsd:string
        }
    """
    def __new__(cls, month:Union[str, int]):
        if isinstance(month, vMonth):
            return cls(month.to_ical().decode())
        if isinstance(month, str):
            if month.isdigit():
                month_index = int(month)
                leap = False
            else:
                if not month[-1] == "L" and month[:-1].isdigit():
                    raise ValueError(f"Invalid month: {month!r}")
                month_index = int(month[:-1])
                leap = True
        else:
            leap = False
            month_index = int(month)
        self = super().__new__(cls, month_index)
        self.leap = leap
        self.params = Parameters()
        return self

    def to_ical(self) -> bytes:
        """The ical representation."""
        return str(self).encode('utf-8')

    @classmethod
    def from_ical(cls, ical: str):
        return cls(ical)

    def leap():
        doc = "Whether this is a leap month."
        def fget(self) -> bool:
            return self._leap
        def fset(self, value:bool) -> None:
            self._leap = value
        return locals()
    leap = property(**leap())


    def __repr__(self) -> str:
        """repr(self)"""
        return f"{self.__class__.__name__}({str(self)!r})"

    def __str__(self) -> str:
        """str(self)"""
        return f"{int(self)}{'L' if self.leap else ''}"


class vSkip(vText, Enum):
    """Skip values for RRULE.

    These are defined in :rfc:`7529`.

    OMIT  is the default value.
    """

    OMIT = "OMIT"
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"

    def __reduce_ex__(self, _p):
        """For pickling."""
        return self.__class__, (self._name_,)


class vRecur(CaselessDict):
    """Recurrence definition.
    """

    frequencies = ["SECONDLY", "MINUTELY", "HOURLY", "DAILY", "WEEKLY",
                   "MONTHLY", "YEARLY"]

    # Mac iCal ignores RRULEs where FREQ is not the first rule part.
    # Sorts parts according to the order listed in RFC 5545, section 3.3.10.
    canonical_order = ("RSCALE", "FREQ", "UNTIL", "COUNT", "INTERVAL",
                       "BYSECOND", "BYMINUTE", "BYHOUR", "BYDAY", "BYWEEKDAY",
                       "BYMONTHDAY", "BYYEARDAY", "BYWEEKNO", "BYMONTH",
                       "BYSETPOS", "WKST", "SKIP")

    types = CaselessDict({
        'COUNT': vInt,
        'INTERVAL': vInt,
        'BYSECOND': vInt,
        'BYMINUTE': vInt,
        'BYHOUR': vInt,
        'BYWEEKNO': vInt,
        'BYMONTHDAY': vInt,
        'BYYEARDAY': vInt,
        'BYMONTH': vMonth,
        'UNTIL': vDDDTypes,
        'BYSETPOS': vInt,
        'WKST': vWeekday,
        'BYDAY': vWeekday,
        'FREQ': vFrequency,
        'BYWEEKDAY': vWeekday,
        'SKIP': vSkip,
    })

    def __init__(self, *args, **kwargs):
        for k, v in kwargs.items():
            if not isinstance(v, SEQUENCE_TYPES):
                kwargs[k] = [v]
        super().__init__(*args, **kwargs)
        self.params = Parameters()

    def to_ical(self):
        result = []
        for key, vals in self.sorted_items():
            typ = self.types.get(key, vText)
            if not isinstance(vals, SEQUENCE_TYPES):
                vals = [vals]
            vals = b','.join(typ(val).to_ical() for val in vals)

            # CaselessDict keys are always unicode
            key = key.encode(DEFAULT_ENCODING)
            result.append(key + b'=' + vals)

        return b';'.join(result)

    @classmethod
    def parse_type(cls, key, values):
        # integers
        parser = cls.types.get(key, vText)
        return [parser.from_ical(v) for v in values.split(',')]

    @classmethod
    def from_ical(cls, ical: str):
        if isinstance(ical, cls):
            return ical
        try:
            recur = cls()
            for pairs in ical.split(';'):
                try:
                    key, vals = pairs.split('=')
                except ValueError:
                    # E.g. incorrect trailing semicolon, like (issue #157):
                    # FREQ=YEARLY;BYMONTH=11;BYDAY=1SU;
                    continue
                recur[key] = cls.parse_type(key, vals)
            return cls(recur)
        except ValueError:
            raise
        except:
            raise ValueError(f'Error in recurrence rule: {ical}')


class vTime(TimeBase):
    """Time
    Value Name:  TIME

    Purpose:  This value type is used to identify values that contain a
      time of day.

    Format Definition:  This value type is defined by the following
      notation:

       time         = time-hour time-minute time-second [time-utc]

       time-hour    = 2DIGIT        ;00-23
       time-minute  = 2DIGIT        ;00-59
       time-second  = 2DIGIT        ;00-60
       ;The "60" value is used to account for positive "leap" seconds.

       time-utc     = "Z"

    Description:  If the property permits, multiple "time" values are
      specified by a COMMA-separated list of values.  No additional
      content value encoding (i.e., BACKSLASH character encoding, see
      vText) is defined for this value type.

      The "TIME" value type is used to identify values that contain a
      time of day.  The format is based on the [ISO.8601.2004] complete
      representation, basic format for a time of day.  The text format
      consists of a two-digit, 24-hour of the day (i.e., values 00-23),
      two-digit minute in the hour (i.e., values 00-59), and two-digit
      seconds in the minute (i.e., values 00-60).  The seconds value of
      60 MUST only be used to account for positive "leap" seconds.
      Fractions of a second are not supported by this format.

      In parallel to the "DATE-TIME" definition above, the "TIME" value
      type expresses time values in three forms:

      The form of time with UTC offset MUST NOT be used.  For example,
      the following is not valid for a time value:

       230000-0800        ;Invalid time format

      FORM #1 LOCAL TIME

      The local time form is simply a time value that does not contain
      the UTC designator nor does it reference a time zone.  For
      example, 11:00 PM:

       230000
      Time values of this type are said to be "floating" and are not
      bound to any time zone in particular.  They are used to represent
      the same hour, minute, and second value regardless of which time
      zone is currently being observed.  For example, an event can be
      defined that indicates that an individual will be busy from 11:00
      AM to 1:00 PM every day, no matter which time zone the person is
      in.  In these cases, a local time can be specified.  The recipient
      of an iCalendar object with a property value consisting of a local
      time, without any relative time zone information, SHOULD interpret
      the value as being fixed to whatever time zone the "ATTENDEE" is
      in at any given moment.  This means that two "Attendees", may
      participate in the same event at different UTC times; floating
      time SHOULD only be used where that is reasonable behavior.

      In most cases, a fixed time is desired.  To properly communicate a
      fixed time in a property value, either UTC time or local time with
      time zone reference MUST be specified.

      The use of local time in a TIME value without the "TZID" property
      parameter is to be interpreted as floating time, regardless of the
      existence of "VTIMEZONE" calendar components in the iCalendar
      object.

      FORM #2: UTC TIME

      UTC time, or absolute time, is identified by a LATIN CAPITAL
      LETTER Z suffix character, the UTC designator, appended to the
      time value.  For example, the following represents 07:00 AM UTC:

       070000Z

      The "TZID" property parameter MUST NOT be applied to TIME
      properties whose time values are specified in UTC.

      FORM #3: LOCAL TIME AND TIME ZONE REFERENCE

      The local time with reference to time zone information form is
      identified by the use the "TZID" property parameter to reference
      the appropriate time zone definition.

    Example:  The following represents 8:30 AM in New York in winter,
      five hours behind UTC, in each of the three formats:

        083000
        133000Z
        TZID=America/New_York:083000
       
 
    """

    def __init__(self, *args):
        if len(args) == 1:
            if not isinstance(args[0], (time, datetime)):
                raise ValueError(f'Expected a datetime.time, got: {args[0]}')
            self.dt = args[0]
        else:
            self.dt = time(*args)
        self.params = Parameters({'value': 'TIME'})

    def to_ical(self):
        return self.dt.strftime("%H%M%S")

    @staticmethod
    def from_ical(ical):
        # TODO: timezone support
        try:
            timetuple = (int(ical[:2]), int(ical[2:4]), int(ical[4:6]))
            return time(*timetuple)
        except Exception:
            raise ValueError(f'Expected time, got: {ical}')


class vUri(str):
    """URI
    Value Name:  URI

    Purpose:  This value type is used to identify values that contain a
      uniform resource identifier (URI) type of reference to the
      property value.

    Format Definition:  This value type is defined by the following
      notation:

       uri = scheme ":" hier-part [ "?" query ] [ "#" fragment ]

    Description:  This value type might be used to reference binary
      information, for values that are large, or otherwise undesirable
      to include directly in the iCalendar object.

      Property values with this value type MUST follow the generic URI
      syntax defined in [RFC3986].

      When a property parameter value is a URI value type, the URI MUST
      be specified as a quoted-string value.

    Example:  The following is a URI for a network file:

        http://example.com/my-report.txt

        >>> from icalendar.prop import vUri
        >>> uri = vUri.from_ical('http://example.com/my-report.txt')
        >>> uri
        'http://example.com/my-report.txt'

    """

    def __new__(cls, value, encoding=DEFAULT_ENCODING):
        value = to_unicode(value, encoding=encoding)
        self = super().__new__(cls, value)
        self.params = Parameters()
        return self

    def to_ical(self):
        return self.encode(DEFAULT_ENCODING)

    @classmethod
    def from_ical(cls, ical):
        try:
            return cls(ical)
        except Exception:
            raise ValueError(f'Expected , got: {ical}')


class vGeo:
    """Geographic Position

    Property Name:  GEO

    Purpose:  This property specifies information related to the global
        position for the activity specified by a calendar component.

    Value Type:  FLOAT.  The value MUST be two SEMICOLON-separated FLOAT
        values.

    Property Parameters:  IANA and non-standard property parameters can
        be specified on this property.

    Conformance:  This property can be specified in "VEVENT" or "VTODO"
        calendar components.

    Description:  This property value specifies latitude and longitude,
        in that order (i.e., "LAT LON" ordering).  The longitude
        represents the location east or west of the prime meridian as a
        positive or negative real number, respectively.  The longitude and
        latitude values MAY be specified up to six decimal places, which
        will allow for accuracy to within one meter of geographical
        position.  Receiving applications MUST accept values of this
        precision and MAY truncate values of greater precision.

    Example:
        GEO:37.386013;-122.082932
        
        >>> from icalendar.prop import vGeo
        >>> geo = vGeo.from_ical('37.386013;-122.082932')
        >>> geo.latitude
        37.386013
        >>> geo.longitude
        -122.082932
    """

    def __init__(self, geo):
        try:
            latitude, longitude = (geo[0], geo[1])
            latitude = float(latitude)
            longitude = float(longitude)
        except Exception:
            raise ValueError('Input must be (float, float) for '
                             'latitude and longitude')
        self.latitude = latitude
        self.longitude = longitude
        self.params = Parameters()

    def to_ical(self):
        return f'{self.latitude};{self.longitude}'

    @staticmethod
    def from_ical(ical):
        try:
            latitude, longitude = ical.split(';')
            return (float(latitude), float(longitude))
        except Exception:
            raise ValueError(f"Expected 'float;float' , got: {ical}")

    def __eq__(self, other):
        return self.to_ical() == other.to_ical()


class vUTCOffset:
    """UTC Offset
    Value Name:  UTC-OFFSET

    Purpose:  This value type is used to identify properties that contain
      an offset from UTC to local time.

    Format Definition:  This value type is defined by the following
      notation:

       utc-offset = time-numzone

       time-numzone = ("+" / "-") time-hour time-minute [time-second]

    Description:  The PLUS SIGN character MUST be specified for positive
      UTC offsets (i.e., ahead of UTC).  The HYPHEN-MINUS character MUST
      be specified for negative UTC offsets (i.e., behind of UTC).  The
      value of "-0000" and "-000000" are not allowed.  The time-second,
      if present, MUST NOT be 60; if absent, it defaults to zero.

    Example:  The following UTC offsets are given for standard time for
      New York (five hours behind UTC) and Geneva (one hour ahead of
      UTC):

        -0500

        +0100
        
        >>> from icalendar.prop import vUTCOffset
        >>> utc_offset = vUTCOffset.from_ical('-0500')
        >>> utc_offset
        datetime.timedelta(days=-1, seconds=68400)
        >>> utc_offset = vUTCOffset.from_ical('+0100')
        >>> utc_offset
        datetime.timedelta(seconds=3600)

        
    """

    ignore_exceptions = False  # if True, and we cannot parse this

    # component, we will silently ignore
    # it, rather than let the exception
    # propagate upwards

    def __init__(self, td):
        if not isinstance(td, timedelta):
            raise ValueError('Offset value MUST be a timedelta instance')
        self.td = td
        self.params = Parameters()

    def to_ical(self):

        if self.td < timedelta(0):
            sign = '-%s'
            td = timedelta(0) - self.td  # get timedelta relative to 0
        else:
            # Google Calendar rejects '0000' but accepts '+0000'
            sign = '+%s'
            td = self.td

        days, seconds = td.days, td.seconds

        hours = abs(days * 24 + seconds // 3600)
        minutes = abs((seconds % 3600) // 60)
        seconds = abs(seconds % 60)
        if seconds:
            duration = f'{hours:02}{minutes:02}{seconds:02}'
        else:
            duration = f'{hours:02}{minutes:02}'
        return sign % duration

    @classmethod
    def from_ical(cls, ical):
        if isinstance(ical, cls):
            return ical.td
        try:
            sign, hours, minutes, seconds = (ical[0:1],
                                             int(ical[1:3]),
                                             int(ical[3:5]),
                                             int(ical[5:7] or 0))
            offset = timedelta(hours=hours, minutes=minutes, seconds=seconds)
        except Exception:
            raise ValueError(f'Expected utc offset, got: {ical}')
        if not cls.ignore_exceptions and offset >= timedelta(hours=24):
            raise ValueError(
                f'Offset must be less than 24 hours, was {ical}')
        if sign == '-':
            return -offset
        return offset

    def __eq__(self, other):
        if not isinstance(other, vUTCOffset):
            return False
        return self.td == other.td


class vInline(str):
    """This is an especially dumb class that just holds raw unparsed text and
    has parameters. Conversion of inline values are handled by the Component
    class, so no further processing is needed.
    """

    def __new__(cls, value, encoding=DEFAULT_ENCODING):
        value = to_unicode(value, encoding=encoding)
        self = super().__new__(cls, value)
        self.params = Parameters()
        return self

    def to_ical(self):
        return self.encode(DEFAULT_ENCODING)

    @classmethod
    def from_ical(cls, ical):
        return cls(ical)


class TypesFactory(CaselessDict):
    """All Value types defined in RFC 5545 are registered in this factory
    class.

    The value and parameter names don't overlap. So one factory is enough for
    both kinds.
    """

    def __init__(self, *args, **kwargs):
        "Set keys to upper for initial dict"
        super().__init__(*args, **kwargs)
        self.all_types = (
            vBinary,
            vBoolean,
            vCalAddress,
            vDDDLists,
            vDDDTypes,
            vDate,
            vDatetime,
            vDuration,
            vFloat,
            vFrequency,
            vGeo,
            vInline,
            vInt,
            vPeriod,
            vRecur,
            vText,
            vTime,
            vUTCOffset,
            vUri,
            vWeekday,
            vCategory,
        )
        self['binary'] = vBinary
        self['boolean'] = vBoolean
        self['cal-address'] = vCalAddress
        self['date'] = vDDDTypes
        self['date-time'] = vDDDTypes
        self['duration'] = vDDDTypes
        self['float'] = vFloat
        self['integer'] = vInt
        self['period'] = vPeriod
        self['recur'] = vRecur
        self['text'] = vText
        self['time'] = vTime
        self['uri'] = vUri
        self['utc-offset'] = vUTCOffset
        self['geo'] = vGeo
        self['inline'] = vInline
        self['date-time-list'] = vDDDLists
        self['categories'] = vCategory

    #################################################
    # Property types

    # These are the default types
    types_map = CaselessDict({
        ####################################
        # Property value types
        # Calendar Properties
        'calscale': 'text',
        'method': 'text',
        'prodid': 'text',
        'version': 'text',
        # Descriptive Component Properties
        'attach': 'uri',
        'categories': 'categories',
        'class': 'text',
        'comment': 'text',
        'description': 'text',
        'geo': 'geo',
        'location': 'text',
        'percent-complete': 'integer',
        'priority': 'integer',
        'resources': 'text',
        'status': 'text',
        'summary': 'text',
        # Date and Time Component Properties
        'completed': 'date-time',
        'dtend': 'date-time',
        'due': 'date-time',
        'dtstart': 'date-time',
        'duration': 'duration',
        'freebusy': 'period',
        'transp': 'text',
        # Time Zone Component Properties
        'tzid': 'text',
        'tzname': 'text',
        'tzoffsetfrom': 'utc-offset',
        'tzoffsetto': 'utc-offset',
        'tzurl': 'uri',
        # Relationship Component Properties
        'attendee': 'cal-address',
        'contact': 'text',
        'organizer': 'cal-address',
        'recurrence-id': 'date-time',
        'related-to': 'text',
        'url': 'uri',
        'uid': 'text',
        # Recurrence Component Properties
        'exdate': 'date-time-list',
        'exrule': 'recur',
        'rdate': 'date-time-list',
        'rrule': 'recur',
        # Alarm Component Properties
        'action': 'text',
        'repeat': 'integer',
        'trigger': 'duration',
        'acknowledged': 'date-time',
        # Change Management Component Properties
        'created': 'date-time',
        'dtstamp': 'date-time',
        'last-modified': 'date-time',
        'sequence': 'integer',
        # Miscellaneous Component Properties
        'request-status': 'text',
        ####################################
        # parameter types (luckily there is no name overlap)
        'altrep': 'uri',
        'cn': 'text',
        'cutype': 'text',
        'delegated-from': 'cal-address',
        'delegated-to': 'cal-address',
        'dir': 'uri',
        'encoding': 'text',
        'fmttype': 'text',
        'fbtype': 'text',
        'language': 'text',
        'member': 'cal-address',
        'partstat': 'text',
        'range': 'text',
        'related': 'text',
        'reltype': 'text',
        'role': 'text',
        'rsvp': 'boolean',
        'sent-by': 'cal-address',
        'tzid': 'text',
        'value': 'text',
    })

    def for_property(self, name):
        """Returns a the default type for a property or parameter
        """
        return self[self.types_map.get(name, 'text')]

    def to_ical(self, name, value):
        """Encodes a named value from a primitive python type to an icalendar
        encoded string.
        """
        type_class = self.for_property(name)
        return type_class(value).to_ical()

    def from_ical(self, name, value):
        """Decodes a named property or parameter value from an icalendar
        encoded string to a primitive python type.
        """
        type_class = self.for_property(name)
        decoded = type_class.from_ical(value)
        return decoded


__all__ = ["DURATION_REGEX", "TimeBase", "TypesFactory", "WEEKDAY_RULE",
           "tzid_from_dt", "vBinary", "vBoolean", "vCalAddress",
           "vCategory", "vDDDLists", "vDDDTypes", "vDate", "vDatetime",
           "vDuration", "vFloat", "vFrequency", "vGeo", "vInline", "vInt",
           "vMonth", "vPeriod", "vRecur", "vSkip", "vText", "vTime",
           "vUTCOffset", "vUri", "vWeekday"]
