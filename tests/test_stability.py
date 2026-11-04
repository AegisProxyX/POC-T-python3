import sys, os, subprocess, unittest, tempfile, time, json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'

class StabilityTests(unittest.TestCase):
    def call(self, plugin, *extra):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            folder=Path(folder)
            (folder/'poc.py').write_text(plugin,encoding='utf-8')
            output=folder/'results.txt'
            r=subprocess.run([sys.executable,'-B',str(ROOT/'POC-T.py'),'-T','-t','5',
                '-m',str(folder/'poc.py'),'-iA','0-100','-o',str(output),'-oS',*extra],
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=12,
                env={**os.environ,'PYTHONIOENCODING':'utf-8'})
            errors=Path(str(output)+'.errors.jsonl')
            entries=[json.loads(line) for line in errors.read_text(encoding='utf-8').splitlines()] if errors.exists() else []
            return r,entries

    def test_systemexit_does_not_lose_targets(self):
        r,entries=self.call('def poc(target):\n    raise SystemExit(1)\n')
        self.assertEqual(r.returncode,1,r.stdout+r.stderr)
        self.assertEqual(len(entries),100)
        self.assertEqual(len({e['target'] for e in entries}),100)

    def test_exception_continues_and_reports(self):
        r,entries=self.call('def poc(target):\n    raise ValueError("offline failure")\n')
        self.assertEqual(r.returncode,1)
        self.assertEqual(len(entries),100)

    def test_retries_terminate(self):
        r,entries=self.call('def poc(target):\n    return 2\n','--max-retries','2')
        self.assertEqual(r.returncode,1)
        self.assertEqual(len(entries),100)
        self.assertTrue(all(e['error']=='Retry limit exceeded' for e in entries))

    def test_stall_exits_incomplete(self):
        start=time.monotonic()
        r,entries=self.call('import time\ndef poc(target):\n    time.sleep(20)\n    return False\n',
            '--stall-timeout','0.2')
        self.assertEqual(r.returncode,1,r.stdout+r.stderr)
        self.assertIn('unfinished scan',r.stdout)
        self.assertLess(time.monotonic()-start,5)

    def test_streaming_and_retry_counts(self):
        from lib.core.data import conf,th
        from lib.controller import engine
        from lib.core.enums import ENGINE_MODE_STATUS
        import queue, collections
        conf.update(ENGINE=ENGINE_MODE_STATUS.THREAD,MODULE_NAME='offline',FILE_OUTPUT=False,
                    SCREEN_OUTPUT=False,OUTPUT_FILE_PATH='',SINGLE_MODE=False,MAX_RETRIES=2,STALL_TIMEOUT=10)
        th.THREADS_NUM=5
        th.queue=queue.Queue(maxsize=1)
        th.target_source=(str(i) for i in range(100))
        calls=collections.Counter()
        def poc(target):
            calls[target]+=1
            return 2 if calls[target]<3 else False
        th.module_obj=SimpleNamespace(poc=poc)
        engine.run()
        self.assertEqual(th.loaded_count,100)
        self.assertEqual(th.scan_count,100)
        self.assertEqual(th.thread_count,0)
        self.assertEqual(th.queue.unfinished_tasks,0)
        self.assertTrue(all(n==3 for n in calls.values()))
        th.pop('target_source',None)

    def test_title_bytes_fix(self):
        from plugin.extracts import getTitle
        with patch('plugin.extracts.requests.get',return_value=SimpleNamespace(text='<title>Offline title</title>')):
            self.assertEqual(getTitle('http://offline.invalid'),'Offline title')

if __name__=='__main__': unittest.main(argv=[sys.argv[0]],verbosity=2)
