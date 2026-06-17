from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import secrets
from database import SessionLocal, User, Dish, Order

# ------------------------------------------------------------
# Настройка приложения
# ------------------------------------------------------------
app = FastAPI(title="Canteen System", description="Веб-система для столовой роддома")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

security = HTTPBearer()
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    credentials_exception = HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception

# ------------------------------------------------------------
# API
# ------------------------------------------------------------
@app.post("/register")
def register(full_name: str, password: str, role: str = "patient", diet_type: str = "normal", db: Session = Depends(get_db)):
    hashed = hash_password(password)
    user = User(full_name=full_name, hashed_password=hashed, role=role, diet_type=diet_type)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User created", "user_id": user.id}

@app.post("/login")
def login(full_name: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.full_name == full_name).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token({"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/dishes")
def get_dishes(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    dishes = db.query(Dish).all()
    if current_user.role != "patient":
        return dishes
    user_diet = current_user.diet_type if current_user.diet_type else "normal"
    filtered = []
    for d in dishes:
        allowed = d.allowed_diets if d.allowed_diets else "normal,diabetic,allergy"
        if user_diet in allowed.split(','):
            filtered.append(d)
    return filtered

@app.post("/orders")
def create_order(dish_ids: list[int], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    qr_token = secrets.token_urlsafe(32)
    new_order = Order(user_id=current_user.id, qr_token=qr_token, status="created")
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return {"order_id": new_order.id, "qr_token": qr_token}

@app.get("/my_orders")
def get_my_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    orders = db.query(Order).filter(Order.user_id == current_user.id).all()
    return orders

@app.get("/kitchen/orders")
def get_all_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["kitchen", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return db.query(Order).all()

@app.put("/kitchen/orders/{order_id}/status")
def update_order_status(order_id: int, status: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["kitchen", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if status == "delivered":
        db.delete(order)
        db.commit()
        return {"message": "Order delivered and removed"}
    else:
        order.status = status
        db.commit()
        return {"message": "Status updated"}

@app.delete("/kitchen/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["kitchen", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(order)
    db.commit()
    return {"message": "Order deleted"}

@app.post("/kitchen/verify-qr")
def verify_qr(qr_token: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["kitchen", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    order = db.query(Order).filter(Order.qr_token == qr_token).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(order)
    db.commit()
    return {"message": "Order delivered and removed", "order_id": order.id}

# ------------------------------------------------------------
# Веб-страницы (с кодировкой UTF-8)
# ------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Вход</title>
<style>
body{font-family:Arial;background:#f0f2f5;padding:20px}
.container{max-width:400px;margin:50px auto;background:#fff;padding:30px;border-radius:8px}
input,button{width:100%;padding:10px;margin:10px 0}
button{background:#3498db;color:#fff;border:none;cursor:pointer}
</style>
</head>
<body>
<div class=container>
<h1>🍽️ Столовая роддома</h1>
<form id=loginForm>
<input type=text id=full_name placeholder="Полное имя" required>
<input type=password id=password placeholder=Пароль required>
<button>Войти</button>
</form>
<a href="/register_page">Регистрация</a>
<div id=message></div>
</div>
<script>
localStorage.removeItem('access_token');
document.getElementById('loginForm').onsubmit=async(e)=>{
    e.preventDefault();
    const r=await fetch(`/login?full_name=${encodeURIComponent(full_name.value)}&password=${encodeURIComponent(password.value)}`,{method:'POST'});
    if(r.ok){
        const d=await r.json();
        localStorage.setItem('access_token',d.access_token);
        window.location.href='/menu';
    }else message.innerText='Ошибка входа';
};
</script>
</body></html>""", media_type="text/html; charset=utf-8")

@app.get("/register_page", response_class=HTMLResponse)
async def register_page():
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Регистрация</title>
<style>
body{font-family:Arial;background:#f0f2f5;padding:20px}
.container{max-width:400px;margin:50px auto;background:#fff;padding:30px;border-radius:8px}
input,select,button{width:100%;padding:10px;margin:10px 0}
</style>
</head>
<body>
<div class=container>
<h2>Регистрация</h2>
<form id=registerForm>
<input type=text id=full_name placeholder="Полное имя" required>
<input type=password id=password placeholder=Пароль required>
<select id=role>
<option value=patient>Пациент</option>
<option value=staff>Сотрудник</option>
<option value=kitchen>Кухня</option>
</select>
<select id=diet_type>
<option value=normal>Обычное питание</option>
<option value=diabetic>Диабет (без сахара)</option>
<option value=allergy>Аллергия</option>
</select>
<button>Зарегистрироваться</button>
</form>
<a href="/">Назад</a>
<div id=message></div>
</div>
<script>
document.getElementById('registerForm').onsubmit=async(e)=>{
    e.preventDefault();
    const full_name=document.getElementById('full_name').value;
    const password=document.getElementById('password').value;
    const role=document.getElementById('role').value;
    const diet_type=document.getElementById('diet_type').value;
    const res=await fetch(`/register?full_name=${encodeURIComponent(full_name)}&password=${encodeURIComponent(password)}&role=${role}&diet_type=${diet_type}`,{method:'POST'});
    if(res.ok) window.location.href='/';
    else message.innerText='Ошибка';
};
</script>
</body></html>""", media_type="text/html; charset=utf-8")

@app.get("/menu", response_class=HTMLResponse)
async def menu_page():
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Меню</title>
<style>
body{font-family:Arial;background:#f8f9fa;padding:20px}
.container{max-width:800px;margin:auto;background:#fff;padding:20px;border-radius:8px}
.dish{border:1px solid #ddd;padding:10px;margin:10px 0}
button{padding:5px 10px;margin:5px;cursor:pointer}
.logout{background:#dc3545;color:white}
</style>
</head>
<body>
<div class=container>
<h1>🍴 Меню сегодня</h1>
<div id=dishes></div>
<div id=cart>Выбрано блюд: 0</div>
<button id=orderBtn style="background:#27ae60;color:white;width:100%">Оформить заказ</button>
<div><a href="/orders">Мои заказы</a> <a href="/kitchen">Панель кухни</a> <button id=logoutBtn class=logout>Выйти</button></div>
<div id=result></div>
</div>
<script>
const token=localStorage.getItem('access_token');
if(!token) window.location.href='/';
let selected=[];
async function load(){
    const res=await fetch('/dishes',{headers:{'Authorization':`Bearer ${token}`}});
    if(!res.ok){window.location.href='/';return;}
    const dishes=await res.json();
    const container=document.getElementById('dishes');
    if(!dishes.length) container.innerHTML='<p>Меню пусто. Добавьте блюда через SQL.</p>';
    else container.innerHTML=dishes.map(d=>`<div class=dish><strong>${escape(d.name)}</strong><br>${escape(d.description||'')}<br><button onclick="add(${d.id})">Выбрать</button></div>`).join('');
}
function escape(s){if(!s)return '';return s.replace(/[&<>]/g,function(m){if(m==='&')return'&amp;';if(m==='<')return'&lt;';if(m==='>')return'&gt;';return m;});}
window.add=id=>{selected.push(id);document.getElementById('cart').innerText=`Выбрано блюд: ${selected.length}`;};
document.getElementById('orderBtn').onclick=async()=>{
    if(!selected.length){alert('Выберите блюдо');return;}
    const res=await fetch('/orders',{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${token}`},body:JSON.stringify(selected)});
    const data=await res.json();
    const qr=`https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${data.qr_token}`;
    document.getElementById('result').innerHTML=`<strong>Заказ оформлен!</strong><br>Токен: ${data.qr_token}<br><img src="${qr}">`;
    selected=[];
    document.getElementById('cart').innerText='Выбрано блюд: 0';
};
document.getElementById('logoutBtn').onclick=()=>{localStorage.removeItem('access_token');window.location.href='/';};
load();
</script>
</body></html>""", media_type="text/html; charset=utf-8")

@app.get("/orders", response_class=HTMLResponse)
async def orders_page():
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Мои заказы</title>
<style>
body{font-family:Arial;background:#f8f9fa;padding:20px}
.container{max-width:600px;margin:auto;background:#fff;padding:20px;border-radius:8px}
.order{border-bottom:1px solid #ddd;padding:10px 0}
.logout{background:#dc3545;color:white}
</style>
</head>
<body>
<div class=container>
<h1>Ваши заказы</h1>
<div id=orders></div>
<div><a href="/menu">← Назад</a> <a href="/kitchen">Панель кухни</a> <button id=logoutBtn class=logout>Выйти</button></div>
</div>
<script>
const token=localStorage.getItem('access_token');
if(!token) window.location.href='/';
async function load(){
    const res=await fetch('/my_orders',{headers:{'Authorization':`Bearer ${token}`}});
    const orders=await res.json();
    const container=document.getElementById('orders');
    if(!orders.length) container.innerHTML='<p>Пока нет заказов.</p>';
    else container.innerHTML=orders.map(o=>`<div class=order>Заказ №${o.id} — статус: <strong>${o.status||'создан'}</strong><br>QR: ${o.qr_token}</div>`).join('');
}
load();
document.getElementById('logoutBtn').onclick=()=>{localStorage.removeItem('access_token');window.location.href='/';};
</script>
</body></html>""", media_type="text/html; charset=utf-8")

@app.get("/kitchen", response_class=HTMLResponse)
async def kitchen_page():
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Кухня</title>
<style>
body{font-family:Arial;background:#f8f9fa;padding:20px}
.container{max-width:1000px;margin:auto;background:#fff;padding:20px;border-radius:8px}
.order{border:1px solid #ddd;padding:15px;margin:10px 0}
.qr-scan{background:#e9ecef;padding:15px;border-radius:5px;margin-bottom:20px}
button{margin:5px;padding:5px 10px}
.logout{background:#dc3545;color:white}
</style>
</head>
<body>
<div class=container>
<h1>👩‍🍳 Кухня: управление заказами</h1>
<div class=qr-scan>
<h3>Подтвердить выдачу по QR-коду</h3>
<input type=text id=qrInput size=50 placeholder="Введите QR-токен">
<button id=scanBtn>Подтвердить выдачу</button>
<span id=scanResult></span>
</div>
<div id=orders></div>
<div><a href="/menu">Меню</a> <a href="/orders">Мои заказы</a> <button id=logoutBtn class=logout>Выйти</button></div>
</div>
<script>
const token=localStorage.getItem('access_token');
if(!token) window.location.href='/';
async function loadOrders(){
    const res=await fetch('/kitchen/orders',{headers:{'Authorization':`Bearer ${token}`}});
    if(res.status===403){document.getElementById('orders').innerHTML='<p>Нет прав доступа.</p>';return;}
    const orders=await res.json();
    const container=document.getElementById('orders');
    if(!orders.length){container.innerHTML='<p>Нет заказов</p>';return;}
    container.innerHTML=orders.map(o=>`<div class=order><strong>Заказ №${o.id}</strong>, пользователь: ${o.user_id}<br>Статус: <span id=status-${o.id}>${o.status||'created'}</span><br>QR: ${o.qr_token}<br>
        <button onclick="changeStatus(${o.id},'accepted')">Принять</button>
        <button onclick="changeStatus(${o.id},'cooking')">Готовить</button>
        <button onclick="changeStatus(${o.id},'ready')">Готово</button>
        <button onclick="changeStatus(${o.id},'delivered')">Выдать (удалить)</button>
        <button onclick="deleteOrder(${o.id})" style="background:#dc3545;color:white">Удалить</button>
    </div>`).join('');
}
window.changeStatus=async(orderId,newStatus)=>{
    const res=await fetch(`/kitchen/orders/${orderId}/status?status=${newStatus}`,{method:'PUT',headers:{'Authorization':`Bearer ${token}`}});
    if(res.ok){
        if(newStatus==='delivered') loadOrders();
        else document.getElementById(`status-${orderId}`).innerText=newStatus;
    }else alert('Ошибка');
};
window.deleteOrder=async(orderId)=>{
    if(!confirm('Удалить заказ?')) return;
    const res=await fetch(`/kitchen/orders/${orderId}`,{method:'DELETE',headers:{'Authorization':`Bearer ${token}`}});
    if(res.ok) loadOrders();
    else alert('Ошибка');
};
document.getElementById('scanBtn').onclick=async()=>{
    const qr=document.getElementById('qrInput').value;
    if(!qr){alert('Введите QR-токен');return;}
    const res=await fetch(`/kitchen/verify-qr?qr_token=${encodeURIComponent(qr)}`,{method:'POST',headers:{'Authorization':`Bearer ${token}`}});
    const data=await res.json();
    if(res.ok){document.getElementById('scanResult').innerHTML=`<span style="color:green;">✅ Заказ выдан</span>`;loadOrders();}
    else document.getElementById('scanResult').innerHTML=`<span style="color:red;">❌ ${data.detail||'Ошибка'}</span>`;
};
document.getElementById('logoutBtn').onclick=()=>{localStorage.removeItem('access_token');window.location.href='/';};
loadOrders();
setInterval(loadOrders,5000);
</script>
</body></html>""", media_type="text/html; charset=utf-8")