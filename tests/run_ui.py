"""Run the DOM integration test with a disposable database and local Flask server."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='crop-ui-') as directory:
    env = dict(os.environ, CROP_TEST_DATABASE=str(Path(directory) / 'users.sqlite3'))
    code = "import os; from app import create_app; create_app({'DATABASE':os.environ['CROP_TEST_DATABASE'],'SECRET_KEY':'disposable-test-secret'}).run(port=5051)"
    server = subprocess.Popen([sys.executable, '-c', code], cwd=ROOT, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if server.poll() is not None:
                raise RuntimeError('Test server could not start on port 5051.')
            try:
                urllib.request.urlopen('http://127.0.0.1:5051/api/session', timeout=1)
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError('Test server did not become ready.')
        result = subprocess.run(['node', 'tests/test_ui.cjs'], cwd=ROOT)
        sys.exit(result.returncode)
    finally:
        server.terminate()
        server.wait(timeout=5)
