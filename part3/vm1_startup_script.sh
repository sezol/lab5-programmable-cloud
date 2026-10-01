#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

apt-get update
apt-get install -y python3 python3-pip

mkdir -p /srv
cd /srv

curl http://metadata.google.internal/computeMetadata/v1/instance/attributes/vm1-launch-vm2-code -H "Metadata-Flavor: Google" > vm1_launch_vm2.py
curl http://metadata.google.internal/computeMetadata/v1/instance/attributes/service-credentials -H "Metadata-Flavor: Google" > service-credentials.json

pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

python3 /srv/vm1_launch_vm2.py > /srv/vm1_launch_vm2.log 2>&1
