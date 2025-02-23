from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# In-memory storage
users = {
    1: {"id": 1, "name": "John Doe", "email": "john@example.com"},
    2: {"id": 2, "name": "Jane Smith", "email": "jane@example.com"}
}

orders = {
    1: {"id": 1, "user_id": 1, "items": ["item1"], "total": 100, "status": "pending"},
    2: {"id": 2, "user_id": 2, "items": ["item2"], "total": 200, "status": "completed"}
}

# User APIs
@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify(list(users.values()))

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = users.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json()
    
    # Validate required fields
    if not all(key in data for key in ["name", "email"]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Create new user
    new_id = max(users.keys()) + 1 if users else 1
    new_user = {
        "id": new_id,
        "name": data["name"],
        "email": data["email"]
    }
    users[new_id] = new_user
    return jsonify(new_user), 201

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    if user_id not in users:
        return jsonify({"error": "User not found"}), 404
    
    data = request.get_json()
    users[user_id].update({
        "name": data.get("name", users[user_id]["name"]),
        "email": data.get("email", users[user_id]["email"])
    })
    return jsonify(users[user_id])

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if user_id not in users:
        return jsonify({"error": "User not found"}), 404
    del users[user_id]
    return "", 204

# Order APIs
@app.route('/api/orders', methods=['GET'])
def get_orders():
    return jsonify(list(orders.values()))

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order)

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    
    # Validate required fields
    if not all(key in data for key in ["user_id", "items", "total"]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Validate user exists
    if data["user_id"] not in users:
        return jsonify({"error": "User not found"}), 404
    
    # Create new order
    new_id = max(orders.keys()) + 1 if orders else 1
    new_order = {
        "id": new_id,
        "user_id": data["user_id"],
        "items": data["items"],
        "total": data["total"],
        "status": "pending"
    }
    orders[new_id] = new_order
    return jsonify(new_order), 201

@app.route('/api/orders/<int:order_id>/status', methods=['PATCH'])
def update_order_status(order_id):
    if order_id not in orders:
        return jsonify({"error": "Order not found"}), 404
    
    data = request.get_json()
    if "status" not in data:
        return jsonify({"error": "Status field is required"}), 400
        
    orders[order_id]["status"] = data["status"]
    return jsonify(orders[order_id])

if __name__ == "__main__":
    app.run(debug=True, port=5000)