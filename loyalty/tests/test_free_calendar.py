"""Provider quotas and UTC-date Coral rotation must agree with actual cron."""
import re
import sys
import unittest
from datetime import date,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'loyalty'))
from ekp_session_collect import MAX_CREDITS as EKP_CREDITS


def weekdays(filename):
    text=(ROOT/'.github/workflows'/filename).read_text()
    value=re.search(r"schedule:\s*\n\s*- cron: '([^']+)'",text)
    if not value:raise AssertionError('Explicit scheduled workflow is missing')
    minute,hour,dom,month,dow=value[1].split()
    if (dom,month)!=('*','*'):raise AssertionError('Unexpected calendar filter')
    selected=set(range(7)) if dow=='*' else {(int(v)-1)%7 for v in dow.split(',')}
    return minute,hour,selected


class FreeCalendarTests(unittest.TestCase):
    def test_provider_is_four_days_and_ekp_remains_weekly(self):
        self.assertEqual(weekdays('loyalty-free-access.yml'),('3','6',{0,1,3,4}))
        self.assertEqual(weekdays('ekp-api.yml'),('13','7',{0}))

    def test_every_31_day_window_fits_recurring_free_allocation(self):
        source_days=weekdays('loyalty-free-access.yml')[2];ekp_days=weekdays('ekp-api.yml')[2]
        base=date(2026,1,1)
        for shift in range(366):
            days=[base+timedelta(days=shift+i) for i in range(31)]
            n=sum(d.weekday() in source_days for d in days);m=sum(d.weekday() in ekp_days for d in days)
            self.assertLessEqual(n,19);self.assertLessEqual(m,5)
            self.assertLessEqual(n*269+m*EKP_CREDITS,5986)

    def test_both_coral_halves_recur_without_even_day_starvation(self):
        source_days=weekdays('loyalty-free-access.yml')[2]
        base=date(2026,1,1)
        days=[base+timedelta(days=i) for i in range(70)]
        for half in (0,1):
            observations=[d for d in days if d.weekday() in source_days and d.toordinal()%2==half]
            self.assertGreater(len(observations),10)
            self.assertLessEqual(max((b-a).days for a,b in zip(observations,observations[1:])),4)

    def test_remaining_observed_cycle_with_two_release_reservations(self):
        # Reproduce the observed account period and balance, not a runtime rule.
        source_days=weekdays('loyalty-free-access.yml')[2];ekp_days=weekdays('ekp-api.yml')[2]
        start=date(2026,9,17);end=date(2026,10,15)
        days=[start+timedelta(days=i) for i in range((end-start).days+1)]
        n=sum(d.weekday() in source_days for d in days);m=sum(d.weekday() in ekp_days for d in days)
        self.assertEqual((n,m),(17,4));self.assertEqual(n*269+m*EKP_CREDITS,5273)
        self.assertGreaterEqual(6346-300-269,n*269+m*EKP_CREDITS)

if __name__=='__main__':unittest.main()
