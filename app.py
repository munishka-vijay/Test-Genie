import streamlit as st
import requests
import json
import yaml
import pandas as pd
import time
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="API Testing Agent", layout="wide")

def parse_openapi_spec(spec_content):
    """Parse OpenAPI/Swagger specification from YAML or JSON"""
    try:
        # Try parsing as JSON first
        return json.loads(spec_content)
    except json.JSONDecodeError:
        # If not JSON, try YAML
        try:
            return yaml.safe_load(spec_content)
        except yaml.YAMLError as e:
            st.error(f"Failed to parse specification: {str(e)}")
            return None

def generate_test_cases(spec):
    """Generate test cases from OpenAPI specification"""
    test_cases = []
    
    # Extract base URL
    servers = spec.get('servers', [])
    base_url = servers[0]['url'] if servers else ""
    
    # Process each path and method
    for path, path_item in spec.get('paths', {}).items():
        for method, operation in path_item.items():
            if method.lower() not in ['get', 'post', 'put', 'delete', 'patch']:
                continue
                
            # Create a base test case for this endpoint
            test_case = {
                'path': path,
                'method': method.upper(),
                'name': operation.get('summary', f"{method.upper()} {path}"),
                'description': operation.get('description', ''),
                'request': {
                    'url': f"{base_url}{path}",
                    'headers': {},
                    'params': {},
                    'body': None
                },
                'expected': {
                    'status': list(operation.get('responses', {}).keys())[0] if operation.get('responses') else "200"
                }
            }
            
            # Add authentication if required
            security = operation.get('security', spec.get('security', []))
            if security:
                auth_scheme = list(security[0].keys())[0] if security[0] else None
                if auth_scheme:
                    test_case['auth_required'] = True
                    security_schemes = spec.get('components', {}).get('securitySchemes', {})
                    if auth_scheme in security_schemes:
                        scheme = security_schemes[auth_scheme]
                        if scheme.get('type') == 'apiKey':
                            test_case['auth_type'] = 'apiKey'
                            test_case['auth_name'] = scheme.get('name')
                            test_case['auth_in'] = scheme.get('in')
                        elif scheme.get('type') == 'http' and scheme.get('scheme') == 'bearer':
                            test_case['auth_type'] = 'bearer'
            
            # Add parameters
            parameters = operation.get('parameters', [])
            for param in parameters:
                param_name = param.get('name')
                param_in = param.get('in')
                required = param.get('required', False)
                
                if param_in == 'query':
                    # For query parameters
                    test_case['request']['params'][param_name] = None
                elif param_in == 'header':
                    # For header parameters
                    test_case['request']['headers'][param_name] = None
                
                if required:
                    test_case['required_params'] = test_case.get('required_params', [])
                    test_case['required_params'].append(param_name)
            
            # Handle request body
            request_body = operation.get('requestBody', {})
            if request_body:
                content = request_body.get('content', {})
                for content_type, content_schema in content.items():
                    test_case['request']['headers']['Content-Type'] = content_type
                    # Generate a sample body based on schema
                    schema = content_schema.get('schema', {})
                    if schema:
                        test_case['request']['body'] = {}
                        # In a real implementation, you would generate a sample based on the schema
            
            test_cases.append(test_case)
            
            # Create additional test cases for error conditions
            # 1. Missing required parameters
            if test_case.get('required_params'):
                error_test = test_case.copy()
                error_test['name'] = f"{test_case['name']} - Missing Required Parameters"
                error_test['request'] = test_case['request'].copy()
                error_test['request']['params'] = {}
                error_test['expected']['status'] = "400"
                test_cases.append(error_test)
                
            # 2. Invalid authentication
            if test_case.get('auth_required'):
                error_test = test_case.copy()
                error_test['name'] = f"{test_case['name']} - Invalid Authentication"
                error_test['request'] = test_case['request'].copy()
                error_test['auth_value'] = "invalid_auth_value"
                error_test['expected']['status'] = "401"
                test_cases.append(error_test)
    
    return test_cases

def execute_test(test_case, auth_values):
    """Execute a single test case"""
    result = {
        'test_name': test_case['name'],
        'path': test_case['path'],
        'method': test_case['method'],
        'start_time': datetime.now(),
        'status': 'Pending'
    }
    
    try:
        # Prepare request
        url = test_case['request']['url']
        method = test_case['method'].lower()
        headers = test_case['request']['headers'].copy()
        params = test_case['request']['params'].copy()
        body = test_case['request']['body']
        
        # Fill in authentication
        if test_case.get('auth_required'):
            auth_type = test_case.get('auth_type')
            if auth_type == 'apiKey':
                auth_name = test_case.get('auth_name')
                auth_in = test_case.get('auth_in')
                auth_value = auth_values.get('apiKey')
                
                if auth_in == 'header':
                    headers[auth_name] = auth_value
                elif auth_in == 'query':
                    params[auth_name] = auth_value
            elif auth_type == 'bearer':
                headers['Authorization'] = f"Bearer {auth_values.get('bearer')}"
        
        # Make the request
        request_kwargs = {
            'url': url,
            'headers': headers,
            'params': params
        }
        
        if body is not None and method in ['post', 'put', 'patch']:
            request_kwargs['json'] = body
        
        result['request'] = {
            'url': url,
            'method': method,
            'headers': headers,
            'params': params,
            'body': body
        }
        
        response = None
        if method == 'get':
            response = requests.get(**request_kwargs)
        elif method == 'post':
            response = requests.post(**request_kwargs)
        elif method == 'put':
            response = requests.put(**request_kwargs)
        elif method == 'delete':
            response = requests.delete(**request_kwargs)
        elif method == 'patch':
            response = requests.patch(**request_kwargs)
        
        # Process response
        result['response'] = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'body': response.text[:1000]  # Truncate long responses
        }
        
        # Validate
        expected_status = test_case['expected']['status']
        if isinstance(expected_status, list):
            passed = str(response.status_code) in expected_status
        else:
            passed = str(response.status_code) == str(expected_status)
        
        result['passed'] = passed
        result['status'] = 'Passed' if passed else 'Failed'
        
    except Exception as e:
        result['error'] = str(e)
        result['passed'] = False
        result['status'] = 'Error'
    
    result['end_time'] = datetime.now()
    result['duration'] = (result['end_time'] - result['start_time']).total_seconds()
    
    return result

def run_tests(test_cases, auth_values, max_workers=5):
    """Run all test cases with progress tracking"""
    results = []
    total_tests = len(test_cases)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_test = {executor.submit(execute_test, test, auth_values): test for test in test_cases}
        completed = 0
        
        for future in future_to_test:
            test_case = future_to_test[future]
            status_text.text(f"Running test: {test_case['name']}")
            
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({
                    'test_name': test_case['name'],
                    'path': test_case['path'],
                    'method': test_case['method'],
                    'error': str(e),
                    'passed': False,
                    'status': 'Error'
                })
            
            completed += 1
            progress_bar.progress(completed / total_tests)
    
    status_text.text(f"Completed all {total_tests} tests")
    return results

def generate_report(results):
    """Generate a detailed report of test results"""
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r.get('passed', False))
    failed_tests = total_tests - passed_tests
    
    # Create summary
    summary = {
        'total_tests': total_tests,
        'passed_tests': passed_tests,
        'failed_tests': failed_tests,
        'success_rate': round(passed_tests / total_tests * 100, 2) if total_tests > 0 else 0,
        'execution_time': sum(r.get('duration', 0) for r in results if 'duration' in r)
    }
    
    # Group by endpoint
    endpoint_results = {}
    for result in results:
        endpoint = f"{result['method']} {result['path']}"
        if endpoint not in endpoint_results:
            endpoint_results[endpoint] = {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'tests': []
            }
        
        endpoint_results[endpoint]['total'] += 1
        if result.get('passed', False):
            endpoint_results[endpoint]['passed'] += 1
        else:
            endpoint_results[endpoint]['failed'] += 1
        
        endpoint_results[endpoint]['tests'].append(result)
    
    return {
        'summary': summary,
        'endpoint_results': endpoint_results,
        'results': results
    }

def display_report(report):
    """Display the test report in Streamlit"""
    st.header("Test Results Summary")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tests", report['summary']['total_tests'])
    col2.metric("Passed Tests", report['summary']['passed_tests'])
    col3.metric("Failed Tests", report['summary']['failed_tests'])
    col4.metric("Success Rate", f"{report['summary']['success_rate']}%")
    
    st.write(f"Total execution time: {report['summary']['execution_time']:.2f} seconds")
    
    # Results by endpoint
    st.header("Results by Endpoint")
    
    for endpoint, data in report['endpoint_results'].items():
        with st.expander(f"{endpoint} - {data['passed']}/{data['total']} passed"):
            for test in data['tests']:
                if test.get('passed', False):
                    st.success(test['test_name'])
                else:
                    st.error(f"{test['test_name']} - {test.get('status', 'Failed')}")
                    
                    # Show details for failed tests directly (no nested expander)
                    st.write("Request Details:")
                    if 'request' in test:
                        st.json(test['request'])
                    
                    st.write("Response Details:")
                    if 'response' in test:
                        st.json(test['response'])
                    
                    if 'error' in test:
                        st.write("Error:")
                        st.code(test['error'])
    
    # Failed tests in detail
    st.header("Failed Tests in Detail")
    failed_tests = [r for r in report['results'] if not r.get('passed', False)]
    
    if failed_tests:
        for test in failed_tests:
            with st.expander(f"{test['test_name']} - {test['method']} {test['path']}"):
                cols = st.columns(2)
                
                with cols[0]:
                    st.subheader("Request")
                    st.write("URL:", test['request']['url'])
                    st.write("Method:", test['request']['method'].upper())
                    st.write("Headers:")
                    st.json(test['request'].get('headers', {}))
                    st.write("Query Parameters:")
                    st.json(test['request'].get('params', {}))
                    if test['request'].get('body'):
                        st.write("Body:")
                        st.json(test['request']['body'])
                
                with cols[1]:
                    st.subheader("Response")
                    if 'response' in test:
                        st.write("Status Code:", test['response'].get('status_code', 'Unknown'))
                        st.write("Headers:")
                        st.json(test['response'].get('headers', {}))
                        st.write("Body:")
                        st.code(test['response'].get('body', 'No response'))
                    
                    if 'error' in test:
                        st.write("Error:")
                        st.error(test['error'])
                
                st.write("Expected Status:", test.get('expected', {}).get('status', 'Unknown'))
                st.write("Actual Status:", test.get('response', {}).get('status_code', 'No response'))
                st.write("Failure Reason:", 
                         f"Expected status code {test.get('expected', {}).get('status', 'Unknown')} " +
                         f"but got {test.get('response', {}).get('status_code', 'No response')}" if 'response' in test else test.get('error', 'Unknown error'))
    else:
        st.success("No failed tests! 🎉")

    # Download full report as JSON
    st.download_button(
        label="Download Full Report (JSON)",
        data=json.dumps(report, default=str, indent=2),
        file_name=f"api_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )


# Main Streamlit UI
st.title("API Testing Agent")

with st.sidebar:
    st.header("Input Configuration")
    input_method = st.radio("Input Method", ["Upload OpenAPI/Swagger Spec", "Direct Input"])
    
    # Authentication inputs
    st.subheader("Authentication (if required)")
    api_key = st.text_input("API Key", "", type="password")
    bearer_token = st.text_input("Bearer Token", "", type="password")
    
    auth_values = {
        'apiKey': api_key,
        'bearer': bearer_token
    }

if input_method == "Upload OpenAPI/Swagger Spec":
    uploaded_file = st.file_uploader("Upload OpenAPI/Swagger Specification", type=["json", "yaml", "yml"])
    
    if uploaded_file is not None:
        spec_content = uploaded_file.read().decode("utf-8")
        spec = parse_openapi_spec(spec_content)
        
        if spec:
            st.success("Successfully parsed specification!")
            
            # Display basic info about the API
            st.subheader("API Information")
            st.write(f"Title: {spec.get('info', {}).get('title', 'Unknown')}")
            st.write(f"Version: {spec.get('info', {}).get('version', 'Unknown')}")
            st.write(f"Description: {spec.get('info', {}).get('description', 'No description')}")
            
            # Generate and display test cases
            test_cases = generate_test_cases(spec)
            st.write(f"Generated {len(test_cases)} test cases")
            
            with st.expander("Review Test Cases"):
                for i, test in enumerate(test_cases):
                    st.write(f"Test {i+1}: {test['name']}")
                    st.write(f"Endpoint: {test['method']} {test['path']}")
                    st.write(f"Expected Status: {test['expected']['status']}")
                    st.write("---")
            
            # Run tests button
            if st.button("Run Tests"):
                with st.spinner("Running tests..."):
                    results = run_tests(test_cases, auth_values)
                    report = generate_report(results)
                
                # Display report OUTSIDE the expander to fix Streamlit nesting issue
                st.subheader("Test Report")
                display_report(report)

else:  # Direct Input
    st.subheader("API Specification")
    
    with st.expander("Simplified YAML Configuration Format", expanded=True):
        st.code('''
apis:
  - endpoint: /users
    method: GET
    auth: bearer_token
    test_cases:
      - name: "valid request"
        expected_status: 200
      - name: "invalid pagination"
        query_params: {page: -1}
        expected_status: 400
        ''', language="yaml")
    
    yaml_input = st.text_area("Enter API Configuration YAML", height=300)
    
    if yaml_input and st.button("Generate Tests"):
        try:
            yaml_data = yaml.safe_load(yaml_input)
            
            # Convert simplified format to test cases
            test_cases = []
            base_url = yaml_data.get('base_url', 'http://localhost:8000')
            
            for api in yaml_data.get('apis', []):
                endpoint = api.get('endpoint')
                method = api.get('method', 'GET')
                auth_type = api.get('auth')
                
                for tc in api.get('test_cases', []):
                    test_case = {
                        'path': endpoint,
                        'method': method.upper(),
                        'name': tc.get('name', f"{method} {endpoint}"),
                        'request': {
                            'url': f"{base_url}{endpoint}",
                            'headers': tc.get('headers', {}),
                            'params': tc.get('query_params', {}),
                            'body': tc.get('body')
                        },
                        'expected': {
                            'status': tc.get('expected_status', '200')
                        }
                    }
                    
                    # Add authentication if specified
                    if auth_type:
                        test_case['auth_required'] = True
                        if auth_type == 'api_key':
                            test_case['auth_type'] = 'apiKey'
                            test_case['auth_name'] = 'X-API-Key'
                            test_case['auth_in'] = 'header'
                        elif auth_type == 'bearer_token':
                            test_case['auth_type'] = 'bearer'
                    
                    test_cases.append(test_case)
            
            st.success(f"Generated {len(test_cases)} test cases")
            
            with st.expander("Review Test Cases"):
                for i, test in enumerate(test_cases):
                    st.write(f"Test {i+1}: {test['name']}")
                    st.write(f"Endpoint: {test['method']} {test['path']}")
                    st.write(f"URL: {test['request']['url']}")
                    st.write(f"Expected Status: {test['expected']['status']}")
                    st.write("---")
            
            # Run tests button
            if st.button("Run Tests"):
                with st.spinner("Running tests..."):
                    results = run_tests(test_cases, auth_values)
                    report = generate_report(results)
                
                # Display report OUTSIDE the expander to fix Streamlit nesting issue
                st.subheader("Test Report")
                display_report(report)

        except Exception as e:
            st.error(f"Error parsing YAML: {str(e)}")
