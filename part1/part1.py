#!/usr/bin/env python3

import time

import googleapiclient.discovery
import google.auth

credentials, project = google.auth.default()
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

ZONE = 'us-west1-b'
INSTANCE_NAME = 'flask-app-instance'
MACHINE_TYPE = 'e2-medium'

startup_script = """#!/bin/bash
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
    print("Waiting for operation to finish...")
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


def firewall_rule_exists(compute, project, name='allow-5000'):
    result = compute.firewalls().list(project=project).execute()
    rules = result.get('items', [])
    return any(rule['name'] == name for rule in rules)


def create_firewall_rule(compute, project):
    firewall_body = {
        'name': 'allow-5000',
        'network': 'global/networks/default',
        'sourceRanges': ['0.0.0.0/0'],
        'targetTags': ['allow-5000'],
        'allowed': [{
            'IPProtocol': 'tcp',
            'ports': ['5000']
        }]
    }
    return compute.firewalls().insert(project=project, body=firewall_body).execute()


def create_instance(compute, project, zone, name, startup_script, machine_type):
    image_response = compute.images().getFromFamily(
        project='ubuntu-os-cloud', family='ubuntu-2204-lts'
    ).execute()
    source_disk_image = image_response['selfLink']

    config = {
        'name': name,
        'machineType': f"zones/{zone}/machineTypes/{machine_type}",
        'tags': {
            'items': ['allow-5000']
        },
        'disks': [{
            'boot': True,
            'autoDelete': True,
            'initializeParams': {
                'sourceImage': source_disk_image,
            }
        }],
        'networkInterfaces': [{
            'network': 'global/networks/default',
            'accessConfigs': [{
                'type': 'ONE_TO_ONE_NAT',
                'name': 'External NAT'
            }]
        }],
        'metadata': {
            'items': [{
                'key': 'startup-script',
                'value': startup_script
            }]
        }
    }

    return compute.instances().insert(
        project=project, zone=zone, body=config
    ).execute()


def main():
    if not firewall_rule_exists(service, project, 'allow-5000'):
        print("Firewall rule 'allow-5000' not found, creating it...")
        operation = create_firewall_rule(service, project)
        wait_for_operation(service, project, operation['name'])
    else:
        print("Firewall rule 'allow-5000' already exists, skipping creation.")

    print(f"Creating instance '{INSTANCE_NAME}' in {ZONE}...")
    operation = create_instance(service, project, ZONE, INSTANCE_NAME, startup_script, MACHINE_TYPE)
    wait_for_operation(service, project, operation['name'], zone=ZONE)

    instance_info = service.instances().get(
        project=project, zone=ZONE, instance=INSTANCE_NAME
    ).execute()
    external_ip = instance_info['networkInterfaces'][0]['accessConfigs'][0]['natIP']

    print(f"\nThe Flask application is available at:\n\nhttp://{external_ip}:5000\n")


if __name__ == '__main__':
    main()
