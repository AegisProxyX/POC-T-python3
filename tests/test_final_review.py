import os,sys,unittest,tempfile,subprocess,queue,types
from pathlib import Path
from unittest.mock import patch
ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'

class FinalTests(unittest.TestCase):
    def test_changed_input_detected(self):
        from lib.controller import loader
        from lib.core.data import conf,th
        from lib.core.enums import TARGET_MODE_STATUS
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            p=Path(d)/'targets.txt';p.write_text('a\nb\n',encoding='utf-8')
            conf.update(TARGET_MODE=TARGET_MODE_STATUS.FILE,INPUT_FILE_PATH=str(p))
            loader.loadPayloads()
            p.write_text('different\n',encoding='utf-8')
            with self.assertRaises(Exception):list(th.target_source)
            loader.loadPayloads()
            source=th.target_source
            self.assertEqual(next(source),'different')
            p.write_text('changed again\n',encoding='utf-8')
            with self.assertRaises(Exception):list(source)
            th.pop('target_source',None)

    def test_count_mismatch_is_not_success(self):
        from lib.controller import engine
        from lib.core.data import conf,th
        from lib.core.enums import ENGINE_MODE_STATUS
        conf.update(ENGINE=ENGINE_MODE_STATUS.THREAD,MODULE_NAME='offline',FILE_OUTPUT=False,
                    SCREEN_OUTPUT=False,OUTPUT_FILE_PATH='',SINGLE_MODE=False,MAX_RETRIES=2,STALL_TIMEOUT=5)
        th.THREADS_NUM=2;th.queue=queue.Queue(maxsize=1000)
        th.target_source=iter(['one']);th.total_count=2
        th.module_obj=types.SimpleNamespace(poc=lambda target:False)
        with self.assertRaises(SystemExit) as ex:engine.run()
        self.assertEqual(ex.exception.code,1)
        self.assertIn('count mismatch',th.errmsg)
        th.pop('target_source',None)

    def test_socket_closed(self):
        from plugin.util import checkPortTcp
        for failing in [False,True]:
            with patch('plugin.util.socket.socket') as create:
                sock=create.return_value
                if failing:sock.connect.side_effect=OSError('offline failure')
                self.assertEqual(checkPortTcp('offline.invalid',80),not failing)
                sock.close.assert_called_once()

    def test_unsafe_output_and_unwritable_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            d=Path(d);plugin=d/'offline.py';targets=d/'targets.txt';marker=d/'executed'
            plugin.write_text('from pathlib import Path\ndef poc(target):\n    Path('+repr(str(marker))+').touch()\n    return True\n',encoding='utf-8')
            targets.write_text('offline-target\n',encoding='utf-8')
            original=targets.read_bytes();source=plugin.read_bytes()
            for output in [targets,plugin,d/'missing'/'results.txt']:
                r=subprocess.run([sys.executable,'-B',str(ROOT/'POC-T.py'),'-T','-m',str(plugin),'-f',str(targets),'-o',str(output)],
                    cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=10,
                    env={**os.environ,'PYTHONIOENCODING':'utf-8'})
                self.assertEqual(r.returncode,1,r.stdout+r.stderr)
                self.assertFalse(marker.exists())
                self.assertEqual(targets.read_bytes(),original)
                self.assertEqual(plugin.read_bytes(),source)

if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
