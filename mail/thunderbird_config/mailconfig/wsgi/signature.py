#!/usr/bin/env python3
import argparse
import base64
import glob
import json
import os
from bottle import jinja2_template
import ldap_support as lds
import mailboxes

FILE_PATH = os.path.dirname(os.path.abspath(__file__))


def _add_picture_links(domain, vars_signature):
    pictures = glob.glob('{}/signatures/{}/files/*'.format(FILE_PATH, domain))
    picture_links = {}
    for picture in pictures:
        with open(picture, "rb") as fh:
            file_content = base64.b64encode(fh.read()).decode('utf-8')

        inline_picture = 'data:image/{};base64,{}'.format(picture.split('.')[-1], file_content)
        key = picture.split('/')[-1].replace('.', '_')
        picture_links[key] = inline_picture

    vars_signature['picture_link_to'] = picture_links


def get_signature(mailbox, user, debug=False):
    with open("{}/config.json".format(FILE_PATH), "r") as read_file:
        config = json.load(read_file)

    mailbox_user, mailbox_domain = mailbox.split('@')
    if mailbox_user == user:
        ldap_attrs = ['displayName', 'url', 'telephoneNumber', 'title', 'mobile', 'otherMailbox', 'mail']
        ldap_filter = '(&(objectClass=user)(proxyAddresses={}))'.format(mailbox)
        ldap_info = lds.search(config['ldap']['uri'], config['ldap']['base_dn'], 'sub', ldap_filter, ldap_attrs,
                               verify_cert=not debug, user=config['ldap']['user'], password=config['ldap']['password'])[0]

        mail_address = mailboxes.get_longest_alias(mailbox, ldap_info['url'])
    else:
        ldap_attrs = ['displayName', 'mail', 'telephoneNumber']
        ldap_filter = '(&(objectClass=group)(mail={}))'.format(mailbox)
        ldap_info = lds.search(config['ldap']['uri'], config['ldap']['base_dn'], 'sub', ldap_filter, ldap_attrs, 
                               verify_cert=not debug, user=config['ldap']['user'], password=config['ldap']['password'])[0]
        mail_address = ldap_info['mail']

    if not ldap_info or not os.path.exists('{}/signatures/{}/signature.html.j2'.format(FILE_PATH, mailbox_domain)):
        return ''

    vars_signature = {
        'mail_address': mail_address,
        'fullname': ldap_info['displayName'],
    }
    if 'title' in ldap_info:
        vars_signature['job_title'] = ldap_info['title']
    if 'telephoneNumber' in ldap_info:
        vars_signature['phone'] = ldap_info['telephoneNumber']
    if 'mobile' in ldap_info:
        vars_signature['mobile'] = ldap_info['mobile']

    _add_picture_links(mailbox_domain, vars_signature)

    mail_signature = jinja2_template('{}/signatures/{}/signature.html.j2'.format(FILE_PATH, mailbox_domain),
                                     vars_signature).replace('\n', '')
    return mail_signature


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mailbox', dest='mailbox', required=True)
    parser.add_argument('-u', '--user', dest='user', required=True)
    parser.set_defaults(shared=False)
    parser.set_defaults(debug=False)
    args = parser.parse_args(argv)
    print(get_signature(args.mailbox, args.user, debug=False))


if __name__ == "__main__":
    main()
