"""
    The implementation of the Facebook Client
"""

from . import auth
from .utils import Json2ObjectsFactory
import requests

try:
    #python 3
    from urllib.parse import parse_qsl, urlencode
    from urllib.request import urlopen
except:
    #python 2
    from urlparse import parse_qsl, parse_qs
    from urllib import urlencode, urlopen

import json

class FacebookClient(object):
    """
        This class implements the interface to the Facebook Graph API
    """

    FACEBOOK_URL = "https://www.facebook.com/"
    GRAPH_URL = "https://graph.facebook.com/v5.0/"
    API_URL = "https://api.facebook.com/"

    BASE_AUTH_URL = "%sdialog/oauth?" % FACEBOOK_URL
    DIALOG_BASE_URL = "%sdialog/feed?" % FACEBOOK_URL
    FBQL_BASE_URL = "%sfql?" % GRAPH_URL
    BASE_TOKEN_URL = "%soauth/access_token?" % GRAPH_URL

    DEFAULT_REDIRECT_URI = "http://www.facebook.com/connect/login_success.html"
    DEFAULT_SCOPE = ["email"]
    DEFAULT_DIALOG_URI = "http://www.example.com/response/"

     #A factory to make objects from a json
    factory = Json2ObjectsFactory()

    def __init__(self, app_id, access_token=None, raw_data=False, permissions=None):

        self.app_id = app_id
        self.access_token = access_token
        self.raw_data = raw_data

        if permissions is None:
            self.permissions = self.DEFAULT_SCOPE
        else:
            self.permissions = permissions

        self.expires = None

    def _make_request(self, url, data=None):
        """
            Makes a simple request. If not data is a GET else is a POST.
        """
        if not data:
            data = None
        else:
            pass
            #try:
            #    data = data.encode("utf-8")
            #except:
            #    pass

        if data:
            return requests.post(url, data=data).content
        else:
            params={}
            if "?" in url:
                params = parse_qs(url.split("?")[1])
                params = { key: params[key][0] for key in params.keys() }

            response = requests.get(url.split("?")[0], data=params)
            return response.content

    def _make_auth_request(self, path, extra_params=None, **data):
        """
            Makes a request to the facebook Graph API.
            This method requires authentication!
            Don't forget to get the access token before use it.
        """
        if self.access_token is None:
            raise PyfbException("Must Be authenticated. Did you forget to get the access token?")

        if "?" not in path:
            sep = "?"
        else:
            sep = "&"

        token_url = "%saccess_token=%s" % (sep, self.access_token)

        url = "%s%s%s" % (self.GRAPH_URL, path, token_url)
        if extra_params:
            url = "%s&%s" % (url, extra_params)

        if data:
            post_data = data
        else:
            post_data = None

        return self._make_request(url, post_data)

    def _make_object(self, name, data):
        """
            Uses the factory to make an object from a json
        """
        if not self.raw_data:
            return self.factory.make_object(name, data)
        return self.factory.loads(data)

    def _get_url_path(self, dic):

        return urlencode(dic)

    def _get_auth_url(self, params, redirect_uri):
        """
            Returns the authentication url
        """
        if redirect_uri is None:
            redirect_uri = self.DEFAULT_REDIRECT_URI
        params['redirect_uri'] = redirect_uri

        url_path = self._get_url_path(params)
        url = "%s%s" % (self.BASE_AUTH_URL, url_path)
        return url

    def _get_permissions(self):

        return ",".join(self.permissions)

    def get_auth_token_url(self, redirect_uri):
        """
            Returns the authentication token url
        """
        params = {
            "client_id": self.app_id,
            "type": "user_agent",
            "scope": self._get_permissions(),
        }
        return self._get_auth_url(params, redirect_uri)

    def get_auth_code_url(self, redirect_uri, state=None):
        """
            Returns the url to get a authentication code
        """
        params = {
            "client_id": self.app_id,
            "scope": self._get_permissions(),
        }

        if state:
            params['state'] = state

        return self._get_auth_url(params, redirect_uri)

    def get_access_token(self, app_secret_key, secret_code, redirect_uri):

        if redirect_uri is None:
            redirect_uri = self.DEFAULT_REDIRECT_URI

        self.secret_key = app_secret_key

        url_path = self._get_url_path({
            "client_id": self.app_id,
            "client_secret" : app_secret_key,
            "redirect_uri" : redirect_uri,
            "code" : secret_code,
        })
        url = u"%s%s" % (self.BASE_TOKEN_URL, url_path)

        data = self._make_request(url)

        try:
            data = json.loads(data)
        except:
            #old facebook api didn't use json. Keep it just in case...
            data = dict(parse_qsl(data))

        if not "access_token" in data:
            ex = self.factory.make_object('Error', data)
            raise PyfbException(ex.error.message)

        self.access_token = data.get('access_token')
        self.expires = data.get('expires')
        return self.access_token

    def exchange_token(self, app_secret_key, exchange_token):

        self.secret_key = app_secret_key

        url_path = self._get_url_path({
            "grant_type": 'fb_exchange_token',
            "client_id": self.app_id,
            "client_secret" : app_secret_key,
            "fb_exchange_token" : exchange_token,
            })
        url = "%s%s" % (self.BASE_TOKEN_URL, url_path)

        data = self._make_request(url)

        if not "access_token" in data:
            ex = self.factory.make_object('Error', data)
            raise PyfbException(ex.error.message)

        try:
            data = json.loads(data)
        except:
            #old facebook api didn't use json. Keep it just in case...
            data = dict(parse_qsl(data))

        self.access_token = data.get('access_token')
        self.expires = data.get('expires')
        return self.access_token, self.expires

    def get_dialog_url(self, redirect_uri):

        if redirect_uri is None:
            redirect_uri = self.DEFAULT_DIALOG_URI

        url_path = self._get_url_path({
            "app_id" : self.app_id,
            "redirect_uri": redirect_uri,
        })
        url = "%s%s" % (self.DIALOG_BASE_URL, url_path)
        return url

    def get_one(self, path, object_name, extra_params=None):
        """
            Gets one object
        """
        data = self._make_auth_request(path, extra_params=extra_params)
        obj = self._make_object(object_name, data)

        if hasattr(obj, 'error'):
            raise PyfbException(obj.error.message)

        return obj

    def get_list(self, id, path, object_name=None):
        """
            Gets A list of objects
        """
        if id is None:
            id = "me"
        if object_name is None:
            object_name = path
        path = "%s/%s" % (id, path.lower())

        obj = self.get_one(path, object_name)
        obj_list = self.factory.make_paginated_list(obj, object_name)

        if obj_list == False:
            obj_list = obj.get("data")

        return obj_list

    def push(self, id, path, **data):
        """
            Pushes data to facebook
        """
        if id is None:
            id = "me"
        path = "%s/%s" % (id, path)
        response = self._make_auth_request(path, **data)
        return self._make_object("response", response)

    def delete(self, id):
        """
            Deletes a object by id
        """
        data = {"method": "delete"}
        response = self._make_auth_request(id, **data)
        return self._make_object("response", response)

    def _get_table_name(self, query):
        """
            Try to get the table name from a fql query
        """
        KEY = "FROM"
        try:
            index = query.index(KEY) + len(KEY) + 1
            table = query[index:].strip().split(" ")[0]
            return table
        except Exception as e:
            raise PyfbException("Invalid FQL Syntax")

    def execute_fql_query(self, query):
        """
            Executes a FBQL query and return a list of objects
        """
        table = self._get_table_name(query)
        url_path = self._get_url_path({'q' : query, 'access_token' : self.access_token, 'format' : 'json'})
        url = "%s%s" % (self.FBQL_BASE_URL, url_path)
        data = self._make_request(url)

        objs = self.factory.make_objects_list(table, data)

        if hasattr(objs, 'error'):
            raise PyfbException(objs.error.message)

        return objs


class PyfbException(Exception):
    """
        A PyFB Exception class
    """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
