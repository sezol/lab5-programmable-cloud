#!/usr/bin/env python3

import os
import time

import googleapiclient.discovery
import google.oauth2.service_account as service_account

ZONE = 'us-west1-b'
INSTANCE_NAME = 'flask-vm2-instance'
MACHINE_TYPE = 'e2-medium'

flask_startup_script = """#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

apt-get update
apt-get install -y python3 python3-pip git

cd /home
git clone https://github.com/cu-csci-4253-datacenter/flask-tutorial
cd flask-tutorial

python3 setup.py install
pip3 install -e .

export FLASK_APP=flaskr
flask init-db

nohup flask run -h 0.0.0.0 &
"""


def wait_for_operation(compute, project, operation_name, zone=None):
    while True:
        if zone:
            result = compute.zoneOperations().get(
                project=project, zone=zone, operation=operation_name
            ).execute()
        else:
            result = compute.globalOperations().get(
                project=project, operation=operation_name
            ).execute()
        if result['status'] == 'DONE':
            if 'error' in result:
                raise Exception(result['error'])
            return result
        time.sleep(2)


def create_instance(compute, project, zone, name, startup_script, machine_type):
    image_response = compute.images().getFromFamily(
        project='ubuntu-os-cloud', family='ubuntu-2204-lts'
    ).execute()
    source_disk_image = image_response['selfLink']

    config = {
        'name': name,
        'machineType': f"zones/{zone}/machineTypes/{machine_type}",
        'tags': {'items': ['allow-5000']},
        'disks': [{
            'boot': True,
            'autoDelete': True,
            'initializeParams': {'sourceImage': source_disk_image}
        }],
        'networkInterfaces': [{
            'network': 'global/networks/default',
            'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}]
        }],
        'metadata': {
            'items': [{'key': 'startup-script', 'value': startup_script}]
        }
    }

    return compute.instances().insert(project=project, zone=zone, body=config).execute()


def main():
    credentials = service_account.Credentials.from_service_account_file(
        filename='/srv/service-credentials.json'
    )
    project = credentials.project_id
    compute = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

    print(f"Creating VM-2 ('{INSTANCE_NAME}') using service account credentials...")
    operation = create_instance(compute, project, ZONE, INSTANCE_NAME, flask_startup_script, MACHINE_TYPE)
    wait_for_operation(compute, project, operation['name'], zone=ZONE)

    instance_info = compute.instances().get(
        project=project, zone=ZONE, instance=INSTANCE_NAME
    ).execute()
    external_ip = instance_info['networkInterfaces'][0]['accessConfigs'][0]['natIP']

    print(f"\nVM-2 created. Flask application should be available at:\nhttp://{external_ip}:5000\n")


if __name__ == '__main__':
    main()
