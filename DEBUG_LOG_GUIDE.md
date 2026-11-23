# Debug Logging Guide — RewriteWorker Silent Failure Investigation

## Overview
Comprehensive `>>> [TAG]` logging was added across the entire signal chain from UI button click to worker completion/error. All logs are emitted via Python's `logging` module (INFO or DEBUG level).

## Log Chain (Expected Order)

### Phase 1: UI Initiation (`main_window.py`)
| # | Tag | Log Message | Meaning |
|---|-----|-------------|---------|
| 1 | `[DEBUG]` | `source_type=..., source_value_len=...` | User clicked "开始写作", inputs received |
| 2 | `[SIGNAL]` | `signals object id=...` | Signal bus created/verified |
| 3 | `[DEBUG]` | `worker created: ...` | RewriteWorker instance created |
| 4 | `[DEBUG]` | `calling _thread.start()` | About to start QThread |
| 5 | `[DEBUG]` | `thread started, isRunning=...` | Thread should be running (True) |

### Phase 2: Worker Execution (`worker.py`)
| # | Tag | Log Message | Meaning |
|---|-----|-------------|---------|
| 6 | `[WORKER]` | `run() entered \| thread_id=...\| pid=...` | Worker thread actually started executing |
| 7 | `[WORKER]` | `Step 1: content extraction starting` | Beginning to extract content |
| 8 | `[WORKER]` | `Calling ce.extract() \| type=...\| value_len=...` | About to call content extractor |
| 9 | `[WORKER]` | `ce.extract() returned \| text_len=...\| title=...` | Content extracted successfully |
| 10 | `[WORKER]` | `Building prompt and emitting to UI` | Prompt constructed, sending to preview tab |
| 11 | `[WORKER]` | `Calling rw.call_ollama_streaming() \| model=...` | About to call Ollama API (this is where long delays happen) |
| 12 | `[WORKER]` | `call_ollama_streaming returned \| rewritten_len=...` | AI response received completely |

### Phase 3: Signal Return to UI (`main_window.py`)
| # | Tag | Log Message | Meaning |
|---|-----|-------------|---------|
| 13 | `[SIGNAL]` | `_on_rewrite_finished called \| title_len=...\| body_len=...` | Finished signal received |
| 14 | `[SIGNAL]` | `_on_rewrite_finished UI updated: btn_start enabled, cancel disabled` | UI restored to ready state |

### Phase 4: Thread Cleanup (`main_window.py`)
| # | Tag | Log Message | Meaning |
|---|-----|-------------|---------|
| 15 | `[THREAD]` | `_on_thread_finished called \| sender=...` | QThread exited, cleanup starting |
| 16 | `[THREAD]` | `_on_thread_finished clearing references` | References cleared (identity verified) |

## Error/Abort Paths

### Empty Content
```
>>> [WORKER] error emitted: empty content
>>> [SIGNAL] _on_rewrite_error called | msg='提取到的内容为空...'
```

### Thread Cancellation
```
>>> [CANCEL] _on_cancel_task called | _worker=True
[Worker checks self._cancelled and exits early]
>>> [THREAD] _on_thread_finished called | sender=...
>>> [THREAD] _on_thread_finished clearing references
```

### Stale Callback Protection (T3.0)
```
>>> [THREAD] _on_thread_finished skipped (stale callback) | sender=... | expected_id=...
```
This means an old thread's finished signal arrived after a new task was already started. The stale callback is safely ignored.

## Diagnostic Flow

### If you see logs 1-5 but NOT log 6:
**Problem**: Thread starts but `run()` never executes.
**Suspects**:
- `self._worker.moveToThread(self._thread)` failed silently
- Lambda connection `started.connect(lambda: self._worker.run())` issue
- Worker was garbage-collected before thread started

### If you see logs 6-9 but NOT log 10/11:
**Problem**: Content extraction succeeded but prompt building failed.
**Suspects**: Exception in `rw.build_prompt()` that's caught somewhere or the worker crashes

### If you see log 11 but it never returns (log 12):
**Problem**: Ollama API call hangs.
**Suspects**:
- Network/connectivity issue to Ollama server
- Ollama model loading takes too long
- Request body malformed causing timeout on server side
- Check: `curl http://localhost:11434/api/tags` to verify Ollama is running

### If you see no logs at all after clicking button:
**Problem**: `_on_start_writing()` not reached.
**Suspects**:
- Button connection broken
- Event loop blocked (Qt UI frozen)
- Check browser console for JavaScript errors if using web interface

## How to Run with Verbose Logging

```bash
cd /home/gan/AI_Mine/proj-publisher
python3 main.py 2>&1 | grep -E ">>> \[|ERROR|WARNING"
```

Or with full debug output:
```bash
python3 main.py 2>&1
```

## Files Modified
- `main_window.py` — Signal handlers, thread lifecycle, UI callbacks
- `worker.py` — Worker execution steps, API call instrumentation
