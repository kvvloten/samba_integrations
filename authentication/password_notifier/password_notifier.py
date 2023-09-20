#!/opt/password_notifier/bin/python3
import json
import os
import ldap_support as lds
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from subprocess import Popen, PIPE
from datetime import datetime, timedelta

FILE_PATH = os.path.dirname(os.path.abspath(__file__))
debug = False

CONFIG = {}
MAIL_TEXT = ''


def ldap2datetime(ts: float):
    return datetime(1601, 1, 1) + timedelta(seconds=ts/10000000)


def send_mail(mail_to, days_remaining, subject, content):
    mail_from = CONFIG['mail_from']

    msg = MIMEMultipart("alternative")
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg["Subject"] = subject
    msg.attach(MIMEText(content.format(days_remaining=days_remaining), "plain"))
    sendmail = Popen(["/usr/sbin/sendmail", "-t"], stdin=PIPE)
    sendmail.communicate(msg.as_string().encode())


def check_password_expiry(users):
    for user in users:
        if user['pwdLastSet'] == '0' or int(user['userAccountControl']) & 2:
            # has never set password, account is locked
            continue

        last_password_change_date = ldap2datetime(float(user['pwdLastSet']))
        days_since_password_change = (datetime.now() - last_password_change_date).days
        days_remaining = CONFIG['password_max_age'] - days_since_password_change

        if days_remaining in CONFIG['notice_days']:
            print('Sending email to {}: password expires in {} days'.format(user['mail'], days_remaining))
            subject = CONFIG['notice_subject'].format(days_remaining)
            send_mail(user['mail'], days_remaining, subject, MAIL_NOTICE_TEXT)

        if days_remaining in CONFIG['warning_days']:
            print('Sending email to {}: password expires in {} days'.format(user['mail'], days_remaining))
            subject = CONFIG['warning_subject'].format(days_remaining)
            send_mail(user['mail'], days_remaining, subject, MAIL_WARNING_TEXT)

        # elif days_since_password_change > CONFIG['password_max_age']:
        #     days_since_password_expired = days_since_password_change - CONFIG['password_max_age']
        #     print('User {}: password expired for {} days'.format(user['mail'].split('@')[0],
        #           days_since_password_expired))
        # else:
        #     print('User {}: expires in {} days'.format(user['mail'].split('@')[0], days_remaining))


def main():
    global CONFIG, MAIL_NOTICE_TEXT, MAIL_WARNING_TEXT
    with open('{}/config.json'.format(FILE_PATH), 'r') as fh:
        CONFIG = json.load(fh)

    with open('{}/mail_notice.txt'.format(FILE_PATH), 'r') as fh:
        MAIL_NOTICE_TEXT = fh.read()

    with open('{}/mail_warning.txt'.format(FILE_PATH), 'r') as fh:
        MAIL_WARNING_TEXT = fh.read()

    records = lds.search(CONFIG['ldap']['uri'], CONFIG['ldap']['user_dn'], 'sub', '(objectClass=user)',
                         ['pwdLastSet', 'mail', 'userAccountControl'], verify_cert=not debug,
                         user=CONFIG['ldap']['user'], password=CONFIG['ldap']['password'])

    check_password_expiry(records)


if __name__ == '__main__':
    main()
