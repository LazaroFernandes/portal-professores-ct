"""Local live-data finance preview; isolated session/database, no scheduler.

Usage: .venv312/bin/python scripts/preview_finance.py --env /path/to/Nextfit/.env
Credentials stay server-side. Only finance and authentication routes are loaded.
"""
import argparse
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--env',required=True)
    parser.add_argument('--port',type=int,default=8003)
    parser.add_argument('--snapshot',help='Reuse an explicitly selected live capture for local UI validation')
    args=parser.parse_args()
    from dotenv import dotenv_values
    credentials=dotenv_values(args.env)
    for key in list(os.environ):
        if key.startswith(('NEXTFIT','DATABASE','PG','SESSION_','APP_PASSWORD','PROFESSOR_','COOKIE_')):
            os.environ.pop(key)
    for key in ('NEXTFIT_API_KEY','NEXTFIT_BASE_URL','NEXTFIT_API_VERSION','NEXTFIT_V2_TOKEN','NEXTFIT_V2_REFRESH_TOKEN','NEXTFIT_CODIGO_UNIDADE'):
        if credentials.get(key): os.environ[key]=credentials[key]
    private=ROOT/'.local-finance';private.mkdir(exist_ok=True,mode=0o700)
    os.environ.update(APP_ENV='development',COOKIE_SECURE='false',SESSION_SECRET=secrets.token_urlsafe(48),
        APP_PASSWORD=secrets.token_urlsafe(24),GYM_PRESENCE_DATABASE_PATH=str(private/'preview.sqlite'))
    import dotenv
    dotenv.load_dotenv=lambda *a,**kw:False
    from fastapi import FastAPI, HTTPException
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from backend.app.api import finance, auth
    from backend.app.core.security import create_session, COOKIE_NAME
    from backend.app.services import finance_service
    from concurrent.futures import ThreadPoolExecutor
    pool=ThreadPoolExecutor(max_workers=1)
    if args.snapshot:
        import time
        finance_service._cached=json.loads(Path(args.snapshot).read_text())
        finance_service._expires=time.monotonic()+900
    future=pool.submit(finance_service.source_snapshot)
    def ready(f):
        try:
            snapshot=f.result()
            (private/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False))
            (private/'snapshot.json').chmod(0o600)
            print('Snapshot financeiro completo: '+json.dumps(snapshot['quality']),flush=True)
        except Exception as e:
            print('Consulta financeira falhou: '+type(e).__name__,flush=True)
    future.add_done_callback(ready)
    app=FastAPI();app.include_router(auth.router);app.include_router(finance.router)
    token,_=create_session({'role':'admin','name':'Administrador'})
    (private/'browser-session.json').write_text(json.dumps({'name':COOKIE_NAME,'value':token,'domain':'127.0.0.1','path':'/','httpOnly':True,'sameSite':'Lax'}))
    (private/'browser-session.json').chmod(0o600)
    teacher,_=create_session({'role':'professor','name':'Anderson Da Silva Santos'})
    (private/'teacher-session.json').write_text(json.dumps({'name':COOKIE_NAME,'value':teacher,'domain':'127.0.0.1','path':'/','httpOnly':True,'sameSite':'Lax'}))
    (private/'teacher-session.json').chmod(0o600)
    # An unguessable local login link lets the owner inspect the preview.
    access=secrets.token_urlsafe(32)
    (private/'access-url.txt').write_text(f'http://127.0.0.1:{args.port}/preview-access/{access}')
    (private/'access-url.txt').chmod(0o600)
    @app.get('/preview-access/{key}')
    def enter(key:str):
        if not secrets.compare_digest(key,access): raise HTTPException(404)
        from fastapi.responses import RedirectResponse
        result=RedirectResponse('/admin/financeiro')
        result.set_cookie(COOKIE_NAME,token,httponly=True,samesite='lax')
        return result
    app.mount('/assets',StaticFiles(directory=ROOT/'frontend/dist/assets'),name='assets')
    @app.get('/{path:path}')
    def frontend(path:str):
        if path.startswith('api/'): raise HTTPException(404)
        return FileResponse(ROOT/'frontend/dist/index.html')
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=args.port,lifespan='off')
