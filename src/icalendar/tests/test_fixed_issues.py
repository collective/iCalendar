from icalendar.parser_tools import to_unicode
import unittest

import datetime
import icalendar
import os
import pytz
import pytest
from dateutil import tz

try:
    import zoneinfo
except ModuleNotFoundError:
    from backports import zoneinfo

class TestIssues(unittest.TestCase):
    def test_issue_58(self):
        """Issue #58 - TZID on UTC DATE-TIMEs
        https://github.com/collective/icalendar/issues/58
        """

        # According to RFC 2445: "The TZID property parameter MUST NOT be
        # applied to DATE-TIME or TIME properties whose time values are
        # specified in UTC."

        event = icalendar.Event()
        dt = pytz.utc.localize(datetime.datetime(2012, 7, 16, 0, 0, 0))
        event.add('dtstart', dt)
        self.assertEqual(
            event.to_ical(),
            b"BEGIN:VEVENT\r\n"
            b"DTSTART;VALUE=DATE-TIME:20120716T000000Z\r\n"
            b"END:VEVENT\r\n"
        )

    def test_issue_82(self):
        """Issue #82 - vBinary __repr__ called rather than to_ical from
                       container types
        https://github.com/collective/icalendar/issues/82
        """

        b = icalendar.vBinary('text')
        b.params['FMTTYPE'] = 'text/plain'
        self.assertEqual(b.to_ical(), b'dGV4dA==')
        e = icalendar.Event()
        e.add('ATTACH', b)
        self.assertEqual(
            e.to_ical(),
            b"BEGIN:VEVENT\r\nATTACH;ENCODING=BASE64;FMTTYPE=text/plain;"
            b"VALUE=BINARY:dGV4dA==\r\nEND:VEVENT\r\n"
        )

    def test_issue_104__ignore_exceptions(self):
        """
        Issue #104 - line parsing error in a VEVENT
        (which has ignore_exceptions). Should mark the event broken
        but not raise an exception.
        https://github.com/collective/icalendar/issues/104
        """
        ical_str = """
BEGIN:VEVENT
DTSTART:20140401T000000Z
DTEND:20140401T010000Z
DTSTAMP:20140401T000000Z
SUMMARY:Broken Eevnt
CLASS:PUBLIC
STATUS:CONFIRMED
TRANSP:OPAQUE
X
END:VEVENT"""
        event = icalendar.Calendar.from_ical(ical_str)
        self.assertTrue(isinstance(event, icalendar.Event))
        self.assertTrue(event.is_broken)  # REMOVE FOR NEXT MAJOR RELEASE
        self.assertEqual(
            event.errors,
            [(None, "Content line could not be parsed into parts: 'X': Invalid content line")]  # noqa
        )

    def test_issue_104__no_ignore_exceptions(self):
        """
        Issue #104 - line parsing error in a VCALENDAR
        (which doesn't have ignore_exceptions). Should raise an exception.
        """
        ical_str = """BEGIN:VCALENDAR
VERSION:2.0
METHOD:PUBLISH
BEGIN:VEVENT
DTSTART:20140401T000000Z
DTEND:20140401T010000Z
DTSTAMP:20140401T000000Z
SUMMARY:Broken Eevnt
CLASS:PUBLIC
STATUS:CONFIRMED
TRANSP:OPAQUE
END:VEVENT
X
END:VCALENDAR"""
        with self.assertRaises(ValueError):
            icalendar.Calendar.from_ical(ical_str)

    def test_issue_112(self):
        """Issue #112 - No timezone info on EXDATE
        https://github.com/collective/icalendar/issues/112
        """
        directory = os.path.dirname(__file__)
        path = os.path.join(directory,
                            'issue_112_missing_tzinfo_on_exdate.ics')
        with open(path, 'rb') as ics:
            cal = icalendar.Calendar.from_ical(ics.read())
            event = cal.walk('VEVENT')[0]

            event_ical = to_unicode(event.to_ical())  # Py3 str type doesn't
                                                      # support buffer API
            # General timezone aware dates in ical string
            self.assertTrue('DTSTART;TZID=America/New_York:20130907T120000'
                            in event_ical)
            self.assertTrue('DTEND;TZID=America/New_York:20130907T170000'
                            in event_ical)
            # Specific timezone aware exdates in ical string
            self.assertTrue('EXDATE;TZID=America/New_York:20131012T120000'
                            in event_ical)
            self.assertTrue('EXDATE;TZID=America/New_York:20131011T120000'
                            in event_ical)

            self.assertEqual(event['exdate'][0].dts[0].dt.tzname(), 'EDT')

    def test_issue_116(self):
        """Issue #116/#117 - How to add 'X-APPLE-STRUCTURED-LOCATION'
        https://github.com/collective/icalendar/issues/116
        https://github.com/collective/icalendar/issues/117
        """
        event = icalendar.Event()
        event.add(
            "X-APPLE-STRUCTURED-LOCATION",
            "geo:-33.868900,151.207000",
            parameters={
                "VALUE": "URI",
                "X-ADDRESS": "367 George Street Sydney CBD NSW 2000",
                "X-APPLE-RADIUS": "72",
                "X-TITLE": "367 George Street"
            }
        )
        self.assertEqual(
            event.to_ical(),
            b'BEGIN:VEVENT\r\nX-APPLE-STRUCTURED-LOCATION;VALUE=URI;'
            b'X-ADDRESS="367 George Street Sydney \r\n CBD NSW 2000";'
            b'X-APPLE-RADIUS=72;X-TITLE="367 George Street":'
            b'geo:-33.868900\r\n \\,151.207000\r\nEND:VEVENT\r\n'
        )

        # roundtrip
        self.assertEqual(
            event.to_ical(),
            icalendar.Event.from_ical(event.to_ical()).to_ical()
        )

    def test_issue_142(self):
        """Issue #142 - Multivalued parameters
        This is needed for VCard 3.0.
        https://github.com/collective/icalendar/pull/142
        """
        from icalendar.parser import Contentline, Parameters

        ctl = Contentline.from_ical("TEL;TYPE=HOME,VOICE:000000000")

        self.assertEqual(
            ctl.parts(),
            ('TEL', Parameters({'TYPE': ['HOME', 'VOICE']}), '000000000'),
        )

    def test_issue_143(self):
        """Issue #143 - Allow dots in property names.
        Another vCard related issue.
        https://github.com/collective/icalendar/pull/143
        """
        from icalendar.parser import Contentline, Parameters

        ctl = Contentline.from_ical("ITEMADRNULLTHISISTHEADRESS08158SOMECITY12345.ADR:;;This is the Adress 08; Some City;;12345;Germany")  # nopep8
        self.assertEqual(
            ctl.parts(),
            ('ITEMADRNULLTHISISTHEADRESS08158SOMECITY12345.ADR',
             Parameters(),
             ';;This is the Adress 08; Some City;;12345;Germany'),
        )

        ctl2 = Contentline.from_ical("ITEMADRNULLTHISISTHEADRESS08158SOMECITY12345.X-ABLABEL:")  # nopep8
        self.assertEqual(
            ctl2.parts(),
            ('ITEMADRNULLTHISISTHEADRESS08158SOMECITY12345.X-ABLABEL',
             Parameters(),
             ''),
        )

    def test_issue_157(self):
        """Issue #157 - Recurring rules and trailing semicolons
        https://github.com/collective/icalendar/pull/157
        """
        # The trailing semicolon caused a problem
        ical_str = """BEGIN:VEVENT
DTSTART:20150325T101010
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU;
END:VEVENT"""

        cal = icalendar.Calendar.from_ical(ical_str)
        recur = cal.decoded("RRULE")
        self.assertIsInstance(recur, icalendar.vRecur)
        self.assertEqual(
            recur.to_ical(),
            b'FREQ=YEARLY;BYDAY=1SU;BYMONTH=11'
        )

    def test_issue_168(self):
        """Issue #168 - Parsing invalid icalendars fails without any warning
        https://github.com/collective/icalendar/issues/168
        """

        event_str = """
BEGIN:VCALENDAR
BEGIN:VEVENT
DTEND:20150905T100000Z
DTSTART:20150905T090000Z
X-APPLE-RADIUS=49.91307046514149
UID:123
END:VEVENT
END:VCALENDAR"""

        calendar = icalendar.Calendar.from_ical(event_str)
        self.assertEqual(
            calendar.to_ical(),
            b'BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART:20150905T090000Z\r\n'
            b'DTEND:20150905T100000Z\r\nUID:123\r\n'
            b'END:VEVENT\r\nEND:VCALENDAR\r\n'
        )

    def test_issue_178(self):
        """Issue #178 - A component with an unknown/invalid name is represented
        as one of the known components, the information about the original
        component name is lost.
        https://github.com/collective/icalendar/issues/178
        https://github.com/collective/icalendar/pull/180
        """

        # Parsing of a nonstandard component
        ical_str = '\r\n'.join(['BEGIN:MYCOMP', 'END:MYCOMP'])
        cal = icalendar.Calendar.from_ical(ical_str)
        self.assertEqual(cal.to_ical(),
                         b'BEGIN:MYCOMP\r\nEND:MYCOMP\r\n')

        # Nonstandard component inside other components, also has properties
        ical_str = '\r\n'.join(['BEGIN:VCALENDAR',
                                'BEGIN:UNKNOWN',
                                'UID:1234',
                                'END:UNKNOWN',
                                'END:VCALENDAR'])

        cal = icalendar.Calendar.from_ical(ical_str)
        self.assertEqual(cal.errors, [])
        self.assertEqual(cal.to_ical(),
                         b'BEGIN:VCALENDAR\r\nBEGIN:UNKNOWN\r\nUID:1234\r\n'
                         b'END:UNKNOWN\r\nEND:VCALENDAR\r\n')

        # Nonstandard component is able to contain other components
        ical_str = '\r\n'.join(['BEGIN:MYCOMPTOO',
                                'DTSTAMP:20150121T080000',
                                'BEGIN:VEVENT',
                                'UID:12345',
                                'DTSTART:20150122',
                                'END:VEVENT',
                                'END:MYCOMPTOO'])
        cal = icalendar.Calendar.from_ical(ical_str)
        self.assertEqual(cal.errors, [])
        self.assertEqual(cal.to_ical(),
                         b'BEGIN:MYCOMPTOO\r\nDTSTAMP:20150121T080000\r\n'
                         b'BEGIN:VEVENT\r\nDTSTART:20150122\r\nUID:12345\r\n'
                         b'END:VEVENT\r\nEND:MYCOMPTOO\r\n')

    def test_issue_237(self):
        """Issue #237 - Fail to parse timezone with non-ascii TZID"""

        ical_str = ['BEGIN:VCALENDAR',
                    'BEGIN:VTIMEZONE',
                    'TZID:(UTC-03:00) Brasília',
                    'BEGIN:STANDARD',
                    'TZNAME:Brasília standard',
                    'DTSTART:16010101T235959',
                    'TZOFFSETFROM:-0200',
                    'TZOFFSETTO:-0300',
                    'RRULE:FREQ=YEARLY;INTERVAL=1;BYDAY=3SA;BYMONTH=2',
                    'END:STANDARD',
                    'BEGIN:DAYLIGHT',
                    'TZNAME:Brasília daylight',
                    'DTSTART:16010101T235959',
                    'TZOFFSETFROM:-0300',
                    'TZOFFSETTO:-0200',
                    'RRULE:FREQ=YEARLY;INTERVAL=1;BYDAY=2SA;BYMONTH=10',
                    'END:DAYLIGHT',
                    'END:VTIMEZONE',
                    'BEGIN:VEVENT',
                    'DTSTART;TZID=\"(UTC-03:00) Brasília\":20170511T133000',
                    'DTEND;TZID=\"(UTC-03:00) Brasília\":20170511T140000',
                    'END:VEVENT',
                    'END:VCALENDAR',
                    ]

        cal = icalendar.Calendar.from_ical('\r\n'.join(ical_str))
        self.assertEqual(cal.errors, [])

        dtstart = cal.walk(name='VEVENT')[0].decoded("DTSTART")
        expected = pytz.timezone('America/Sao_Paulo').localize(datetime.datetime(2017, 5, 11, 13, 30))
        self.assertEqual(dtstart, expected)

        try:
            expected_zone = '(UTC-03:00) Brasília'
            expected_tzname = 'Brasília standard'
        except UnicodeEncodeError:
            expected_zone = '(UTC-03:00) Brasília'.encode('ascii', 'replace')
            expected_tzname = 'Brasília standard'.encode('ascii', 'replace')
        self.assertEqual(dtstart.tzinfo.zone, expected_zone)
        self.assertEqual(dtstart.tzname(), expected_tzname)

    def test_issue_321_assert_dst_offset_is_not_false(self):
        """This tests the assertion hitting for a calendar.

        See https://github.com/collective/icalendar/issues/321
        """
        directory = os.path.dirname(__file__)
        path = os.path.join(directory,
                            'issue_321_assert_dst_offset_is_not_false.ics')
        with open(path, 'rb') as ics:
            cal = icalendar.Calendar.from_ical(ics.read())
        timezone = list(cal.walk())[1]
        print(timezone)
        pytz = timezone.to_tz() # assertion should fail

    def test_issue_345(self):
        """Issue #345 - Why is tools.UIDGenerator a class (that must be instantiated) instead of a module? """
        uid1 = icalendar.tools.UIDGenerator.uid()
        uid2 = icalendar.tools.UIDGenerator.uid('test.test')
        uid3 = icalendar.tools.UIDGenerator.uid(unique='123')
        uid4 = icalendar.tools.UIDGenerator.uid('test.test', '123')

        self.assertEqual(uid1.split('@')[1], 'example.com')
        self.assertEqual(uid2.split('@')[1], 'test.test')
        self.assertEqual(uid3.split('-')[1], '123@example.com')
        self.assertEqual(uid4.split('-')[1], '123@test.test')

@pytest.mark.parametrize("zone", [
    pytz.utc,
    zoneinfo.ZoneInfo('UTC'),
    pytz.timezone('UTC'),
    tz.UTC,
    tz.gettz('UTC')])
def test_issue_335_identify_UTC(zone):
    myevent = icalendar.Event()
    dt = datetime.datetime(2021, 11, 17, 15, 9, 15)
    myevent.add('dtstart', dt.astimezone(zone))
    assert 'DTSTART;VALUE=DATE-TIME:20211117T150915Z' in myevent.to_ical().decode('ASCII')
