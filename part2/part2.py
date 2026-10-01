#!/usr/bin/env python3

import time

import googleapiclient.discovery
import google.auth

credentials, project = google.auth.default()
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

ZONE = 'us-west1-b'
SOURCE_INSTANCE = 'flask-app-instance'
MACHINE_TYPE = 'e2-medium'
NUM_CLONES = 3


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


def get_boot_disk_name(compute, project, zone, instance_name):
    instance = compute.instances().get(
        project=project, zone=zone, instance=instance_name
    ).execute()
    for disk in instance['disks']:
        if disk.get('boot'):
            return disk['source'].split('/')[-1]
    raise Exception(f"No boot disk found for instance {instance_name}")


def create_snapshot(compute, project, zone, instance_name, snapshot_name):
    disk_name = get_boot_disk_name(compute, project, zone, instance_name)
    body = {'name': snapshot_name}
    operation = compute.disks().createSnapshot(
        project=project, zone=zone, disk=disk_name, body=body
    ).execute()
    wait_for_operation(compute, project, operation['name'], zone=zone)
    return snapshot_name


def create_instance_from_snapshot(compute, project, zone, name, snapshot_name, machine_type):
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
                'sourceSnapshot': f"global/snapshots/{snapshot_name}",
            }
        }],
        'networkInterfaces': [{
            'network': 'global/networks/default',
            'accessConfigs': [{
                'type': 'ONE_TO_ONE_NAT',
                'name': 'External NAT'
            }]
        }]
    }

    return compute.instances().insert(
        project=project, zone=zone, body=config
    ).execute()


def main():
    snapshot_name = f"base-snapshot-{SOURCE_INSTANCE}"

    print(f"Creating snapshot '{snapshot_name}' from instance '{SOURCE_INSTANCE}'...")
    create_snapshot(service, project, ZONE, SOURCE_INSTANCE, snapshot_name)
    print("Snapshot created.")

    timing_results = []

    for i in range(1, NUM_CLONES + 1):
        instance_name = f"clone-instance-{i}"
        print(f"\nCreating instance '{instance_name}' from snapshot...")

        start_time = time.time()
        operation = create_instance_from_snapshot(
            service, project, ZONE, instance_name, snapshot_name, MACHINE_TYPE
        )
        wait_for_operation(service, project, operation['name'], zone=ZONE)
        end_time = time.time()

        elapsed = end_time - start_time
        print(f"Instance '{instance_name}' created in {elapsed:.2f} seconds.")
        timing_results.append((instance_name, elapsed))

    print("\nTiming summary:")
    for name, elapsed in timing_results:
        print(f"  {name}: {elapsed:.2f} seconds")

    with open('TIMING.md', 'w') as f:
        f.write("# Part 2 - Instance Creation Timing Results\n\n")
        f.write(f"Instances were created in zone `{ZONE}` using machine type `{MACHINE_TYPE}`, ")
        f.write(f"from snapshot `{snapshot_name}` (taken from source instance `{SOURCE_INSTANCE}`).\n\n")
        f.write("| Instance | Creation Time (seconds) |\n")
        f.write("|----------|--------------------------|\n")
        for name, elapsed in timing_results:
            f.write(f"| {name} | {elapsed:.2f} |\n")

    print("\nTIMING.md written.")


if __name__ == '__main__':
    main()
