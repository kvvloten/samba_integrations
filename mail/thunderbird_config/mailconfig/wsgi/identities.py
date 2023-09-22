#!/usr/bin/env python3
import argparse
import json
import os.path

import signature
import mailboxes


FILE_PATH = os.path.dirname(os.path.abspath(__file__))
debug = False


def get_sogo_identities(user):
    """
    :param user:
    :return:
      [
         {
             "email": "user@example.net",
             "isDefault": 1,
             "fullName": "The Test User",
             "signature": "Greetings from iRedMail"
         }
      ]
    """
    with open('{}/config.json'.format(FILE_PATH), 'r') as read_file:
        config = json.load(read_file)

    ldap_user, ldap_groups = mailboxes.get_user_mailboxes(user, config['ldap'], verify_cert=not debug)
    identities = []
    for mailbox_name in ldap_user['proxyAddresses']:
        identity = {
            'email': mailboxes.get_longest_alias(mailbox_name, ldap_user['url']),
            'isDefault': 1 if ldap_user['otherMailbox'] == mailbox_name else 0,
            'fullName': ldap_user['displayName'],
            'signature': signature.get_signature(mailbox_name, user),
        }
        identities.append(identity)

    shared_mailboxes = [mailbox for mailbox in ldap_groups if mailbox['sAMAccountName'].startswith('mail_box-')]
    for mailbox in shared_mailboxes:
        identity = {
            'email': mailbox['mail'],
            'isDefault': 0,
            'fullName': mailbox['displayName'] if mailbox['displayName'] else mailbox['mail'],
            'signature': signature.get_signature(mailbox['mail'], user),
        }
        identities.append(identity)
    return identities


def get_thunderbird_identities(user, config, cached_indices, start_index):
    ldap_user, ldap_groups = mailboxes.get_user_mailboxes(user, config['ldap'], verify_cert=not debug)
    next_index = mailboxes.get_next_index(cached_indices, start_index)
    identities = []
    for mailbox in ldap_user['proxyAddresses']:
        mailbox_domain = mailbox.split('@')[1]
        group_lookup = [mailbox for mailbox in ldap_groups
                        if mailbox['sAMAccountName'] == 'mail_user-{}'.format(mailbox_domain)]
        if not len(group_lookup):  # The mail-domain no longer exists but the user record has not been updated
            continue

        mail_address = mailboxes.get_longest_alias(mailbox, ldap_user['url'])
        cache, next_index = mailboxes.get_index(cached_indices, next_index, mail_address)
        folder_path = '' if not config['mail']['mailbox_domain_folders'] or \
                            config['mail']['dns_domain'] == mailbox_domain else 'INBOX/{}'.format(mailbox_domain),
        identity = {
            'index': cache['index'],
            'mail_address': mail_address,
            'is_default': ldap_user['otherMailbox'] == mailbox,
            'full_name': ldap_user['displayName'],
            'organization': group_lookup[0]['info'],
            'signature': signature.get_signature(mailbox, user).replace('"', '\\"'),
            'folder_path': folder_path,
            'aliases': [alias for alias in ldap_user['url'] if alias.split('@')[1] == mailbox_domain],
        }
        identities.append(identity)

    shared_mailboxes = [mailbox for mailbox in ldap_groups if mailbox['sAMAccountName'].startswith('mail_box-')]
    for mailbox in shared_mailboxes:
        mailbox_user, mailbox_domain = mailbox['mail'].split('@')
        cache, next_index = mailboxes.get_index(cached_indices, next_index, mailbox['mail'])
        identity = {
            'index': cache['index'],
            'mail_address': mailbox['mail'],
            'is_default': False,
            'full_name': mailbox['displayName'] if mailbox['displayName'] else mailbox['mail'],
            'organization': mailbox['info'] if mailbox['displayName'] else '',
            'signature': signature.get_signature(mailbox['mail'], user).replace('"', '\\"'),
            # extensions.folderaccount.replyToOnReplyForward.imap://kvv@strauss.composers.lan/shared/cvanvloten.nl/sysadmin/INBOX
            'folder_path': '{}/{}/{}/INBOX'.format(config['mail']['namespace_shared'], mailbox_domain, mailbox_user),
            'aliases': [],
        }
        identities.append(identity)
    return identities


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', dest='user', required=True)
    parser.add_argument('-t', '--type', dest='type', required=True, choices={'sogo', 'thunderbird'})
    args = parser.parse_args(argv)
    if args.type == 'sogo':
        # Used by: server_mail/mailconfig/h_user_identities_get.yml
        print(json.dumps(get_sogo_identities(args.user)))
    elif args.type == 'thunderbird':
        # Not currently used, except for testing purposes
        with open('{}/config.json'.format(FILE_PATH), 'r') as read_file:
            config = json.load(read_file)

        start_index = 100
        cached_data = mailboxes.read_cache(config, args.user)
        print(json.dumps(get_thunderbird_identities(args.user, config, cached_data['identities'], start_index)))
        mailboxes.write_cache(config, args.user, cached_data)


if __name__ == "__main__":
    main()
