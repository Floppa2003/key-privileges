"""Disposable installed Chrome for the explicitly configured public source.

The caller supplies Xvfb/DISPLAY. Never attach to a user profile or reuse cookies.
"""
from __future__ import annotations
import asyncio
import os
import shutil
import signal
import subprocess
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path


@asynccontextmanager
async def installed_chrome():
    from playwright.async_api import async_playwright
    executable=shutil.which('google-chrome') or shutil.which('google-chrome-stable')
    if not executable:raise RuntimeError('installed_chrome_missing')
    if not os.environ.get('DISPLAY'):raise RuntimeError('installed_chrome_display_missing')
    proc=None;browser=None
    async with async_playwright() as p:
        with tempfile.TemporaryDirectory(prefix='loyalty-chrome-') as profile:
            try:
                proc=subprocess.Popen([executable,f'--user-data-dir={profile}',
                    '--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
                    '--no-first-run','--no-default-browser-check','--no-sandbox',
                    '--lang=ru-RU','--window-size=1365,900','about:blank'],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                port_file=Path(profile)/'DevToolsActivePort';deadline=time.monotonic()+35
                while time.monotonic()<deadline and proc.poll() is None:
                    if port_file.exists():
                        lines=port_file.read_text().splitlines()
                        if lines and lines[0].isdigit() and 0<int(lines[0])<65536:break
                    await asyncio.sleep(.2)
                else:raise RuntimeError('installed_chrome_startup_timeout')
                browser=await p.chromium.connect_over_cdp('http://127.0.0.1:'+lines[0],timeout=10000)
                context=browser.contexts[0]
                page=await asyncio.wait_for(context.new_page(),10)
                # Reject an unresponsive renderer before blaming the remote source.
                if await asyncio.wait_for(page.evaluate('1 + 1'),5)!=2:
                    raise RuntimeError('installed_chrome_renderer_control_failed')
                page.set_default_timeout(8000)
                yield context,page
            finally:
                if browser:
                    try:await asyncio.wait_for(browser.close(),3)
                    except Exception:pass
                if proc and proc.poll() is None:
                    os.killpg(proc.pid,signal.SIGTERM)
                    try:await asyncio.to_thread(proc.wait,timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid,signal.SIGKILL)
                        await asyncio.to_thread(proc.wait,timeout=3)
