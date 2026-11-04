"""Bounded streaming scanner. Plugin exceptions never silently discard the queue."""
import json
import sys
import shutil
import unicodedata
import queue
import signal
import threading
import time
import traceback

from lib.core.data import th, conf, logger
from lib.core.common import dataToStdout
from lib.core.enums import POC_RESULT_STATUS, ENGINE_MODE_STATUS


def initEngine():
    th.thread_mode = conf.ENGINE == ENGINE_MODE_STATUS.THREAD
    th.threads_num = th.THREADS_NUM
    th.thread_count = 0
    th.scan_count = th.found_count = th.error_count = th.loaded_count = 0
    th.active = {}
    th.is_continue = True
    th.stopping = th.found_single = False
    th.pop('errmsg', None)
    th.state_lock = threading.RLock()
    th.file_lock = threading.RLock()
    th.producer_done = threading.Event()
    th.start_time = th.last_completion = time.monotonic()
    th.progress_width = 0
    th.progress_lines = 0
    th.progress_lock = threading.RLock()
    th.s_flag, th.f_flag = conf.SCREEN_OUTPUT, conf.FILE_OUTPUT
    th.output = conf.OUTPUT_FILE_PATH
    th.single_mode = conf.SINGLE_MODE
    th.max_retries = conf.get('MAX_RETRIES', 2)
    th.stall_timeout = conf.get('STALL_TIMEOUT', 300.0)
    if 'target_source' not in th:
        th.loaded_count = th.queue.qsize()
        th.total_count = th.loaded_count
        th.producer_done.set()
    logger.success('扫描并发数：%d' % th.threads_num)


def _produce():
    source = th.target_source
    try:
        for target in source:
            while th.is_continue:
                try:
                    th.queue.put(str(target), timeout=0.1)
                    with th.state_lock:
                        th.loaded_count += 1
                    break
                except queue.Full:
                    pass
            if not th.is_continue:
                break
    except BaseException:
        with th.state_lock:
            th.errmsg = 'Target loading failed:\n' + traceback.format_exc()
            th.is_continue = False
    finally:
        try:
            close = getattr(source, 'close', None)
            if close:
                close()
        finally:
            th.producer_done.set()


def _append(path, message):
    with th.file_lock:
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write(message + '\n')


def _error(payload, error):
    with th.state_lock:
        th.error_count += 1
    if th.f_flag:
        _append(th.output + '.errors.jsonl', json.dumps(
            {'target': payload, 'error': error}, ensure_ascii=False))


def _result(status, payload):
    if not status or status == POC_RESULT_STATUS.FAIL:
        return
    message = payload if status is True or status == POC_RESULT_STATUS.SUCCESS else str(status)
    if th.f_flag:
        _append(th.output, message)
    with th.state_lock:
        th.found_count += 1
        if th.single_mode:
            th.found_single = True
            th.is_continue = False
    if th.s_flag and not th.stopping:
        with th.progress_lock:
            _clearProgress()
            dataToStdout('\r' + message + '\n')


def scan():
    ident = threading.get_ident()
    with th.state_lock:
        th.thread_count += 1
    try:
        while th.is_continue:
            try:
                payload = th.queue.get(timeout=0.1)
            except queue.Empty:
                if th.producer_done.is_set():
                    break
                continue
            with th.state_lock:
                th.active[ident] = (payload, time.monotonic())
            try:
                for attempt in range(th.max_retries + 1):
                    try:
                        status = th.module_obj.poc(payload)
                    except BaseException:
                        # SystemExit in a plugin must not silently kill a worker.
                        _error(payload, traceback.format_exc())
                        break
                    if status == POC_RESULT_STATUS.RETRAY:
                        if attempt == th.max_retries:
                            _error(payload, 'Retry limit exceeded')
                        elif th.is_continue:
                            continue
                        break
                    _result(status, payload)
                    break
            except BaseException:
                with th.state_lock:
                    th.errmsg = 'Scanner/output failure:\n' + traceback.format_exc()
                    th.is_continue = False
            finally:
                th.queue.task_done()
                with th.state_lock:
                    th.active.pop(ident, None)
                    th.scan_count += 1
                    th.last_completion = time.monotonic()
    except BaseException:
        with th.state_lock:
            th.errmsg = 'Worker failure:\n' + traceback.format_exc()
            th.is_continue = False
    finally:
        with th.state_lock:
            th.thread_count -= 1


def formatProgress():
    with th.state_lock:
        now = time.monotonic()
        oldest = max((now - started for _, started in th.active.values()), default=0)
        total = th.get('total_count')
        if total is None and th.producer_done.is_set():
            total = th.loaded_count
        if total is None:
            overall = '总数统计中 | 已扫 {:,} | 剩余未知 | 进度未知'.format(th.scan_count)
        else:
            remaining = max(0, total - th.scan_count)
            percent = (100.0 * th.scan_count / total) if total else 100.0
            # Never display 100% for an unfinished task due to decimal rounding.
            percent = min(percent, 99.99 if remaining else 100.0)
            overall = '总数 {:,} | 已扫 {:,} | 剩余 {:,} | 进度 {:.2f}%'.format(
                total, th.scan_count, remaining, percent)
        return overall + (' | 发现 {:,} | 队列 {:,} | 活跃 {} | 错误 {:,}'
                          ' | 最久 {:.0f}秒 | 耗时 {:.0f}秒').format(
            th.found_count, th.queue.qsize(), len(th.active), th.error_count,
            oldest, now - th.start_time)


def _display_width(text):
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in text)


def _progress_rows(message, columns):
    width = max(1, columns - 2)
    rows = []
    row = ''
    for field in message.split(' | '):
        candidate = row + ' | ' + field if row else field
        if row and _display_width(candidate) > width:
            rows.append(row)
            row = field
        else:
            row = candidate
    if row:
        rows.append(row)
    return [' ' * max(0, width - _display_width(row)) + row for row in rows]


def _clearProgress():
    if th.progress_lines and sys.stdout.isatty():
        rewind = '\x1b[%dA' % (th.progress_lines - 1) if th.progress_lines > 1 else ''
        dataToStdout('\r' + rewind + '\x1b[J')
    th.progress_lines = 0


def printProgress():
    with th.progress_lock:
        message = formatProgress()
        columns = shutil.get_terminal_size(fallback=(80, 25)).columns
        if sys.stdout.isatty():
            _clearProgress()
            rows = _progress_rows(message, columns)
            dataToStdout('\n'.join(rows))
            th.progress_lines = len(rows)
        else:
            width = _display_width(message)
            padding = max(0, th.progress_width - width)
            leading = ' ' * max(0, columns - 2 - width)
            dataToStdout('\r' + leading + message + ' ' * padding)
            th.progress_width = width


def _wait_workers(workers, deadline=None):
    while any(worker.is_alive() for worker in workers):
        if deadline is not None and time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def run():
    # Patch before constructing locks/queues for optional cooperative mode.
    greenlets = []
    if conf.ENGINE == ENGINE_MODE_STATUS.GEVENT:
        from gevent import monkey
        monkey.patch_all()
        import gevent
        # The queue was created before patching; replace its synchronization objects.
        old_queue = th.queue
        th.queue = queue.Queue(maxsize=old_queue.maxsize)
        while not old_queue.empty():
            th.queue.put(old_queue.get_nowait())
    initEngine()
    workers = []
    producer = None
    last_report = 0.0
    try:
        if th.f_flag:
            # Fail before executing any plugin when output cannot be created.
            with open(th.output, 'a', encoding='utf-8'):
                pass
        if th.thread_mode:
            if 'target_source' in th:
                producer = threading.Thread(target=_produce, name='target-reader', daemon=True)
                producer.start()
            for number in range(th.threads_num):
                worker = threading.Thread(target=scan, name='scan-%d' % number, daemon=True)
                worker.start()
                workers.append(worker)
            alive = lambda: any(worker.is_alive() for worker in workers)
            sleep = time.sleep
        else:
            if 'target_source' in th:
                greenlets.append(gevent.spawn(_produce))
            greenlets.extend(gevent.spawn(scan) for _ in range(th.threads_num))
            alive = lambda: any(not worker.ready() for worker in greenlets)
            sleep = gevent.sleep
        while alive():
            now = time.monotonic()
            # This exits the whole CLI on a prolonged stall; Python cannot safely
            # cancel an individual arbitrary plugin thread.
            if th.stall_timeout and now - th.last_completion > th.stall_timeout:
                th.errmsg = 'No completed tasks for %.0fs; unfinished scan (not success).' % th.stall_timeout
                th.is_continue = False
                th.stopping = True
                break
            if th.s_flag and not th.stopping and now - last_report >= 1.0:
                printProgress()
                last_report = now
            sleep(0.05)
        if producer:
            _wait_workers([producer], time.monotonic() + 1.0)
        if 'errmsg' not in th and not th.found_single:
            if not th.producer_done.is_set() or not th.queue.empty() or th.active:
                th.errmsg = 'Workers stopped with unfinished targets.'
            elif th.get('total_count') is not None and (
                    th.loaded_count != th.total_count or th.scan_count != th.total_count):
                th.errmsg = 'Target count mismatch; scan is incomplete.' 
    except KeyboardInterrupt:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        th.stopping = True
        th.is_continue = False
        logger.warning('Stopping: no new targets; waiting up to 5 seconds for active tasks.')
        if greenlets:
            gevent.killall(greenlets, block=False)
        if not _wait_workers(workers, time.monotonic() + 5.0):
            logger.warning('Blocked plugin calls remain. Scan is incomplete.')
        raise SystemExit(130)
    finally:
        th.is_continue = False
        if greenlets:
            gevent.killall(greenlets, block=False)
    if th.s_flag and not th.stopping:
        printProgress()
        dataToStdout('\n')
    if 'errmsg' in th:
        logger.error(th.errmsg)
        raise SystemExit(1)
    if th.error_count:
        logger.error('%d task errors; see result .errors.jsonl when file output is enabled.' % th.error_count)
        raise SystemExit(1)
    if th.found_single:
        logger.info('[single-mode] found!')
