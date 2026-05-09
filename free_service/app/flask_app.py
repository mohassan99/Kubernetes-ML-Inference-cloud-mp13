"""
Free Tier Flask API service.
"""
from kubernetes import client, config
from flask import Flask, request, jsonify
import yaml
import uuid

try:
    config.load_incluster_config()
except config.config_exception.ConfigException:
    config.load_kube_config()

v1 = client.CoreV1Api()
batch_v1 = client.BatchV1Api()
app = Flask(__name__)

@app.route('/free', methods=['POST'])
def post_free():
    data = request.get_json()
    dataset = data.get('dataset', 'mnist')

    with open('free-tier-job.yaml', 'r') as f:
        job_spec = yaml.safe_load(f)

    job_name = f"free-job-{uuid.uuid4().hex[:8]}"
    job_spec['metadata']['name'] = job_name

    for env in job_spec['spec']['template']['spec']['containers'][0]['env']:
        if env['name'] == 'DATASET':
            env['value'] = dataset

    batch_v1.create_namespaced_job(namespace='free-service', body=job_spec)

    return jsonify({'job_name': job_name, 'status': 'submitted'}), 200

@app.route('/free/resource-quota', methods=['GET'])
def get_resource_quota():
    quotas = v1.list_namespaced_resource_quota(namespace='free-service')
    result = []
    for quota in quotas.items:
        result.append({
            'name': quota.metadata.name,
            'hard': quota.status.hard
        })
    return jsonify(result), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
