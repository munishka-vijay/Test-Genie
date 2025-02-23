import pytest
import requests
import json
import re

# Configuration
BASE_URL = "http://127.0.0.1:5000"
HEADERS = {"Content-Type": "application/json"}

def validate_response(response_data: dict, expected_data: dict) -> bool:
    """Helper function to validate response data against expected data."""
    for key, value in expected_data.items():
        if key not in response_data:
            return False
        if value != "*" and response_data[key] != value:
            return False
    return True

class TestUsers:

    def test_list_users(self):
        """Get list of users"""
        expected_status = 200  # Define expected status inside the function
        url = f"{BASE_URL}/api/users"
        response = requests.get(url, headers=HEADERS)

        # Verify status code
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"

        # Verify response content
        response_data = response.json()
        expected_data = {
            "id": "*",
            "name": "*",
            "email": "*"
}

        if response.status_code != 204:  # Skip validation for no-content responses
            assert validate_response(response_data, expected_data), (
                f"Response data does not match expected. Got: {response_data}"
            )

    def test_create_valid_user(self):
        """Create user with valid data"""
        expected_status = 201  # Define expected status inside the function
        url = f"{BASE_URL}/api/users"
        response = requests.post(url, json={
            "name": "Alice",
            "email": "alice@example.com"
}, headers=HEADERS)

        # Verify status code
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"

        # Verify response content
        response_data = response.json()
        expected_data = {
            "id": "*",
            "name": "Alice",
            "email": "alice@example.com"
}

        if response.status_code != 204:  # Skip validation for no-content responses
            assert validate_response(response_data, expected_data), (
                f"Response data does not match expected. Got: {response_data}"
            )

    def test_create_invalid_user(self):
        """Create user with missing email"""
        expected_status = 400  # Define expected status inside the function
        url = f"{BASE_URL}/api/users"
        response = requests.post(url, json={
            "name": "Alice"
}, headers=HEADERS)

        # Verify status code
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"

        # Verify response content
        response_data = response.json()
        expected_data = {
            "error": "Missing required fields"
}

        if response.status_code != 204:  # Skip validation for no-content responses
            assert validate_response(response_data, expected_data), (
                f"Response data does not match expected. Got: {response_data}"
            )

    def test_get_valid_user(self):
        """Get existing user"""
        expected_status = 200  # Define expected status inside the function
        url = f"{BASE_URL}/api/users/1"
        response = requests.get(url, headers=HEADERS)

        # Verify status code
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"

        # Verify response content
        response_data = response.json()
        expected_data = {
            "id": 1,
            "name": "*",
            "email": "*"
}

        if response.status_code != 204:  # Skip validation for no-content responses
            assert validate_response(response_data, expected_data), (
                f"Response data does not match expected. Got: {response_data}"
            )

    def test_get_invalid_user(self):
        """Get non-existent user"""
        expected_status = 404  # Define expected status inside the function
        url = f"{BASE_URL}/api/users/999"
        response = requests.get(url, headers=HEADERS)

        # Verify status code
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"

        # Verify response content
        response_data = response.json()
        expected_data = {
            "error": "User not found"
}

        if response.status_code != 204:  # Skip validation for no-content responses
            assert validate_response(response_data, expected_data), (
                f"Response data does not match expected. Got: {response_data}"
            )

    def test_update_user(self):
        """Update user name"""
        expected_status = 200  # Define expected status inside the function
        url = f"{BASE_URL}/api/users/1"
        response = requests.put(url, json={
            "name": "Updated Name"
}, headers=HEADERS)

        # Verify status code
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"

        # Verify response content
        response_data = response.json()
        expected_data = {
            "id": 1,
            "name": "Updated Name"
}

        if response.status_code != 204:  # Skip validation for no-content responses
            assert validate_response(response_data, expected_data), (
                f"Response data does not match expected. Got: {response_data}"
            )

    def test_delete_user(self):
        """Delete existing user"""
        expected_status = 204  # Define expected status inside the function
        url = f"{BASE_URL}/api/users/1"
        response = requests.delete(url, headers=HEADERS)

        # Verify status code
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"

class TestOrders:

    def test_create_valid_order(self):
        """Create valid order"""
        expected_status = 201  # Define expected status inside the function
        url = f"{BASE_URL}/api/orders"
        response = requests.post(url, json={
            "user_id": 1,
            "items": [
                        "item1"
            ],
            "total": 50
}, headers=HEADERS)

        # Verify status code
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"

        # Verify response content
        response_data = response.json()
        expected_data = {
            "id": "*",
            "status": "pending"
}

        if response.status_code != 204:  # Skip validation for no-content responses
            assert validate_response(response_data, expected_data), (
                f"Response data does not match expected. Got: {response_data}"
            )

    def test_update_status(self):
        """Update order status"""
        expected_status = 200  # Define expected status inside the function
        url = f"{BASE_URL}/api/orders/1/status"
        response = requests.patch(url, json={
            "status": "completed"
}, headers=HEADERS)

        # Verify status code
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"

        # Verify response content
        response_data = response.json()
        expected_data = {
            "id": 1,
            "status": "completed"
}

        if response.status_code != 204:  # Skip validation for no-content responses
            assert validate_response(response_data, expected_data), (
                f"Response data does not match expected. Got: {response_data}"
            )