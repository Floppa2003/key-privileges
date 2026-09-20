"""Offline synthetic canaries; do not claim authenticated Only Assist UI coverage."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'only_assist_device_probe.py'
spec = importlib.util.spec_from_file_location('only_assist_device_probe', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
P = m.PACKAGE


def node(text='', y=100, extra='', children=''):
    return f'<node package="{P}" text="{text}" class="android.widget.TextView" bounds="[0,{y}][1000,{y+100}]" {extra}>{children}</node>'


def screen(*nodes):
    return f'<hierarchy><node package="{P}" bounds="[0,0][1080,2400]">'+''.join(nodes)+'</node></hierarchy>'


class Devices(unittest.TestCase):
    def test_exactly_one_authorized(self):
        self.assertEqual(m.select_device('List of devices attached\nTEST\tdevice\n', None), 'TEST')

    def test_no_device(self):
        with self.assertRaisesRegex(m.ProbeError, 'no_device'):
            m.select_device('List of devices attached\n', None)

    def test_no_silent_choice(self):
        with self.assertRaisesRegex(m.ProbeError, 'multiple_devices'):
            m.select_device('A device\nB unauthorized', None)

    def test_unauthorized(self):
        with self.assertRaisesRegex(m.ProbeError, 'unauthorized'):
            m.select_device('A unauthorized', 'A')

    def test_selected_missing(self):
        with self.assertRaisesRegex(m.ProbeError, 'not_connected'):
            m.select_device('A device', 'B')

    def test_background_task_does_not_count(self):
        self.assertIsNone(m.resumed_package(f'Hist #0: ActivityRecord{{ u0 {P}/X }}'))

    def test_resumed_and_multidisplay(self):
        self.assertEqual(m.resumed_package(f'mResumedActivity: ActivityRecord{{abc u0 {P}/X t1}}'), P)
        self.assertIsNone(m.resumed_package(f'mResumedActivity: ActivityRecord{{ u0 {P}/X }}\ntopResumedActivity=ActivityRecord{{ u0 example.other/X }}'))


class Screens(unittest.TestCase):
    def test_visible_screen_is_not_catalogue(self):
        result = m.screen_labels(screen(node('Скидки'), node('Example shop', 600)), 'Скидки')
        self.assertEqual(result['element_count'], 2)
        self.assertFalse(result['catalogue_complete'])

    def test_bottom_nav_is_not_title(self):
        with self.assertRaisesRegex(m.ProbeError, 'expected_top_title'):
            m.screen_labels(screen(node('Чат'), node('Скидки', 2100)), 'Скидки')

    def test_login_labels_fail_closed(self):
        for label in ('Alfa ID', 'Добро пожаловать', 'Войти'):
            with self.assertRaisesRegex(m.ProbeError, 'login_required'):
                m.screen_labels(screen(node(label)), label)

    def test_other_package_dialog_is_rejected(self):
        xml = screen(node('Скидки')).replace('</hierarchy>', '<node package="example.keyboard" text="PRIVATE" /></hierarchy>')
        with self.assertRaisesRegex(m.ProbeError, 'another_package'):
            m.screen_labels(xml, 'Скидки')

    def test_input_and_aggregate_not_saved(self):
        field = f'<node package="{P}" class="android.widget.EditText" text="PRIVATE" bounds="[0,400][1000,500]"/>'
        xml = screen(node('Скидки'), node('PRIVATE', 350, children=field), node('Example shop', 600))
        self.assertNotIn('PRIVATE', json.dumps(m.screen_labels(xml, 'Скидки')))

    def test_password_is_rejected(self):
        with self.assertRaisesRegex(m.ProbeError, 'password'):
            m.screen_labels(screen(node('Скидки'), node('PRIVATE', 700, 'password="true"')), 'Скидки')

    def test_hidden_node_not_saved(self):
        result=m.screen_labels(screen(node('Скидки'), node('PRIVATE', 700, 'visible-to-user="false"')), 'Скидки')
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_entities_and_invalid_xml_rejected(self):
        for xml in ('<!DOCTYPE node>', '<hierarchy>', '<!ENTITY x "abc">'):
            with self.assertRaises(m.ProbeError):
                m.screen_labels(xml, 'Скидки')

    def test_cleanup_even_on_bad_screen(self):
        class Fake(m.Adb):
            def __init__(self): self.calls=[]
            def run(self, *args, **kwargs):
                self.calls.append(args)
                if args[:3]==('shell','dumpsys','activity'):
                    return f'mResumedActivity: ActivityRecord{{ u0 {P}/X }}'
                if args[:2]==('shell','cat'):return screen(node('Alfa ID'))
                return ''
        adb=Fake()
        with self.assertRaisesRegex(m.ProbeError, 'login_required'): adb.capture('Alfa ID')
        self.assertEqual(adb.calls[-1][:3], ('shell','rm','-f'))
        self.assertFalse(any('input' in c or 'install' in c or 'start' in c for c in adb.calls))

    def test_foreground_switch_rejected(self):
        class Fake(m.Adb):
            def __init__(self): self.count=0
            def run(self,*args,**kwargs):
                if args[:3]==('shell','dumpsys','activity'):
                    self.count+=1
                    return f'mResumedActivity: ActivityRecord{{ u0 {P if self.count==1 else "example.other"}/X }}'
                if args[:2]==('shell','cat'):return screen(node('Скидки'))
                return ''
        with self.assertRaisesRegex(m.ProbeError, 'foreground'): Fake().capture('Скидки')


class Storage(unittest.TestCase):
    def test_private_modes_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            one=m.save_private({'test':1},Path(d)/'capture')
            two=m.save_private({'test':2},Path(d)/'capture')
            self.assertNotEqual(one,two)
            self.assertEqual(json.loads(one.read_text()), {'test':1})
            if os.name=='posix':self.assertEqual(one.stat().st_mode&0o777,0o600)

    def test_git_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'.git').mkdir()
            with self.assertRaisesRegex(m.ProbeError,'git_worktree'):
                m.save_private({},Path(d)/'private')

    def test_symlink_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'target';target.mkdir(); link=Path(d)/'link';link.symlink_to(target)
            with self.assertRaisesRegex(m.ProbeError,'symlink'):
                m.save_private({},link)

    def test_world_readable_directory_rejected(self):
        if os.name!='posix': return
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d,0o755)
            with self.assertRaisesRegex(m.ProbeError,'permissions'):
                m.save_private({},Path(d))


if __name__=='__main__':unittest.main()
