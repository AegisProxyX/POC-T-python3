import unittest
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ShutdownTests(unittest.TestCase):
    def test_interrupt_stops_queue(self):
        code = """
import sys, threading, _thread, time, queue
sys.path.insert(0, sys.argv[1])
from lib.core.data import th, conf
from lib.core.enums import ENGINE_MODE_STATUS
from lib.controller.engine import run
conf.ENGINE = ENGINE_MODE_STATUS.THREAD
conf.MODULE_NAME = 'offline'
conf.FILE_OUTPUT = False
conf.SCREEN_OUTPUT = False
conf.OUTPUT_FILE_PATH = 'unused'
conf.SINGLE_MODE = False
th.THREADS_NUM = 4
th.queue = queue.Queue()
for i in range(100): th.queue.put(str(i))
class Plugin:
    def poc(self, target):
        time.sleep(0.4)
        return False
th.module_obj = Plugin()
timer = threading.Timer(0.15, _thread.interrupt_main)
timer.start()
try:
    run()
except SystemExit as ex:
    timer.join()
    assert ex.code == 130, ex.code
    assert th.queue.qsize() >= 96, th.queue.qsize()
    assert th.thread_count == 0, th.thread_count
    print('CLEAN_INTERRUPT')
else:
    raise AssertionError('interrupt was not handled')
"""
        r = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT)],
            capture_output=True, text=True, encoding='utf-8', timeout=10,
            env={**os.environ,'PYTHONIOENCODING':'utf-8'})
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertIn('CLEAN_INTERRUPT', r.stdout)
        self.assertNotIn('Traceback', r.stdout+r.stderr)

    def test_warning_filter_is_specific(self):
        code = """
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)
with warnings.catch_warnings(record=True) as seen:
    warnings.warn('HTTPS test', InsecureRequestWarning)
    warnings.warn('Keep other warnings visible', RuntimeWarning)
    assert len(seen) == 1 and seen[0].category is RuntimeWarning
"""
        r=subprocess.run([sys.executable, '-B', '-c', code], capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

if __name__=='__main__': unittest.main(verbosity=2)
