""" Assign EC2 Elastic IP to the current instance """
import logging
import logging.config
import sys

import boto.utils
from boto.ec2 import connect_to_region

from aws_ec2_assign_elastic_ip.command_line_options import ARGS as args


logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format':
            '%(asctime)s - aws-ec2-assign-eip - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        }
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': True
        },
        'aws-ec2-assign-eip': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': False
        }
    }
})
LOGGER = logging.getLogger('aws-ec2-assign-eip')

# Connect to AWS EC2
if args.aws_access_key or args.aws_secret_key:
    CONNECTION = connect_to_region(
        args.region,
        aws_access_key_id=args.aws_access_key,
        aws_secret_access_key=args.aws_secret_key)
else:
    CONNECTION = connect_to_region(args.region)
LOGGER.info('Connected to AWS EC2 in {}'.format(args.region))


def main():
    """ Main function """
    # Get our instance name
    instance_id = boto.utils.get_instance_metadata()['instance-id']

    # Get an unassigned Elastic IP
    address = _get_unassigned_address()

    # Exit if there were no available Elastic IPs
    if not address:
        sys.exit(1)

    # Assign the Elastic IP to our instance
    _assign_address(instance_id, address)


def _assign_address(instance_id, address):
    """ Assign an address to the given instance ID

    :type instance_id: str
    :param instance_id: Instance ID
    :type address: boto.ec2.address
    :param address: Elastic IP address
    :returns: None
    """
    LOGGER.debug('Trying to associate {} with {}'.format(
        instance_id, address.public_ip))

    # Check if this is an VPC or standard allocation
    try:
        if address.domain == 'standard':
            # EC2 classic association
            CONNECTION.associate_address(
                instance_id,
                public_ip=address.public_ip)
        else:
            # EC2 VPC association
            CONNECTION.associate_address(
                instance_id,
                allocation_id=address.allocation_id)
    except Exception as error:
        LOGGER.error('Failed to associate {} with {}. Reason: {}'.format(
            instance_id, address.public_ip, error))
        sys.exit(1)

    LOGGER.info('Successfully associated Elastic IP {} with {}'.format(
        address.public_ip, instance_id))


def _get_unassigned_address():
    """ Return the first unassigned EIP we can find

    :returns: boto.ec2.address or None
    """
    eip = None
    valid_ips = _valid_ips()

    for address in CONNECTION.get_all_addresses():
        # Check if the address is associated
        if address.instance_id:
            continue

        # Check if the address is in the valid IP's list
        if valid_ips and address.public_ip not in valid_ips:
            continue

        eip = address

    if not eip:
        LOGGER.error('No unassigned Elastic IP found!!')

    return eip


def _valid_ips():
    """ Get a list of the valid Elastic IPs to assign

    :returns: list or None
        List of IPs. If any IP is valid the function returns None
    """
    if args.ips:
        ips = []

        for ip in args.ips.split(','):
            ips.append(ip.strip())

        LOGGER.info('Valid IPs: {}'.format(', '.join(ips)))
        return ips

    LOGGER.info('Valid IPs: any')
    return None