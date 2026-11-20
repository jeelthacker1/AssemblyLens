"""Create local credentials without printing secrets or overwriting an existing .env."""
import json,secrets
from pathlib import Path
path=Path('.env')
if path.exists(): raise SystemExit('.env already exists; left unchanged')
values={'POSTGRES_PASSWORD':secrets.token_hex(24),'S3_ACCESS_KEY':'assemblylens','S3_SECRET_KEY':secrets.token_hex(24),'CLICKHOUSE_PASSWORD':secrets.token_hex(24),'DEMO_MODE':'1','ENABLE_OUTBOX':'0','API_KEYS_JSON':json.dumps({secrets.token_hex(32):{'tenant':'factory-a','user':'administrator','role':'admin'}},separators=(',',':')),'CORS_ORIGINS':'http://localhost:3010','NEXT_PUBLIC_API_URL':'http://localhost:8010'}
path.write_text('\n'.join(k+'='+v for k,v in values.items())+'\n')
print('Created .env with random local credentials. Local demo key: demo-admin. Disable DEMO_MODE before exposing the API.')
