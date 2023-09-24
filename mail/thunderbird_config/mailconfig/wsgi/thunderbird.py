#!/usr/bin/env python3
import argparse
import json
import os.path

import ldap

import ldap_support as lds
from bottle import jinja2_template

import identities
import mailboxes

FILE_PATH = os.path.dirname(os.path.abspath(__file__))
debug = False


def _get_conn_security(name):
    lookup = {'STARTTLS': 2, 'TLS': 3}
    return lookup[name.upper()]


def _get_auth_method(name):
    lookup = {'NORMAL': 3, 'GSSAPI': 5, 'OAUTH2': 10}
    return lookup[name.upper()]


def _get_cached_item(indices, mailbox_name, next_account_index, key):
    cache_key = list_key = 'identities' if key == 'identity' else '{}s'.format(key)
    cache, next_account_index = mailboxes.get_index(indices['cached'][cache_key], next_account_index, mailbox_name)
    if key != 'identity':
        indices[list_key].append(cache['index'])
    return cache, next_account_index


def _get_conf_domain_identities(config, indices, ldap_user, is_external_machine, account_index, server_index):
    mail_identities = identities.get_thunderbird_identities(ldap_user['sAMAccountName'], config,
                                                            indices['cached']['identities'], indices['identity'])
    ordered_identities = [identity['index'] for identity in mail_identities if identity['is_default']] + \
                         [identity['index'] for identity in mail_identities if not identity['is_default']]
    template_vars = {
        'account_index': account_index,
        'server_index': server_index,
        'user_name': ldap_user['sAMAccountName'],
        'identities': mail_identities,
        'ordered_identities': ordered_identities,
        'imap': {
            'server': config['mail']['server_extern'] if is_external_machine else config['mail']['server_intern'],
        }
    }
    conf_identities = jinja2_template('{}/thunderbird/identities.j2'.format(FILE_PATH), template_vars)
    indices['identity'] = mailboxes.get_next_index(indices['cached']['identities'], indices['identity'])
    conf_identities += jinja2_template('{}/thunderbird/folderaccount.j2'.format(FILE_PATH), template_vars)
    return conf_identities, ordered_identities


def _get_conf_domain_mailbox(config, indices, ldap_user, is_external_machine):
    mailbox_name = ldap_user['mail']
    next_account_index = mailboxes.get_next_index(indices['cached']['accounts'], indices['account'])
    next_server_index = mailboxes.get_next_index(indices['cached']['servers'], indices['server'])

    account_cache, next_account_index = _get_cached_item(indices, mailbox_name, next_account_index, 'account')
    server_cache, next_server_index = _get_cached_item(indices, mailbox_name, next_server_index, 'server')

    conf_mailboxes, ordered_identities = _get_conf_domain_identities(config, indices, ldap_user, is_external_machine, 
                                                                     account_cache['index'], server_cache['index'])
    template_vars = {
        'account_index': account_cache['index'],
        'server_index': server_cache['index'],
        'ordered_identities': ordered_identities,
        'display_name': ldap_user['displayName'],
        'user_name': ldap_user['sAMAccountName'],
        'mailbox_name': mailbox_name,
        'imap': {
            'server': config['mail']['server_extern'] if is_external_machine else config['mail']['server_intern'],
            'port': config['mail']['imap']['port'],
            'security': _get_conn_security(config['mail']['imap']['security']),
            'auth_method': _get_auth_method('NORMAL') if is_external_machine else _get_auth_method('GSSAPI'),
        },
        'smtp': {
            'server': config['mail']['server_extern'] if is_external_machine else  config['mail']['server_intern'],
            'port': config['mail']['smtp']['port'],
            'security': _get_conn_security(config['mail']['smtp']['security']),
            'auth_method': _get_auth_method('NORMAL') if is_external_machine else _get_auth_method('GSSAPI'),
        },
    }
    conf_mailboxes += jinja2_template('{}/thunderbird/mailbox_domain_base.j2'.format(FILE_PATH), template_vars)
    conf_mailboxes += jinja2_template('{}/thunderbird/mailbox_domain_settings.j2'.format(FILE_PATH), template_vars)
    indices['account'] = next_account_index
    indices['server'] = next_server_index
    return conf_mailboxes


def _get_conf_mailboxes(config, ldap_user, user_cache, is_external_machine):
    default_account_index = 1
    default_server_index = 1000  # index of the domain imap, smtp server
    default_identity_index = 2000
    indices = {
        'account': default_account_index,
        'server': default_server_index,
        'identity': default_identity_index,
        'accounts': [],
        'servers': [],
        'cached': user_cache
    }

    conf_mailboxes = _get_conf_domain_mailbox(config, indices, ldap_user, is_external_machine)

    template_vars = {
        'account_refs': ','.join(['account{}'.format(index) for index in indices['accounts']]),
        'smtp_refs': ','.join(['smtp{}'.format(index) for index in indices['servers']]),
        'default_account': 'account{}'.format(indices['accounts'][0]),
        'default_smtp': 'smtp{}'.format(indices['servers'][0]),
        'user_name': ldap_user['sAMAccountName'],
    }
    conf_mailboxes += jinja2_template('{}/thunderbird/mailbox_glue.j2'.format(FILE_PATH), template_vars)
    return conf_mailboxes


def _get_conf_settings(config, user_name, user_collected_addressbook_id, user_cache, is_external_machine):
    templates = [
        {
            "file": "settings_mail.j2",
            "vars": {'user_name': user_name}
        },
        {
            "file": "settings_filelink.j2",
            "vars": {
                'user_name': user_name,
                'filelink': {
                    # Use a little margin to Postfix's maximum size and convert to kB for Thunderbird
                    'maximum_message_size': (int(config['mail']['maximum_message_size']) - 1) * 1024,
                }
            }
        },
        {
            "file": "settings_calendar.j2",
            "vars": {
                'user_name': user_name,
                'dns_domain': config['mail']['dns_domain'],
                'calendar': {
                    'base_url': config['calendar']['url_extern'] if is_external_machine else config['calendar']['url_intern'],
                    'title': config['calendar']['title'],
                    'uuid': mailboxes.get_calendar_uuid(user_cache)['uuid'],
                    'timezone': config['calendar']['timezone'],
                    'first_week_day': config['calendar']['first_week_day'],
                    'weekend_days': config['calendar']['weekend_days'],
                    'business_hours': config['calendar']['business_hours'],
                }
            }
        },
        {
            "file": "settings_addressbooks.j2",
            "vars": {
                'user_name': user_name,
                'dns_domain': config['mail']['dns_domain'],
                'carddav': {
                    'base_url': config['carddav']['url_extern'] if is_external_machine else config['carddav']['url_intern'],
                    'domain_addressbook': {
                        'title': config['carddav']['domain_addressbook']['title'],
                        'id': config['carddav']['domain_addressbook']['id'],
                    },
                    'personal_addressbook_title': config['carddav']['personal_addressbook_title'],
                    'collected_addressbook': {
                        'title': config['carddav']['collected_addressbook_title'],
                        'id': user_collected_addressbook_id.split('=')[
                            1] if '=' in user_collected_addressbook_id else '',
                    }
                }
            }
        },
    ]
    conf_other = ""
    for template in templates:
        conf_other += jinja2_template('{}/thunderbird/{}'.format(FILE_PATH, template["file"]), template["vars"])
    return conf_other

def _is_external_machine(host, ldap_conf, verify_cert):
    if not host:
        return False

    ldap_s = lds.LdapSupport(ldap_conf['uri'], verify_cert=verify_cert, user=ldap_conf['user'], password=ldap_conf['password'])

    ldap_attrs = ['member']
    for group in ldap_conf['external_machine_groups']:
        ldap_filter = '(&(objectClass=group)(sAMAccountName={}))'.format(group)
        ldap_group = ldap_s.search(ldap_conf['base_dn'], 'sub', ldap_filter, ldap_attrs)[0]
        for member in ldap_group['member']:
            member_host = ldap.dn.explode_dn(member, flags=ldap_conf.DN_FORMAT_LDAPV2)[0].split('=')[0]
            if host == member_host:
                return True
    return False


def get_thunderbird_config(host, user):
    with open('{}/config.json'.format(FILE_PATH), 'r') as read_file:
        config = json.load(read_file)

    is_external_machine = _is_external_machine(host, config['ldap'], verify_cert=not debug)
    ldap_user, _ = mailboxes.get_user_mailboxes(user, config['ldap'], verify_cert=not debug)
    user_name = ldap_user['sAMAccountName']
    user_cache = mailboxes.read_cache(config, user_name)

    tb_config = jinja2_template('{}/thunderbird/main_start.j2'.format(FILE_PATH), user_name=user_name)
    if config['enable']['mailbox'] == 'domain' or 'mailconfig=true' in ldap_user['primaryTelexNumber']:
        tb_config += _get_conf_mailboxes(config, ldap_user, user_cache, is_external_machine)
    if config['enable']['settings'] == 'domain' or 'mailconfig=true' in ldap_user['primaryTelexNumber']:
        tb_config += _get_conf_settings(config, user_name, ldap_user['primaryInternationalISDNNumber'], 
                                        user_cache, is_external_machine)
    tb_config += jinja2_template('{}/thunderbird/main_end.j2'.format(FILE_PATH), user_name=user_name)

    mailboxes.write_cache(config, user_name, user_cache)
    return tb_config


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', dest='user', required=True)
    parser.add_argument('-s', '--host', dest='host', required=True)
    args = parser.parse_args(argv)
    print(get_thunderbird_config(args.host, args.user))


if __name__ == "__main__":
    debug = True
    main()
