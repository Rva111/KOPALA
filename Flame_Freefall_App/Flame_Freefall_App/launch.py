"""Run the app locally; the key stays in this Python process, never the browser."""
import os, sys, threading, webbrowser
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    os.chdir(root)
    from assistant import api_key
    try: api_key()
    except RuntimeError:
        # Optional local file picker for the private key file already downloaded.
        print('Select your existing private .env.local file. Cancel to use local comparisons without AI.')
        window=None
        try:
            import tkinter as tk
            from tkinter import filedialog
            window=tk.Tk();window.withdraw();window.attributes('-topmost',True)
            selected=filedialog.askopenfilename(title='Select your existing .env.local file',initialdir=str(Path.home()/'Downloads'))
            if selected:os.environ['FLAME_ENV_FILE']=selected
        except Exception:
            print('File picker unavailable. Place .env.local in this app folder to enable AI.')
        finally:
            if window is not None:window.destroy()
    port=int(os.getenv('PORT','8765'))
    url=f'http://127.0.0.1:{port}'
    print(f'Flame / Freefall is opening at {url}. Keep this window open. Ctrl+C stops it.')
    threading.Timer(1.5,lambda:webbrowser.open(url)).start()
    import uvicorn
    uvicorn.run('server:app',host='127.0.0.1',port=port,access_log=False)

if __name__=='__main__':main()
