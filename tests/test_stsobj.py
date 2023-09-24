import datetime
import unittest

import stskit.stsobj as stsobj


class TestStsObj(unittest.TestCase):
    def test_time_to_minutes(self):
        t = datetime.time(hour=15, minute=55, second=31, microsecond=1)
        assert stsobj.time_to_minutes(t) == 15 * 60 + 56
        td = datetime.timedelta(hours=15, minutes=55, seconds=31, milliseconds=500, microseconds=1)
        assert stsobj.time_to_minutes(td) == 15 * 60 + 56

    def test_time_to_seconds(self):
        t = datetime.time(hour=15, minute=55, second=31, microsecond=1)
        r = stsobj.time_to_seconds(t)
        s = (15 * 60 + 55) * 60 + 31
        assert r == s
        td = datetime.timedelta(hours=15, minutes=55, seconds=31, milliseconds=500, microseconds=1)
        r = stsobj.time_to_seconds(td)
        assert r == s

    def test_minutes_to_time(self):
        m = 15 * 60 + 55.5
        t = datetime.time(hour=15, minute=55, second=30)
        r = stsobj.minutes_to_time(m)
        assert t.hour == r.hour
        assert t.minute == r.minute
        assert t.second == r.second

    def test_seconds_to_time(self):
        s = (15 * 60 + 55) * 60 + 30
        t = datetime.time(hour=15, minute=55, second=30)
        r = stsobj.seconds_to_time(s)
        assert t.hour == r.hour
        assert t.minute == r.minute
        assert t.second == r.second

    def test_zugnummer(self):
        """
        - "536" -> 536
        - "ICE 624" -> 624
        - "ICE624" -> 624
        - "S8 8376 RF" -> 8376
        - "S 8449 S12" -> 8449
        """

        assert stsobj.ZugDetails.get_nummer("536") == 536
        assert stsobj.ZugDetails.get_nummer("ICE 624") == 624
        assert stsobj.ZugDetails.get_nummer("S8 8376 RF") == 8376
        assert stsobj.ZugDetails.get_nummer("S 8449 S12") == 8449
