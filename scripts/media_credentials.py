"""Read user-authorized private media credentials without shell evaluation or logging."""
from __future__ import annotations
import json,os,stat
from pathlib import Path

ALLOWED=('STUDIO_API_KEY','DASHSCOPE_API_KEY')
PROVIDERS={'image':'STUDIO_API_KEY','studio':'STUDIO_API_KEY','audio':'DASHSCOPE_API_KEY','bailian':'DASHSCOPE_API_KEY'}

class CredentialConfigError(RuntimeError):
    pass

def config_path():
    override=os.environ.get('HISTORY_MEDIA_CREDENTIALS')
    return Path(override).expanduser() if override else Path.home()/'.config/history-video/credentials.env'

def load_file(path=None):
    path=Path(path) if path is not None else config_path()
    if not path.exists():return {}
    if path.is_symlink():raise CredentialConfigError('Credential config must be a regular private file, not a symlink')
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>65536:raise CredentialConfigError('Invalid credential config file')
    if hasattr(os,'getuid') and info.st_uid!=os.getuid():raise CredentialConfigError('Credential config has another owner')
    if info.st_mode & 0o077:raise CredentialConfigError('Credential config permissions must be 0600 or more restrictive')
    values={}
    for number,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):continue
        if '=' not in line:raise CredentialConfigError(f'Invalid assignment at line {number}')
        name,value=line.split('=',1);name=name.strip();value=value.strip()
        if name not in ALLOWED:raise CredentialConfigError(f'Unknown credential field at line {number}')
        if value and value[0] in '\"\'':
            if len(value)<2 or value[-1]!=value[0]:raise CredentialConfigError(f'Unclosed quote at line {number}')
            value=value[1:-1]
        if any(c.isspace() for c in value):raise CredentialConfigError(f'Unexpected whitespace at line {number}')
        if name in values:raise CredentialConfigError(f'Duplicate credential field at line {number}')
        values[name]=value
    return values

def get_key(provider, environ=None, path=None):
    name=PROVIDERS.get(provider,provider)
    if name not in ALLOWED:raise CredentialConfigError('Unknown credential provider')
    env=os.environ if environ is None else environ
    value=env.get(name,'').strip()
    return value or load_file(path).get(name,'')

def safe_status(path=None, environ=None):
    file=Path(path) if path is not None else config_path()
    env=os.environ if environ is None else environ
    values=load_file(file)
    return {'path':str(file),'exists':file.exists(),'permissions':oct(file.stat().st_mode&0o777) if file.exists() else None,
        'imageConfigured':bool(env.get('STUDIO_API_KEY') or values.get('STUDIO_API_KEY')),
        'audioConfigured':bool(env.get('DASHSCOPE_API_KEY') or values.get('DASHSCOPE_API_KEY')),
        'credentialValuesLogged':False}

if __name__=='__main__':
    try:print(json.dumps(safe_status(),ensure_ascii=False))
    except CredentialConfigError as exc:print(json.dumps({'error':str(exc),'credentialValuesLogged':False}));raise SystemExit(2)
