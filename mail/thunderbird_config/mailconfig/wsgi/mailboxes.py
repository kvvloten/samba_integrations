#!/usr/bin/env python3
import argparse
import json
import os
import uuid
import ldap_support as lds

FILE_PATH = os.path.dirname(os.path.abspath(__file__))
debug = False


def read_cache(config, user):
    cache_file = '{}/{}.json'.format(config['thunderbird_cache_directory'], user)
    if not os.path.exists(cache_file):
        return {'accounts': {}, 'servers': {}, 'identities': {}, 'ldap': {}}

    with open(cache_file, 'r') as read_file:
        cache = json.load(read_file)
    if 'servers' not in cache:
        cache['servers'] = {}
    if 'calendar' not in cache:
        cache['calendar'] = {}
    for item in cache:
        if item in ['calendar']:
            continue
        for key in cache[item]:
            cache[item][key]['active'] = False
    return cache


def write_cache(config, user, cache):
    cache_file = '{}/{}.json'.format(config['thunderbird_cache_directory'], user)
    with open(cache_file, 'w') as write_file:
        json.dump(cache, write_file, indent=4)


def get_next_index(cached_indices, start_index):
    next_index = max(start_index,
                     0 if not len(cached_indices) else max(cached_indices[key]['index'] for key in cached_indices) + 1)
    return next_index


def get_index(cached_items, next_index, mail_address):
    if mail_address in cached_items:
        if 'uuid' not in cached_items[mail_address]:
            cached_items[mail_address]['uuid'] = str(uuid.uuid4())

        cache = {
            'index': cached_items[mail_address]['index'],
            'uuid': cached_items[mail_address]['uuid'],
        }
    else:
        cache = {
            'index': next_index,
            'uuid': str(uuid.uuid4()),
        }
        cached_items[mail_address] = cache
        next_index += 1

    cached_items[mail_address]['active'] = True
    return cache, next_index


def get_calendar_uuid(cached_items):
    key = 'calendar'
    if not cached_items[key]:
        cached_items[key] = {'uuid': str(uuid.uuid4())}

    cache = cached_items[key]
    return cache


def get_longest_alias(mailbox, user_aliases):
    domain = mailbox.split('@')[1]
    aliases = [alias for alias in user_aliases if alias.split('@')[1] == domain]
    exposed_mail_address = mailbox
    for alias in aliases:
        if len(alias) > len(exposed_mail_address):
            exposed_mail_address = alias

    return exposed_mail_address


def get_user_mailboxes(user, ldap, verify_cert=True):
    ldap_s = lds.LdapSupport(ldap['uri'], verify_cert=verify_cert, user=ldap['user'], password=ldap['password'])

    user_attrs = ['distinguishedName', 'sAMAccountName', 'displayName', 'mail', 'proxyAddresses', 'otherMailbox',
                  'url', 'userPrincipalName', 'primaryTelexNumber', 'primaryInternationalISDNNumber']
    user_filter = '(&(objectClass=user)(|(sAMAccountName={})(userPrincipalName={})))'.format(user, user)
    ldap_user = ldap_s.search(ldap['base_dn'], 'sub', user_filter, user_attrs)[0]
    for user_attr in ['primaryTelexNumber', 'primaryInternationalISDNNumber']:
        if not user_attr in ldap_user:
            ldap_user[user_attr] = ''

    for user_attr in ['proxyAddresses', 'url']:
        if isinstance(ldap_user[user_attr], str):
            ldap_user[user_attr] = [ldap_user[user_attr]]

    # Lookup shared mailboxes (mail_box-*) and authorized mail-domains (mail_user-*)
    group_attrs = ['sAMAccountName', 'displayName', 'mail', 'info']
    group_filter = '(&(|(cn=mail_box-*)(cn=mail_user-*))(member:1.2.840.113556.1.4.1941:={}))'. \
        format(ldap_user['distinguishedName'])
    ldap_groups = ldap_s.search(ldap['base_dn'], 'sub', group_filter, group_attrs)

    return ldap_user, ldap_groups


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', dest='user', required=True)
    args = parser.parse_args(argv)
    print()
    with open('{}/config.json'.format(FILE_PATH), 'r') as read_file:
        config = json.load(read_file)

    ldap_user, ldap_groups = get_user_mailboxes(args.user, config['ldap'], verify_cert=not debug)

    print('user: {}'.format(ldap_user))
    print('groups {}'.format(ldap_groups))


if __name__ == "__main__":
    debug = True
    main()
