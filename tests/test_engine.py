import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from engine import norm,parse_date,match,read_xml

class EngineTests(unittest.TestCase):
    def test_normalize_quality(self):
        self.assertEqual(norm('TR: STAR TV FHD (1080p)'), 'star tv')
        self.assertEqual(norm('TR: KANAL D HD'), 'kanal d')
    def test_dates(self):
        self.assertEqual(parse_date('20261115180000 +0300').isoformat(),'2026-11-15T15:00:00+00:00')
    def test_exact_id(self):
        self.assertEqual(match({'id':'STAR.TV.HD.tr','names':['TR: STAR TV FHD']},{'STAR.TV.HD.tr':['STAR TV']},{}),('STAR.TV.HD.tr','exact-id'))
    def test_duplicate_ambiguous(self):
        self.assertEqual(match({'id':'x','names':['TR: STAR TV']},{'foo':['STAR TV'],'bar':['STAR TV']},{}),(None,'ambiguous'))
    def test_parse_xml(self):
        self.assertEqual(read_xml(b'<tv><channel id="a"/></tv>').tag,'tv')
        with self.assertRaises(ValueError):read_xml(b'<!DOCTYPE tv [<!ENTITY x "xx">]><tv/>')

if __name__ == '__main__':unittest.main()
