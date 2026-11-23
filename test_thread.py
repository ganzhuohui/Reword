"""测试信号连接和线程工作是否正常。"""
import sys, logging, time
logging.basicConfig(level=logging.DEBUG)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, QObject

sys.path.insert(0, '/home/gan/AI_Mine/proj-publisher')
from worker import RewriteWorker, WorkerSignals

signals = WorkerSignals()
print('WorkerSignals created OK')

results = []

# Connect to signals (simulating MainWindow.__init__)
signals.status.connect(lambda msg: results.append(('status', msg)))
signals.progress.connect(lambda s, m, msg: results.append(('progress', s, m, msg)))
signals.error.connect(lambda msg: results.append(('error', msg)))

print('Connections OK')

thread = QThread()
worker = RewriteWorker('text', 'test content for rewrite', {}, signals)
worker.moveToThread(thread)

thread.started.connect(lambda: worker.run())
thread.finished.connect(lambda: print('Thread finished'))

print('Starting thread...')
thread.start()

time.sleep(2)
thread.wait(5000)

print(f'Results collected: {len(results)} events')
for r in results[:10]:
    print(f'  {r}')
print('Test complete')
