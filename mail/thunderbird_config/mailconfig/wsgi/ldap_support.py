import ldap
import sys


class LdapSupport:
    def __init__(self, uri, verify_cert=True, user='', password=''):
        # if not verify_cert:
        #     ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

        ldap.set_option(ldap.OPT_REFERRALS, 0)  # https://github.com/python-ldap/python-ldap/issues/275
        self.conn = ldap.initialize(uri)
        try:
            self.conn.start_tls_s()
        except ldap.LDAPError as e:
            self._print_error('Cannot start TLS', e)

        try:
            self.conn.protocol_version = ldap.VERSION3
            self.conn.simple_bind_s(user, password)
        except ldap.INVALID_CREDENTIALS:
            self._print_error("Bind_dn or bind_pw incorrect!")
        except ldap.LDAPError as e:
            self._print_error('Ldap bind failed', e)

    def __del__(self):
        if self.conn:
            self.conn.unbind_s()

    @staticmethod
    def _print_error(msg, err=None):
        print(msg)
        if err:
            print(err)
        sys.exit(0)

    @staticmethod
    def _load_scope(search_scope):
        scopes = {
            'base': ldap.SCOPE_BASE,
            'onelevel': ldap.SCOPE_ONELEVEL,
            'sub': ldap.SCOPE_SUBTREE,
        }
        if search_scope not in scopes:
            raise ValueError('Invalid search scope specified was {}, valid options {}'.format(search_scope,
                                                                                              scopes.keys()))
        return scopes[search_scope]

    @staticmethod
    def _extract_entry(dn, attrs, attrlist):
        if dn is None:
            return None
        extracted = {'dn': dn}
        for key, value in attrs.items():
            if isinstance(value, list):
                value = value[0].decode() if len(value) == 1 else [v.decode() for v in value]

            if attrlist is None or key in attrlist:
                extracted[key] = value
        return extracted

    def search(self, base_dn, search_scope, search_filter, attrs):
        try:
            response = self.conn.search_s(base_dn, self._load_scope(search_scope),
                                          filterstr=search_filter, attrlist=attrs, attrsonly=False)

            results = [self._extract_entry(result[0], result[1], attrs) for result in response if result[0] is not None]
            return results
        except ldap.NO_SUCH_OBJECT:
            self._print_error('Base not found: {}'.format(base_dn))
        except ldap.LDAPError as e:
            self._print_error('Ldap query error', e)


def search(ldap_uri, base_dn, scope, search_filter, attrs, verify_cert=True, user='', password=''):
    ldap_s = LdapSupport(ldap_uri, verify_cert=verify_cert, user=user, password=password)
    ldap_info = ldap_s.search(base_dn, scope, search_filter, attrs)
    return ldap_info
