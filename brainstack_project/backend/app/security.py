import os, time, uuid, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Header
pwd=CryptContext(schemes=['bcrypt'],deprecated='auto')
SECRET=os.getenv('JWT_SECRET','CHANGE-ME-BEFORE-DEPLOYMENT-USE-A-LONG-RANDOM-SECRET')
def hash_password(p): return pwd.hash(p)
def verify_password(p,h): return pwd.verify(p,h)
def token_for(user): return jwt.encode({'sub':str(user['id']),'role':user['role'],'jti':str(uuid.uuid4()),'exp':int(time.time())+86400},SECRET,algorithm='HS256')
def current_user(authorization: str|None=Header(default=None)):
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401,'Authentication required')
    try:return jwt.decode(authorization[7:],SECRET,algorithms=['HS256'])
    except Exception: raise HTTPException(401,'Invalid or expired token')
def admin_user(user= None):
    if not user or user.get('role')!='admin': raise HTTPException(403,'Administrator access required')
    return user
