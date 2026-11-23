from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)
def test_health_and_catalog():
    h=client.get('/api/health'); assert h.status_code==200; assert h.json()['books']>=200
    b=client.get('/api/books?limit=5'); assert b.status_code==200; assert len(b.json()['items'])==5
def test_guest_session():
    r=client.post('/api/auth/guest',json={}); assert r.status_code==200; assert r.json()['guest_id']
def test_ai_catalog_tools():
    r=client.get('/api/ai/tools/search_books',params={'q':'adventure'}); assert r.status_code==200
