from pathlib import Path
import sys, os, subprocess, tempfile, unittest, warnings, importlib

ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True

class MigrationTests(unittest.TestCase):
    def test_compile_all(self):
        for p in ROOT.rglob('*.py'):
            with self.subTest(file=str(p.relative_to(ROOT))):
                with warnings.catch_warnings():
                    warnings.simplefilter('error', SyntaxWarning)
                    compile(p.read_text(encoding='utf-8'),str(p),'exec')

    def test_core_helpers(self):
        from lib.core.common import getUnicode, getFileItems
        from lib.core.data import paths
        paths.ROOT_PATH=str(ROOT)
        from lib.core.common import setPaths
        setPaths()
        self.assertEqual(getUnicode('中文'.encode()),'中文')
        self.assertEqual(getUnicode(12),'12')
        self.assertTrue(getFileItems(str(ROOT/'data/pass100.txt'),unique=True))
        from plugin.util import randomMD5
        import hashlib
        plain,digest=randomMD5()
        self.assertEqual(digest,hashlib.md5(plain.encode()).hexdigest())
        from plugin.useragent import get_random_agent
        self.assertTrue(get_random_agent())
        from thirdparty.IPy.IPy import IP, IPSet
        self.assertEqual(len(IP('127.0.0.0/30')),4)
        self.assertTrue(IP('127.0.0.1') in IPSet([IP('127.0.0.0/30')]))
        from lib.utils.config import ConfigFileParser
        self.assertIsInstance(ConfigFileParser().FofaEmail(),str)

    def call(self,entry,*args):
        r=subprocess.run([sys.executable,'-B',str(ROOT/entry),*map(str,args)],
            cwd=ROOT, capture_output=True,text=True,encoding='utf-8',errors='replace',
            env={**os.environ,'PYTHONIOENCODING':'utf-8'},timeout=20)
        if r.returncode == 0:
            self.assertNotIn('Traceback',r.stdout+r.stderr,r.stdout+r.stderr)
        return r

    def test_help_entries(self):
        for entry in ['Bayonet.py','POC-T.py']:
            self.assertEqual(self.call(entry,'-h').returncode,0)

    def test_local_modes(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            d=Path(d)
            # No HTTP requests: exercise scheduling and Unicode result persistence only.
            plugin=d/'offline.py'
            plugin.write_text('def poc(target):\n    return "通过:" + target\n',encoding='utf-8')
            targets=d/'targets.txt'
            targets.write_text('\ufeff'+''.join(f'target-{i}\n' for i in range(120)),encoding='utf-8')
            modes=[(['-f',targets],120),(['-iS','local'],1),(['-iA','1-5'],4),(['-iN','127.0.0.0/30'],4)]
            for idx,(args,count) in enumerate(modes):
                output=d/f'result{idx}.txt'
                r=self.call('POC-T.py','-T','-t','50','-m',plugin,*args,'-o',output)
                self.assertEqual(r.returncode,0,r.stdout+r.stderr)
                lines=output.read_text(encoding='utf-8').splitlines()
                self.assertEqual(len(lines),count)
                self.assertEqual(len(set(lines)),count)
                self.assertTrue(all(l.startswith('通过:') for l in lines))
            self.assertNotEqual(self.call('POC-T.py','-m',d/'missing.py','-iS','local').returncode,0)
            plugin.write_text('def poc(target):\n    raise RuntimeError("expected offline failure")\n',encoding='utf-8')
            self.assertNotEqual(self.call('POC-T.py','-m',plugin,'-iS','local').returncode,0)

    def test_keyboard_interrupt(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            folder = Path(folder)
            plugin = folder/'interrupt.py'
            plugin.write_text(
                'import threading, _thread, time\n'
                'threading.Timer(0.3, _thread.interrupt_main).start()\n'
                'def poc(target):\n    time.sleep(0.8)\n    return True\n', encoding='utf-8')
            result = self.call('POC-T.py', '-T', '-t', '5', '-m', plugin,
                '-iA', '1-100', '-o', folder/'output.txt')
            self.assertEqual(result.returncode, 130, result.stdout+result.stderr)
            self.assertIn('Stopping:', result.stdout)
            self.assertNotIn('Traceback', result.stdout+result.stderr)
            after = result.stdout.split('Stopping:', 1)[1]
            self.assertNotIn('scanned in', after)

if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]],verbosity=2)
