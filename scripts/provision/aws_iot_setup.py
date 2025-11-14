#!/usr/bin/env python3
"""
AWS IoT Provisioning Module
Handles AWS IoT Thing creation, certificate generation, and policy management
"""

import boto3
import json
from pathlib import Path
from botocore.exceptions import ClientError


class AWSIoTProvisioner:
    """Provisions AWS IoT resources for a new monitoring device"""

    def __init__(self, region, thing_name, output_dir):
        self.region = region
        self.thing_name = thing_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize AWS clients
        self.iot_client = boto3.client('iot', region_name=region)
        self.iot_data_client = boto3.client('iot-data', region_name=region)

    def create_thing(self, thing_name, attributes=None):
        """
        Create IoT Thing

        Args:
            thing_name: Name for the IoT Thing
            attributes: Optional attributes dictionary

        Returns:
            Thing ARN
        """
        try:
            response = self.iot_client.create_thing(
                thingName=thing_name,
                attributePayload={
                    'attributes': attributes or {},
                    'merge': False
                }
            )
            return response['thingArn']

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceAlreadyExistsException':
                print(f"  ⚠ Thing '{thing_name}' already exists, using existing")
                response = self.iot_client.describe_thing(thingName=thing_name)
                return response['thingArn']
            else:
                raise

    def create_certificates(self):
        """
        Create and activate certificates for the device

        Returns:
            Dictionary with certificate information
        """
        # Create keys and certificate
        response = self.iot_client.create_keys_and_certificate(
            setAsActive=True
        )

        cert_id = response['certificateId']
        cert_arn = response['certificateArn']

        # Save certificate files
        cert_pem = response['certificatePem']
        public_key = response['keyPair']['PublicKey']
        private_key = response['keyPair']['PrivateKey']

        # Write certificate files
        (self.output_dir / 'device.pem.crt').write_text(cert_pem)
        (self.output_dir / 'public.pem.key').write_text(public_key)
        (self.output_dir / 'private.pem.key').write_text(private_key)

        # Set restrictive permissions on private key
        (self.output_dir / 'private.pem.key').chmod(0o600)

        # Download Amazon Root CA
        import urllib.request
        ca_url = 'https://www.amazontrust.com/repository/AmazonRootCA1.pem'
        ca_path = self.output_dir / 'AmazonRootCA1.pem'

        with urllib.request.urlopen(ca_url) as response:
            ca_path.write_bytes(response.read())

        print(f"  → Saved certificates to {self.output_dir}")

        return {
            'certificateId': cert_id,
            'certificateArn': cert_arn,
            'certificatePem': cert_pem
        }

    def create_policy(self, policy_name, thing_name):
        """
        Create IoT policy for the device

        Args:
            policy_name: Name for the policy
            thing_name: Thing name for policy document

        Returns:
            Policy ARN
        """
        # Policy document granting necessary permissions
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "iot:Connect"
                    ],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:*:client/{thing_name}"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "iot:Publish"
                    ],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:*:topic/transformers/{thing_name}/*",
                        f"arn:aws:iot:{self.region}:*:topic/transformers/telemetry",
                        f"arn:aws:iot:{self.region}:*:topic/transformers/heartbeat",
                        f"arn:aws:iot:{self.region}:*:topic/transformers/alerts"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "iot:Subscribe",
                        "iot:Receive"
                    ],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:*:topicfilter/transformers/{thing_name}/commands/*",
                        f"arn:aws:iot:{self.region}:*:topic/transformers/{thing_name}/commands/*"
                    ]
                }
            ]
        }

        try:
            response = self.iot_client.create_policy(
                policyName=policy_name,
                policyDocument=json.dumps(policy_document)
            )
            policy_arn = response['policyArn']

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceAlreadyExistsException':
                print(f"  ⚠ Policy '{policy_name}' already exists, using existing")
                # Create new version
                self.iot_client.create_policy_version(
                    policyName=policy_name,
                    policyDocument=json.dumps(policy_document),
                    setAsDefault=True
                )
                response = self.iot_client.get_policy(policyName=policy_name)
                policy_arn = response['policyArn']
            else:
                raise

        # Save policy document for reference
        (self.output_dir / 'iot_policy.json').write_text(
            json.dumps(policy_document, indent=2)
        )

        return policy_arn

    def attach_policy_to_certificate(self, policy_name, certificate_arn):
        """Attach policy to certificate"""
        self.iot_client.attach_policy(
            policyName=policy_name,
            target=certificate_arn
        )

    def attach_certificate_to_thing(self, thing_name, certificate_arn):
        """Attach certificate to thing"""
        self.iot_client.attach_thing_principal(
            thingName=thing_name,
            principal=certificate_arn
        )

    def get_iot_endpoint(self):
        """Get IoT endpoint for the region"""
        response = self.iot_client.describe_endpoint(
            endpointType='iot:Data-ATS'
        )
        return response['endpointAddress']

    def provision_complete_thing(self, thing_name, site_id, attributes=None):
        """
        Complete provisioning workflow
        Creates thing, certificates, policy, and attachments

        Args:
            thing_name: Name for the IoT Thing
            site_id: Site identifier
            attributes: Optional thing attributes

        Returns:
            Dictionary with all provisioning details
        """
        print(f"Provisioning AWS IoT Thing: {thing_name}")

        # Create thing
        thing_arn = self.create_thing(thing_name, attributes)
        print(f"  ✓ Created thing: {thing_arn}")

        # Create certificates
        cert_info = self.create_certificates()
        print(f"  ✓ Created certificates")

        # Create policy
        policy_name = f"{site_id}-monitor-policy"
        policy_arn = self.create_policy(policy_name, thing_name)
        print(f"  ✓ Created policy: {policy_name}")

        # Attach policy to certificate
        self.attach_policy_to_certificate(policy_name, cert_info['certificateArn'])
        print(f"  ✓ Attached policy to certificate")

        # Attach certificate to thing
        self.attach_certificate_to_thing(thing_name, cert_info['certificateArn'])
        print(f"  ✓ Attached certificate to thing")

        # Get endpoint
        endpoint = self.get_iot_endpoint()
        print(f"  ✓ IoT endpoint: {endpoint}")

        return {
            'thing_name': thing_name,
            'thing_arn': thing_arn,
            'certificate_id': cert_info['certificateId'],
            'certificate_arn': cert_info['certificateArn'],
            'policy_name': policy_name,
            'policy_arn': policy_arn,
            'endpoint': endpoint,
            'region': self.region
        }

    def deprovision_thing(self, thing_name):
        """
        Deprovision a thing (cleanup)
        WARNING: This will delete the thing, certificates, and policy
        """
        print(f"Deprovisioning thing: {thing_name}")

        try:
            # Get thing principals (certificates)
            principals = self.iot_client.list_thing_principals(
                thingName=thing_name
            )

            for principal_arn in principals.get('principals', []):
                # Detach certificate from thing
                self.iot_client.detach_thing_principal(
                    thingName=thing_name,
                    principal=principal_arn
                )

                # Get policies attached to certificate
                cert_id = principal_arn.split('/')[-1]
                policies = self.iot_client.list_attached_policies(
                    target=principal_arn
                )

                for policy in policies.get('policies', []):
                    # Detach policy
                    self.iot_client.detach_policy(
                        policyName=policy['policyName'],
                        target=principal_arn
                    )

                # Deactivate certificate
                self.iot_client.update_certificate(
                    certificateId=cert_id,
                    newStatus='INACTIVE'
                )

                # Delete certificate
                self.iot_client.delete_certificate(
                    certificateId=cert_id,
                    forceDelete=True
                )

            # Delete thing
            self.iot_client.delete_thing(thingName=thing_name)
            print(f"  ✓ Deprovisioned {thing_name}")

        except ClientError as e:
            print(f"  ⚠ Deprovision warning: {e}")


if __name__ == '__main__':
    # Test provisioning
    import sys

    if len(sys.argv) < 3:
        print("Usage: python aws_iot_setup.py <thing_name> <region> [deprovision]")
        sys.exit(1)

    thing_name = sys.argv[1]
    region = sys.argv[2]
    deprovision = len(sys.argv) > 3 and sys.argv[3] == 'deprovision'

    provisioner = AWSIoTProvisioner(
        region=region,
        thing_name=thing_name,
        output_dir=f'./output/{thing_name}/certificates'
    )

    if deprovision:
        provisioner.deprovision_thing(thing_name)
    else:
        result = provisioner.provision_complete_thing(
            thing_name=thing_name,
            site_id=thing_name.replace('-monitor', ''),
            attributes={
                'device_type': 'thermal_monitor',
                'provisioned': 'true'
            }
        )

        print("\n" + "="*60)
        print("Provisioning Complete!")
        print("="*60)
        print(f"Thing Name: {result['thing_name']}")
        print(f"Endpoint:   {result['endpoint']}")
        print(f"Region:     {result['region']}")
        print(f"Certs:      ./output/{thing_name}/certificates/")
        print("="*60)
