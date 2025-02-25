# sample_apis.py
from fastapi import FastAPI, HTTPException, Header, Query, Depends, status
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import uvicorn
import uuid
import time
from datetime import datetime

app = FastAPI(
    title="Sample APIs for Testing",
    description="A collection of sample APIs to test the API Testing Agent",
    version="1.0.0"
)

# ---------- Sample Data ----------
users_db = [
    {"id": 1, "username": "john_doe", "email": "john@example.com", "active": True},
    {"id": 2, "username": "jane_smith", "email": "jane@example.com", "active": True},
    {"id": 3, "username": "bob_johnson", "email": "bob@example.com", "active": False}
]

products_db = [
    {"id": 1, "name": "Laptop", "price": 999.99, "stock": 50},
    {"id": 2, "name": "Smartphone", "price": 499.99, "stock": 100},
    {"id": 3, "name": "Headphones", "price": 79.99, "stock": 200}
]

orders_db = []

# ---------- Models ----------
class User(BaseModel):
    id: int
    username: str
    email: str
    active: bool

class UserCreate(BaseModel):
    username: str
    email: str
    
    @validator('email')
    def email_must_contain_at(cls, v):
        if '@' not in v:
            raise ValueError('email must contain @')
        return v

class Product(BaseModel):
    id: int
    name: str
    price: float
    stock: int

class OrderItem(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)

class OrderCreate(BaseModel):
    user_id: int
    items: List[OrderItem]

class Order(BaseModel):
    id: str
    user_id: int
    items: List[OrderItem]
    total: float
    created_at: str

# ---------- Dependencies ----------
def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != "valid_api_key":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return x_api_key

def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication"
        )
    
    token = authorization.replace("Bearer ", "")
    if token != "valid_token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return token

# ---------- Endpoints ----------
@app.get("/")
def read_root():
    return {"message": "Welcome to the Sample API"}

# ----- User Endpoints -----
@app.get("/users", response_model=List[User], tags=["Users"])
def get_users(
    active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    if skip > len(users_db):
        return []
    
    filtered = users_db
    if active is not None:
        filtered = [user for user in users_db if user["active"] == active]
        
    return filtered[skip:skip+limit]

@app.get("/users/{user_id}", response_model=User, tags=["Users"])
def get_user(user_id: int):
    for user in users_db:
        if user["id"] == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")

@app.post("/users", response_model=User, status_code=201, tags=["Users"])
def create_user(user: UserCreate, api_key: str = Depends(verify_api_key)):
    # Check if username already exists
    if any(u["username"] == user.username for u in users_db):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Create new user
    new_user = {
        "id": len(users_db) + 1,
        "username": user.username,
        "email": user.email,
        "active": True
    }
    users_db.append(new_user)
    return new_user

@app.put("/users/{user_id}", response_model=User, tags=["Users"])
def update_user(
    user_id: int, 
    user: UserCreate, 
    token: str = Depends(verify_token)
):
    for i, existing_user in enumerate(users_db):
        if existing_user["id"] == user_id:
            users_db[i].update({
                "username": user.username,
                "email": user.email
            })
            return users_db[i]
    raise HTTPException(status_code=404, detail="User not found")

@app.delete("/users/{user_id}", tags=["Users"])
def delete_user(
    user_id: int, 
    token: str = Depends(verify_token)
):
    for i, user in enumerate(users_db):
        if user["id"] == user_id:
            del users_db[i]
            return {"message": "User deleted"}
    raise HTTPException(status_code=404, detail="User not found")

# ----- Product Endpoints -----
@app.get("/products", response_model=List[Product], tags=["Products"])
def get_products(
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None
):
    filtered = products_db
    
    if min_price is not None:
        filtered = [p for p in filtered if p["price"] >= min_price]
    
    if max_price is not None:
        filtered = [p for p in filtered if p["price"] <= max_price]
    
    if in_stock is not None:
        filtered = [p for p in filtered if (p["stock"] > 0) == in_stock]
        
    return filtered

@app.get("/products/{product_id}", response_model=Product, tags=["Products"])
def get_product(product_id: int):
    for product in products_db:
        if product["id"] == product_id:
            return product
    raise HTTPException(status_code=404, detail="Product not found")

# ----- Order Endpoints -----
@app.post("/orders", response_model=Order, status_code=201, tags=["Orders"])
def create_order(
    order: OrderCreate,
    token: str = Depends(verify_token)
):
    # Verify user exists
    user_exists = any(u["id"] == order.user_id for u in users_db)
    if not user_exists:
        raise HTTPException(status_code=400, detail="User not found")
    
    # Verify products exist and are in stock
    total = 0
    for item in order.items:
        product = next((p for p in products_db if p["id"] == item.product_id), None)
        
        if not product:
            raise HTTPException(status_code=400, detail=f"Product {item.product_id} not found")
        
        if product["stock"] < item.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"Not enough stock for product {item.product_id}. Requested: {item.quantity}, Available: {product['stock']}"
            )
            
        total += product["price"] * item.quantity
    
    # Create order
    new_order = {
        "id": str(uuid.uuid4()),
        "user_id": order.user_id,
        "items": [item.dict() for item in order.items],
        "total": round(total, 2),
        "created_at": datetime.now().isoformat()
    }
    
    orders_db.append(new_order)
    return new_order

@app.get("/orders", response_model=List[Order], tags=["Orders"])
def get_orders(token: str = Depends(verify_token)):
    return orders_db

@app.get("/orders/{order_id}", response_model=Order, tags=["Orders"])
def get_order(order_id: str, token: str = Depends(verify_token)):
    for order in orders_db:
        if order["id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail="Order not found")

# ----- Health Check Endpoint -----
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": app.version
    }

# ----- Error Simulation Endpoints -----
@app.get("/error/timeout", tags=["Errors"])
def simulate_timeout():
    time.sleep(30)  # Sleep for 30 seconds to simulate timeout
    return {"message": "This response took a long time"}

@app.get("/error/500", tags=["Errors"])
def simulate_server_error():
    raise HTTPException(status_code=500, detail="Simulated server error")

@app.get("/error/rate-limit", tags=["Errors"])
def simulate_rate_limit():
    raise HTTPException(
        status_code=429,
        detail="Rate limit exceeded",
        headers={"Retry-After": "60"}
    )

# ---------- OpenAPI Specification Endpoint ----------
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_json():
    return app.openapi()

if __name__ == "__main__":
    uvicorn.run("sample_apis:app", host="0.0.0.0", port=8000, reload=True)