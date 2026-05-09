"""
Premium Tier Flask API service.

This module provides a minimal Flask application that exposes an endpoint to launch
Kubernetes jobs in the 'premium-service' namespace.

Students should extend this code to add additional endpoints, error handling,
or business logic as required by the assignment.
"""

from kubernetes import client, config
from flask import Flask, request, jsonify
import yaml
import uuid

# Load Kubernetes configuration 
try:
    config.load_incluster_config() 
except config.config_exception.ConfigException:
    config.load_kube_config()  

# Initialize Flask app
v1 = client.CoreV1Api()
app = Flask(__name__)

# TODO: Define a POST endpoint that:
#   - Parses the incoming JSON for the 'dataset' parameter
#   - Loads the job YAML template
#   - Injects the dataset value into the job spec
#   - Generates a unique job name
#   - Submits the job to the Kubernetes cluster
#   - Returns a success or error response
@app.route('/premium', methods=['POST'])
def post_premium():
    try:
        data = request.get_json()
        dataset = data.get('dataset', 'kmnist') if data else 'kmnist'

        with open('/app/premium-tier-job.yaml', 'r') as f:
            job_spec = yaml.safe_load(f)

        job_name = f"premium-job-template-{uuid.uuid4().hex[:8]}"
        job_spec['metadata']['name'] = job_name

        for env_var in job_spec['spec']['template']['spec']['containers'][0]['env']:
            if env_var['name'] == 'DATASET':
                env_var['value'] = dataset

        batch_v1 = client.BatchV1Api()
        batch_v1.create_namespaced_job(namespace='premium-service', body=job_spec)

        return jsonify({'job_name': job_name, 'status': 'submitted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
