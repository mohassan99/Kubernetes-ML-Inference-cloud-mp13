"""
Premium Tier Flask API service.
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

@app.route('/premium', methods=['POST'])
def post_premium():
    data = request.get_json()
    dataset = data.get('dataset', 'kmnist')

    with open('premium-tier-job.yaml', 'r') as f:
        job_spec = yaml.safe_load(f)

    job_name = f"premium-job-{uuid.uuid4().hex[:8]}"
    job_spec['metadata']['name'] = job_name

    for env in job_spec['spec']['template']['spec']['containers'][0]['env']:
        if env['name'] == 'DATASET':
            env['value'] = dataset

    batch_v1.create_namespaced_job(namespace='premium-service', body=job_spec)

    return jsonify({'job_name': job_name, 'status': 'submitted'}), 200

@app.route('/premium/logs', methods=['GET'])
def get_premium_logs():
    pods = v1.list_namespaced_pod(namespace='premium-service')
    logs = []
    for pod in pods.items:
        try:
            log = v1.read_namespaced_pod_log(
                name=pod.metadata.name,
                namespace='premium-service'
            )
            logs.append({
                'pod': pod.metadata.name,
                'log': log
            })
        except Exception as e:
            logs.append({
                'pod': pod.metadata.name,
                'log': str(e)
            })
    return jsonify(logs), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
