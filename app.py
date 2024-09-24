from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

users = [
    {"id": 1, "name": "test1"},
    {"id": 2, "name": "test2"}
]

@app.route('/', methods=['GET'])
def hello():
    return jsonify({"message": "hello"})
@app.route('/users/<int:user_id>/orders', methods=['GET'])
def get_user_orders(user_id):
    # Call the order-service using HTTPS
    order_service_url = f'https://order-service.default.svc.cluster.local:5000/orders?user_id={user_id}'
    
    # Disable SSL verification for internal communication (only in internal trusted networks)
    response = requests.get(order_service_url, verify=False)

    if response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify({'error': 'Failed to retrieve orders'}), response.status_code

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80)
