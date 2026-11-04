import sys, os, unittest, tempfile, subprocess, threading, queue
from pathlib import Path
from unittest.mock import patch

ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
from lib.core.data import conf,th,paths
from lib.core.enums import TARGET_MODE_STATUS, API_MODE_NAME
from lib.controller import loader,engine

class ProgressTests(unittest.TestCase):
    def test_file_count_preserves_streaming(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            file=Path(d)/'targets.txt'
            file.write_text('\ufeffa\n\n b \n a\n  \n',encoding='utf-8')
            conf.TARGET_MODE=TARGET_MODE_STATUS.FILE
            conf.INPUT_FILE_PATH=str(file)
            loader.loadPayloads()
            self.assertEqual(th.total_count,3)
            self.assertEqual(th.queue.maxsize,1000)
            self.assertEqual(th.queue.qsize(),0)
            self.assertEqual(list(th.target_source),['a','b','a'])

    def test_other_mode_totals(self):
        for mode,settings,count in [
            (TARGET_MODE_STATUS.SINGLE,{'SINGLE_TARGET_STR':'a'},1),
            (TARGET_MODE_STATUS.RANGE,{'I_NUM2':'1-11'},10),
            (TARGET_MODE_STATUS.IPMASK,{'NETWORK_STR':'127.0.0.0/30'},4)]:
            conf.update(settings)
            conf.TARGET_MODE=mode
            loader.loadPayloads()
            self.assertEqual(th.total_count,count)
            self.assertEqual(len(list(th.target_source)),count)

    def test_chinese_percent_and_remaining(self):
        import time
        th.update(state_lock=threading.RLock(),active={},total_count=1000000,
                  scan_count=126,found_count=0,error_count=0,loaded_count=1126,
                  producer_done=threading.Event(),queue=queue.Queue(),start_time=time.monotonic())
        s=engine.formatProgress()
        for text in ['总数 1,000,000','已扫 126','剩余 999,874','进度 0.01%','队列','活跃','错误','耗时']:
            self.assertIn(text,s)
        th.total_count=1000000
        th.scan_count=999999
        self.assertIn('进度 99.99%',engine.formatProgress())
        th.scan_count=1000000
        self.assertIn('剩余 0 | 进度 100.00%',engine.formatProgress())
        th.total_count=0
        th.scan_count=0
        self.assertIn('进度 100.00%',engine.formatProgress())

    def test_cli_final_progress(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            d=Path(d)
            plugin=d/'offline.py'
            plugin.write_text('def poc(target):\n    return False\n',encoding='utf-8')
            targets=d/'targets.txt'
            targets.write_text('a\n\nb\na\n',encoding='utf-8')
            r=subprocess.run([sys.executable,'-B',str(ROOT/'POC-T.py'),'-T','-t','10',
                '-m',str(plugin),'-f',str(targets),'-oF'],cwd=ROOT,capture_output=True,
                text=True,encoding='utf-8',errors='replace',timeout=10,
                env={**os.environ,'PYTHONIOENCODING':'utf-8'})
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn('总数 3 | 已扫 3 | 剩余 0 | 进度 100.00%',r.stdout)

    def test_right_alignment_and_redraw(self):
        import time
        th.update(state_lock=threading.RLock(),progress_lock=threading.RLock(),
                  progress_lines=0,progress_width=0,active={},total_count=1000000,
                  scan_count=126,found_count=0,error_count=0,loaded_count=1126,
                  producer_done=threading.Event(),queue=queue.Queue(),start_time=time.monotonic())
        message=engine.formatProgress()
        for width in [80,120,240]:
            rows=engine._progress_rows(message,width)
            self.assertTrue(all(engine._display_width(row)==width-2 for row in rows))
            self.assertEqual(' | '.join(row.lstrip() for row in rows),message)
        chunks=[]
        with patch.object(engine.sys.stdout,'isatty',return_value=True), \
             patch.object(engine.shutil,'get_terminal_size',return_value=os.terminal_size((80,25))), \
             patch.object(engine,'dataToStdout',side_effect=chunks.append):
            engine.printProgress()
            self.assertGreater(th.progress_lines,1)
            engine.printProgress()
            self.assertTrue(any('\x1b[J' in chunk for chunk in chunks))
            engine._clearProgress()
            self.assertEqual(th.progress_lines,0)

if __name__=='__main__': unittest.main(argv=[sys.argv[0]],verbosity=2)
