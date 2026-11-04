# Bayonet Python 3 使用说明

版本：1.0.3-py3-cn。基于 Bayonet / [POC-T](https://github.com/Xyntax/POC-T/) 修改，保留原作者信息。

## 安装与启动

建议解压到新目录，放入自己的 `script/mac.py` 和 `1.txt`。原脚本、目标文件和扫描结果请保留。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python POC-T.py -T -t 10 -m script/mac.py -f 1.txt --quiet-tls-warnings
```

插件必须在文件顶层定义 `def poc(target):`。返回 False 为未命中，True 为命中，也可返回结果字符串；返回数字2表示请求重试。
使用搜索API或gevent等可选功能才需要安装 `requirements-optional.txt`。

## 参数与进度

- `-t 10`：10个并发线程。`-T` 使用线程模式。
- `-m` 插件路径，`-f` 目标文件，`-o` 自定结果文件；默认结果保存在 `output/`。
- `--quiet-tls-warnings`：只隐藏未验证HTTPS的警告，不改变证书验证行为。
- `--max-retries 2`：收到重试标记后最多额外重试2次。
- `--stall-timeout 300`：连续300秒没有任务完成时，报未完成并退出；0可关闭。
- `-oS` 关闭屏幕进度；`-oF` 关闭结果和错误文件输出。

中文进度靠右显示，窄终端自动分行，每秒刷新。包含总数、已扫、剩余、百分比、发现、队列、活跃、错误及耗时。

队列最多等待1000条，并非总量只有1000。启动时先逐行统计目标数，再流式扫描，不把百万目标全部放入内存。空行忽略，重复行独立扫描；扫描期间请勿修改目标文件。

## 错误与退出码

任务异常及重试耗尽记录在结果文件名后附加的 `.errors.jsonl` 文件中。结果无法写入、输入发生变化或数量不符时会报错，不伪装为完成。

- 0：正常处理结束，或按 `--single` 找到结果后停止。
- 1：出现任务异常、读写失败、数量不符或无进度超时。
- 130：用户中断。

已扫和百分比表示已处理数量，包括发生异常的任务；100%不代表所有请求成功，需结合错误数与退出码。

## 使用边界及文件说明

支持目标为Python 3.10及以上，实际验证环境Windows Python 3.14.2。22项离线测试通过；Linux服务器长时间联网、外部搜索API和gevent模式未实测。

框架不限制插件内部响应大小和自行缓存，不能保证整个进程永远不增长内存。插件吞掉的网络异常框架无法识别。没有断点续扫；异常退出后需自行安排未完成任务。

`data/` 中的字典和User-Agent文件、`requirements*.txt`、证书文件、`toolkit.conf` 属于运行或安装所需，不应按文档清理。`output/` 是扫描结果目录。

`tests/` 保留离线自检代码，需要时可运行：

```bash
python -B tests/test_python3.py
python -B tests/test_shutdown.py
python -B tests/test_stability.py
python -B tests/test_progress.py
python -B tests/test_final_review.py
```
