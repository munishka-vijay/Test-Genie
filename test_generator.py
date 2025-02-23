import streamlit as st
import pandas as pd
import json
import requests
import time
import re

def extract_resource(endpoint):
    """Extracts the main resource from the API endpoint."""
    parts = re.split(r'[/?{}]', endpoint)  # Split by '/', '?', '{}'
    parts = [p for p in parts if p and not p.isdigit()]  # Remove empty & numeric parts
    return parts[1] if len(parts) > 1 else "General"  # Default if no clear resource

def generate_test_code(df, base_url):
    """Generate pytest test cases based on the CSV specifications."""
    test_code = f"""import pytest
import requests
import json
import re

# Configuration
BASE_URL = "{base_url}"
HEADERS = {{"Content-Type": "application/json"}}

def validate_response(response_data: dict, expected_data: dict) -> bool:
    \"\"\"Helper function to validate response data against expected data.\"\"\"
    for key, value in expected_data.items():
        if key not in response_data:
            return False
        if value != "*" and response_data[key] != value:
            return False
    return True
"""

    test_classes = {}  # Store test cases grouped by resource class

    for _, row in df.iterrows():
        endpoint = row['endpoint']
        method = row['method'].lower()
        test_case = row['test_case']
        description = row['description']
        expected_status = row['expected_status']

        # Extract class name from endpoint
        class_name = f"Test{extract_resource(endpoint).capitalize()}"

        # Ensure class exists in dictionary
        if class_name not in test_classes:
            test_classes[class_name] = []

        # Generate test method
        test_method = f"""
    def test_{test_case}(self):
        \"\"\"{description}\"\"\"
        expected_status = {expected_status}  # Define expected status inside the function
"""

        request_body = json.loads(row['request_body']) if pd.notna(row['request_body']) and row['request_body'].lower() != 'null' else None
        expected_response = json.loads(row['expected_response']) if pd.notna(row['expected_response']) and row['expected_response'].lower() != 'null' else None

        # Extract path parameters from the endpoint
        endpoint_path = endpoint
        path_params = re.findall(r"\{(.*?)\}", endpoint)  # Find placeholders like {id}

        if request_body:
            for key in path_params:
                if key in request_body:
                    endpoint_path = endpoint_path.replace(f"{{{key}}}", str(request_body.pop(key)))  # Replace in URL & remove from body

        test_method += f"        url = f\"{{BASE_URL}}{endpoint_path}\"\n"

        # Send request
        if request_body and method != "get":  # Only include body for non-GET requests
            test_method += f"        response = requests.{method}(url, json={json.dumps(request_body, indent=12)}, headers=HEADERS)\n"
        else:
            test_method += f"        response = requests.{method}(url, headers=HEADERS)\n"

        # Status code assertion
        test_method += f"""
        # Verify status code
        assert response.status_code == expected_status, f"Expected {{expected_status}}, got {{response.status_code}}"
"""

        # Response validation (if applicable)
        if expected_response:
            test_method += f"""
        # Verify response content
        response_data = response.json()
        expected_data = {json.dumps(expected_response, indent=12)}
        
        if response.status_code != 204:  # Skip validation for no-content responses
            assert validate_response(response_data, expected_data), (
                f"Response data does not match expected. Got: {{response_data}}"
            )
"""

        test_classes[class_name].append(test_method)

    # Combine all test classes
    for class_name, tests in test_classes.items():
        test_code += f"\nclass {class_name}:\n" + "".join(tests)

    return test_code

def run_tests(df, base_url):
    """Execute API tests and return a report."""
    results = []
    
    for _, row in df.iterrows():
        method = row['method'].lower()
        endpoint = row['endpoint']
        request_body = json.loads(row['request_body']) if pd.notna(row['request_body']) and row['request_body'].lower() != 'null' else None
        url = f"{base_url}{endpoint}"

        headers = {"Content-Type": "application/json"}
        request_details = {
            "method": method.upper(),
            "url": url,
            "headers": headers,
            "body": request_body
        }

        start_time = time.time()
        response = requests.request(method, url, json=request_body, headers=headers)
        elapsed_time = round((time.time() - start_time) * 1000, 2)

        expected_status = row['expected_status']
        actual_status = response.status_code
        status_match = "✅ Pass" if actual_status == expected_status else "❌ Fail"

        failure_reason = None
        if status_match == "❌ Fail":
            failure_reason = {
                "expected_status": expected_status,
                "actual_status": actual_status,
                "response_body": response.text,
                "request_sent": request_details  # Include request details
            }

        results.append({
            "Test Case": row['test_case'],
            "Endpoint": endpoint,
            "Expected Status": expected_status,
            "Actual Status": actual_status,
            "Status Match": status_match,
            "Response Time (ms)": elapsed_time,
            "Failure Reason": json.dumps(failure_reason, indent=4) if failure_reason else "N/A"
        })
    
    return pd.DataFrame(results)


# Streamlit UI
st.title("API Test Executor & Test Case Generator")
uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
base_url = st.text_input("Enter Base URL (e.g., http://localhost:5000)")

if uploaded_file and base_url:
    df = pd.read_csv(uploaded_file)
    st.write("### Uploaded Data Preview")
    st.dataframe(df.head(2))

    # Buttons for separate actions
    col1, col2 = st.columns(2)

    with col1:
        run_tests_btn = st.button("🚀 Generate Test Report")

    with col2:
        generate_code_btn = st.button("📝 Generate Test Cases")

    if run_tests_btn:
        report_df = run_tests(df, base_url)
        st.write("### 🧪 Test Execution Report")
        st.dataframe(report_df[['Test Case', 'Endpoint', 'Expected Status', 'Actual Status', 'Status Match', 'Response Time (ms)']])

        failed_tests = report_df[report_df["Status Match"] == "❌ Fail"]

        if not failed_tests.empty:
            st.write("### ❌ Detailed Failure Reasons")
            for index, row in failed_tests.iterrows():
                with st.expander(f"Test Case: {row['Test Case']} | Endpoint: {row['Endpoint']}"):
                    failure_data = json.loads(row["Failure Reason"])
                    st.write(f"**Expected Status:** {failure_data['expected_status']}")
                    st.write(f"**Actual Status:** {failure_data['actual_status']}")
                    
                    st.write("**Request Sent:**")
                    st.code(json.dumps(failure_data["request_sent"], indent=4), language="json")
                    
                    st.write("**Response Received:**")
                    st.code(failure_data["response_body"], language="json")
        else:
            st.success("✅ All tests passed successfully! 🎉")

        csv_report = report_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Test Report",
            data=csv_report,
            file_name="test_report.csv",
            mime="text/csv"
        )

    if generate_code_btn:
        st.write("### 📝 Generated Test Cases")
        test_code = generate_test_code(df, base_url)
        st.code(test_code, language='python')

        st.download_button(
            label="📥 Download Test Code",
            data=test_code,
            file_name="test_cases.py",
            mime="text/plain"
        )
