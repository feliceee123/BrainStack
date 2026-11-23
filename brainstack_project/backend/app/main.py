import os, time, secrets, hashlib, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from .db import connect, init_db
from .security import hash_password, verify_password, token_for, current_user

app=FastAPI(title='BrainStack E-Library API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','*').split(','),allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
@app.on_event('startup')
def startup():
    init_db()
    email=os.getenv('ADMIN_EMAIL'); pw=os.getenv('ADMIN_PASSWORD')
    if email and pw:
        # Keep the configured administrator credentials in sync with the environment.
        # This also repairs an existing account whose password differs from .env.
        c=connect()
        c.execute("INSERT OR IGNORE INTO users(name,email,password_hash,role,verified) VALUES(?,?,?,?,1)",('Administrator',email.lower(),hash_password(pw),'admin'))
        c.execute("UPDATE users SET role='admin',verified=1,password_hash=? WHERE email=?",(hash_password(pw),email.lower()))
        c.commit(); c.close()
class Register(BaseModel): name:str=Field(min_length=2,max_length=100); email:EmailStr; password:str=Field(min_length=8,max_length=128)
class Login(BaseModel): email:EmailStr; password:str
class Verify(BaseModel): email:EmailStr; code:str=Field(min_length=6,max_length=6)
class Guest(BaseModel): guest_id:str|None=None
class AIRequest(BaseModel): message:str; conversation_id:int|None=None
class FavoriteConfirm(BaseModel): book_id:int; confirmed:bool

def brevo_send(email,code):
    key=os.getenv('BREVO_API_KEY'); sender=os.getenv('BREVO_SENDER_EMAIL')
    if not key or not sender: raise HTTPException(503,'Email verification is not configured. Set BREVO_API_KEY and BREVO_SENDER_EMAIL.')
    r=requests.post('https://api.brevo.com/v3/smtp/email',headers={'api-key':key,'accept':'application/json','content-type':'application/json'},json={'sender':{'name':os.getenv('BREVO_SENDER_NAME','BrainStack E-Library'),'email':sender},'to':[{'email':email}],'subject':'BrainStack verification code','htmlContent':f'<p>Your BrainStack verification code is <b>{code}</b>.</p><p>It expires in 5 minutes.</p>'},timeout=20)
    if r.status_code>=300: raise HTTPException(502,'Brevo could not send the verification email.')

def user_row(uid):
    c=connect(); row=c.execute('SELECT id,name,email,role,verified FROM users WHERE id=?',(uid,)).fetchone(); c.close(); return dict(row) if row else None
@app.get('/api/health')
def health():
    c=connect(); n=c.execute('SELECT COUNT(*) FROM books').fetchone()[0]; c.close(); return {'status':'ok','database':'connected','books':n}
@app.post('/api/auth/register')
def register(x:Register):
    email=x.email.lower(); code=f'{secrets.randbelow(1000000):06d}'; h=hash_password(x.password); ch=hashlib.sha256(code.encode()).hexdigest()
    c=connect(); exists=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
    if exists: c.close(); raise HTTPException(409,'Email is already registered.')
    c.execute('INSERT OR REPLACE INTO email_codes(email,name,password_hash,code_hash,expires_at,attempts) VALUES(?,?,?,?,?,0)',(email,x.name,h,ch,int(time.time())+300)); c.commit(); c.close()
    brevo_send(email,code); return {'message':'Verification code sent. Check your email.'}
@app.post('/api/auth/verify')
def verify(x:Verify):
    email=x.email.lower(); c=connect(); row=c.execute('SELECT * FROM email_codes WHERE email=?',(email,)).fetchone()
    if not row: c.close(); raise HTTPException(400,'No pending verification request.')
    if row['expires_at']<int(time.time()) or row['attempts']>=5: c.execute('DELETE FROM email_codes WHERE email=?',(email,)); c.commit(); c.close(); raise HTTPException(400,'Code expired or attempt limit reached. Register again.')
    if hashlib.sha256(x.code.encode()).hexdigest()!=row['code_hash']:
        c.execute('UPDATE email_codes SET attempts=attempts+1 WHERE email=?',(email,)); c.commit(); c.close(); raise HTTPException(400,'Incorrect verification code.')
    c.execute('INSERT INTO users(name,email,password_hash,verified) VALUES(?,?,?,1)',(row['name'],email,row['password_hash'])); uid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.execute('DELETE FROM email_codes WHERE email=?',(email,)); c.commit(); c.close(); u=user_row(uid); return {'access_token':token_for(u),'token_type':'bearer','user':u}
@app.post('/api/auth/login')
def login(x:Login):
    c=connect(); u=c.execute('SELECT * FROM users WHERE email=?',(x.email.lower(),)).fetchone(); c.close()
    if not u or not verify_password(x.password,u['password_hash']): raise HTTPException(401,'Invalid email or password.')
    if not u['verified']: raise HTTPException(403,'Verify your email before logging in.')
    d=dict(u); return {'access_token':token_for(d),'token_type':'bearer','user':user_row(d['id'])}
@app.post('/api/auth/guest')
def guest(x:Guest): return {'guest_id':x.guest_id or secrets.token_urlsafe(24),'mode':'guest'}
@app.get('/api/auth/me')
def me(u=Depends(current_user)): return user_row(int(u['sub']))
@app.get('/api/books')
def books(q:str='',category:str='',limit:int=Query(40,ge=1,le=100),offset:int=0):
    c=connect(); where=[]; args=[]
    if q: where.append('(title LIKE ? OR author LIKE ?)'); args += [f'%{q}%',f'%{q}%']
    if category: where.append('category=?'); args.append(category)
    w=(' WHERE '+' AND '.join(where)) if where else ''
    rows=c.execute('SELECT * FROM books'+w+' ORDER BY title LIMIT ? OFFSET ?',args+[limit,offset]).fetchall(); total=c.execute('SELECT COUNT(*) FROM books'+w,args).fetchone()[0]; cats=[r[0] for r in c.execute('SELECT DISTINCT category FROM books ORDER BY category')]; c.close(); return {'items':[dict(r) for r in rows],'total':total,'categories':cats}
@app.get('/api/books/{book_id}')
def book_detail(book_id:int):
    c=connect(); r=c.execute('SELECT * FROM books WHERE id=?',(book_id,)).fetchone(); c.close()
    if not r: raise HTTPException(404,'Book not found')
    return dict(r)
def enforce_download(book_id,user=None,guest_id=None):
    c=connect(); b=c.execute('SELECT * FROM books WHERE id=?',(book_id,)).fetchone()
    if not b: c.close(); raise HTTPException(404,'Book not found')
    if user:
        count=c.execute('SELECT COUNT(DISTINCT book_id) FROM downloads WHERE user_id=?',(user['sub'],)).fetchone()[0]
        exists=c.execute('SELECT 1 FROM downloads WHERE user_id=? AND book_id=?',(user['sub'],book_id)).fetchone()
        if not exists and count>=10: c.close(); raise HTTPException(429,'Registered users may download up to 10 unique books.')
        c.execute('INSERT OR IGNORE INTO downloads(user_id,book_id) VALUES(?,?)',(user['sub'],book_id))
    else:
        if not guest_id: c.close(); raise HTTPException(400,'Guest ID is required.')
        count=c.execute('SELECT COUNT(DISTINCT book_id) FROM downloads WHERE guest_id=?',(guest_id,)).fetchone()[0]
        exists=c.execute('SELECT 1 FROM downloads WHERE guest_id=? AND book_id=?',(guest_id,book_id)).fetchone()
        if not exists and count>=5: c.close(); raise HTTPException(429,'Guests may download up to 5 unique books per session.')
        c.execute('INSERT OR IGNORE INTO downloads(guest_id,book_id) VALUES(?,?)',(guest_id,book_id))
    c.commit(); c.close(); return b['download_url']
@app.post('/api/books/{book_id}/download')
def download(book_id:int,guest_id:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    user=None
    if authorization:
        user=current_user(authorization)
    url=enforce_download(book_id,user,guest_id if not user else None); return {'download_url':url,'message':'Download authorized.'}
@app.get('/api/favorites')
def favorites(u=Depends(current_user)):
    c=connect(); rows=c.execute('SELECT b.* FROM books b JOIN favorites f ON f.book_id=b.id WHERE f.user_id=? ORDER BY f.created_at DESC',(u['sub'],)).fetchall(); c.close(); return [dict(r) for r in rows]
@app.post('/api/favorites/{book_id}')
def add_favorite(book_id:int,u=Depends(current_user)):
    c=connect(); exists=c.execute('SELECT id FROM books WHERE id=?',(book_id,)).fetchone()
    if not exists: c.close(); raise HTTPException(404,'Book not found')
    c.execute('INSERT OR IGNORE INTO favorites(user_id,book_id) VALUES(?,?)',(u['sub'],book_id)); c.commit(); c.close(); return {'saved':True}
@app.delete('/api/favorites/{book_id}')
def remove_favorite(book_id:int,u=Depends(current_user)):
    c=connect(); c.execute('DELETE FROM favorites WHERE user_id=? AND book_id=?',(u['sub'],book_id)); c.commit(); c.close(); return {'saved':False}
@app.get('/api/downloads')
def download_history(u=Depends(current_user)):
    c=connect(); rows=c.execute('SELECT b.*,d.created_at AS downloaded_at FROM downloads d JOIN books b ON b.id=d.book_id WHERE d.user_id=? ORDER BY d.id DESC',(u['sub'],)).fetchall(); c.close(); return [dict(r) for r in rows]
def require_admin(u=Depends(current_user)):
    if u.get('role') != 'admin':
        raise HTTPException(403, 'Admin only')
    return u

@app.get('/api/admin/summary')
def admin_summary(u=Depends(require_admin)):
    c=connect()
    out={
        'books':c.execute('SELECT COUNT(*) FROM books').fetchone()[0],
        'users':c.execute("SELECT COUNT(*) FROM users WHERE role != 'admin'").fetchone()[0],
        'downloads':c.execute('SELECT COUNT(*) FROM downloads').fetchone()[0],
        'favorites':c.execute('SELECT COUNT(*) FROM favorites').fetchone()[0],
        'top_books':[dict(r) for r in c.execute('SELECT b.id,b.title,COUNT(d.id) downloads FROM books b LEFT JOIN downloads d ON b.id=d.book_id GROUP BY b.id ORDER BY downloads DESC,b.title LIMIT 8')]
    }
    c.close(); return out

@app.get('/api/admin/books')
def admin_books(q:str='',category:str='',u=Depends(require_admin)):
    c=connect(); where=[]; args=[]
    if q:
        where.append('(title LIKE ? OR author LIKE ?)'); args += [f'%{q}%',f'%{q}%']
    if category:
        where.append('category=?'); args.append(category)
    w=(' WHERE '+' AND '.join(where)) if where else ''
    rows=c.execute('SELECT * FROM books'+w+' ORDER BY title',args).fetchall()
    categories=[r[0] for r in c.execute('SELECT DISTINCT category FROM books ORDER BY category')]
    c.close(); return {'items':[dict(r) for r in rows],'categories':categories}

@app.post('/api/admin/books')
def create_book(data:dict,u=Depends(require_admin)):
    required=['title','author','category','license','download_url']
    missing=[k for k in required if not str(data.get(k,'')).strip()]
    if missing: raise HTTPException(422,'Missing required fields: '+', '.join(missing))
    c=connect()
    try:
        cur=c.execute('INSERT INTO books(title,author,category,description,license,download_url) VALUES(?,?,?,?,?,?)',(data['title'].strip(),data['author'].strip(),data['category'].strip(),data.get('description','').strip(),data['license'].strip(),data['download_url'].strip()))
        c.commit(); return {'id':cur.lastrowid,'message':'Book added.'}
    except Exception as e:
        c.rollback()
        if 'UNIQUE' in str(e): raise HTTPException(409,'This book and author already exist.')
        raise
    finally: c.close()

@app.put('/api/admin/books/{book_id}')
def update_book(book_id:int,data:dict,u=Depends(require_admin)):
    required=['title','author','category','license','download_url']
    missing=[k for k in required if not str(data.get(k,'')).strip()]
    if missing: raise HTTPException(422,'Missing required fields: '+', '.join(missing))
    c=connect(); exists=c.execute('SELECT id FROM books WHERE id=?',(book_id,)).fetchone()
    if not exists: c.close(); raise HTTPException(404,'Book not found.')
    try:
        c.execute('UPDATE books SET title=?,author=?,category=?,description=?,license=?,download_url=? WHERE id=?',(data['title'].strip(),data['author'].strip(),data['category'].strip(),data.get('description','').strip(),data['license'].strip(),data['download_url'].strip(),book_id))
        c.commit(); return {'message':'Book updated.'}
    except Exception as e:
        c.rollback()
        if 'UNIQUE' in str(e): raise HTTPException(409,'Another book with this title and author already exists.')
        raise
    finally: c.close()

@app.delete('/api/admin/books/{book_id}')
def delete_book(book_id:int,u=Depends(require_admin)):
    c=connect(); exists=c.execute('SELECT id FROM books WHERE id=?',(book_id,)).fetchone()
    if not exists: c.close(); raise HTTPException(404,'Book not found.')
    c.execute('DELETE FROM favorites WHERE book_id=?',(book_id,))
    c.execute('DELETE FROM downloads WHERE book_id=?',(book_id,))
    c.execute('DELETE FROM books WHERE id=?',(book_id,)); c.commit(); c.close()
    return {'message':'Book deleted.'}

@app.get('/api/admin/users')
def admin_users(q:str='',u=Depends(require_admin)):
    c=connect(); args=[]; w=''
    if q:
        w=' WHERE name LIKE ? OR email LIKE ?'; args=[f'%{q}%',f'%{q}%']
    rows=c.execute('SELECT id,name,email,role,verified,created_at FROM users'+w+' ORDER BY id DESC',args).fetchall(); c.close(); return [dict(r) for r in rows]

@app.get('/api/admin/analytics')
def admin_analytics(u=Depends(require_admin)):
    c=connect()
    daily=[dict(r) for r in c.execute("SELECT date(created_at) day,COUNT(*) downloads FROM downloads WHERE date(created_at)>=date('now','-6 days') GROUP BY date(created_at) ORDER BY day")]
    split=dict(c.execute("SELECT SUM(CASE WHEN user_id IS NULL THEN 1 ELSE 0 END) guests,SUM(CASE WHEN user_id IS NOT NULL THEN 1 ELSE 0 END) registered FROM downloads").fetchone())
    categories=[dict(r) for r in c.execute('SELECT category,COUNT(*) books FROM books GROUP BY category ORDER BY books DESC,category')]
    top=[dict(r) for r in c.execute('SELECT b.title,COUNT(d.id) downloads FROM books b LEFT JOIN downloads d ON b.id=d.book_id GROUP BY b.id ORDER BY downloads DESC,b.title LIMIT 10')]
    c.close()
    return {'daily_downloads':daily,'download_split':{k:(v or 0) for k,v in split.items()},'categories':categories,'top_books':top}

@app.get('/api/admin/ai-activity')
def admin_ai_activity(u=Depends(require_admin)):
    c=connect()
    conversations=c.execute('SELECT COUNT(*) FROM ai_conversations').fetchone()[0]
    messages=c.execute('SELECT COUNT(*) FROM ai_messages').fetchone()[0]
    recent=[dict(r) for r in c.execute('SELECT c.id,c.created_at,u.name,u.email,COUNT(m.id) messages FROM ai_conversations c LEFT JOIN users u ON u.id=c.user_id LEFT JOIN ai_messages m ON m.conversation_id=c.id GROUP BY c.id ORDER BY c.id DESC LIMIT 20')]
    c.close(); return {'conversations':conversations,'messages':messages,'recent':recent,'note':'Activity appears here when AI conversations are recorded by the application.'}

@app.get('/api/ai/tools/search_books')
def ai_search_books(q:str,category:str=''):
    c=connect(); rows=c.execute('SELECT id,title,author,category,description,license FROM books WHERE (title LIKE ? OR author LIKE ? OR category LIKE ?) AND (?='' OR category=?) LIMIT 10',(f'%{q}%',f'%{q}%',f'%{q}%',category,category)).fetchall(); c.close(); return [dict(r) for r in rows]
@app.get('/api/ai/tools/book_details/{book_id}')
def ai_book_details(book_id:int): return book_detail(book_id)
@app.post('/api/ai/tools/save_favorite')
def ai_save_favorite(x:FavoriteConfirm,u=Depends(current_user)):
    if not x.confirmed: raise HTTPException(400,'User confirmation is required.')
    return add_favorite(x.book_id,u)
@app.get('/api/config')
def public_config(): return {'elevenlabs_agent_id':os.getenv('ELEVENLABS_AGENT_ID','')}
@app.get('/api/ai/elevenlabs-signed-url')
def elevenlabs_signed_url(u=Depends(current_user)):
    key=os.getenv('ELEVENLABS_API_KEY'); agent=os.getenv('ELEVENLABS_AGENT_ID')
    if not key or not agent: raise HTTPException(503,'Configure ElevenLabs API key and Agent ID.')
    r=requests.get('https://api.elevenlabs.io/v1/convai/conversation/get_signed_url',params={'agent_id':agent},headers={'xi-api-key':key},timeout=20)
    if r.status_code>=300: raise HTTPException(502,'Unable to create ElevenLabs session.')
    return r.json()
WEB=Path(__file__).resolve().parents[2]/'web'
app.mount('/',StaticFiles(directory=WEB,html=True),name='web')
