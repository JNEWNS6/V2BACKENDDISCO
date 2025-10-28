import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)

def require_api_key(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    expected = os.getenv("DISCO_API_KEY", "").strip()
    if not expected:
        return None
    if not creds or not creds.credentials or (creds.scheme or "").lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    if creds.credentials != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    return None
