from datetime import datetime
from typing import Optional, List
import requests
import hashlib
import base64
import hmac
from collections import OrderedDict
from hashlib import sha256
from urllib import parse

import qingcloud.qai
from qingcloud.misc.json_tool import json_dump
from qingcloud.qai.constants import GET_TRAINS, WORK_GROUP, TRAINS_METRICS, GET_RESOURCE_GROUP, SHARE_RESOURCE_GROUP


class QAIConnection():
    """
    Public connection to QAI.
    """
    def __init__(self, qy_access_key_id, qy_secret_access_key, zone, host="ai.coreshub.cn", port=443,
                 protocol="https"):
        self.qy_access_key_id = qy_access_key_id
        self.qy_secret_access_key = qy_secret_access_key
        self.zone = zone
        self.host = host
        self.port = port
        self.protocol = protocol

    # Send request to QAI.
    def send_request(self, url="", method="", params=None, body=None, headers=None, timeout=5):
        if headers:
            headers["Channel"] = "api"
        else:
            headers = {"Channel": "api"}
        signature = QAISignatureAuthHandler.generate_signature(method=method, url=url, ak=self.qy_access_key_id,
                                                               sk=self.qy_secret_access_key,
                                                               params=params)
        try:
            if method == "GET":
                path = f"{self.protocol}://{self.host}:{self.port}{url}?{signature}"
                response = requests.get(path, headers=headers, timeout=timeout)
                return response.text
            if method == "POST":
                path = f"{self.protocol}://{self.host}:{self.port}{url}?{signature}"
                response = requests.post(path, headers=headers, json=body, timeout=timeout)
                return response.text
            if method == "DELETE":
                path = f"{self.protocol}://{self.host}:{self.port}{url}?{signature}"
                response = requests.delete(path, headers=headers, timeout=timeout)
                return response.text
        except requests.exceptions.Timeout:
            print("Connection timed out.")
            raise Exception("Connection timed out.")
        except requests.exceptions.RequestException:
            print("Connection failed.")
            raise Exception("Connection failed.")
        except Exception as e:
            raise e

    # User
    def get_user_info(self):
        url = WORK_GROUP
        params = {
            'zone': self.zone
        }
        resp = self.send_request(url=url, method="GET", params=params)
        return resp

    # Resource Group
    def get_resource_groups(self, offset: int = 0, limit: int = 20, reverse: bool = False, order_by: str = "created_at", search_word: str = ""):
        url = GET_RESOURCE_GROUP
        params = {
            'zone': self.zone,
            'offset': offset,
            'limit': limit,
            'reverse': reverse,
            'order_by': order_by,
            'search_word': search_word
        }
        resp = self.send_request(url=url, method="GET", params=params)
        return resp

    def get_share_users(self, rg_id: str = "", offset: int = 0, limit: int = 20):
        url = SHARE_RESOURCE_GROUP
        params = {
            'zone': self.zone,
            'rg_id': rg_id,
            'offset': offset,
            'limit': limit,
        }
        resp = self.send_request(url=url, method="GET", params=params)
        return resp

    def share_resource_group(self, rg_id: str, is_all: int = 1, share_user_ids: Optional[List[str]] = []):
        """
        @param rg_id: The id of resource group you want to select.
        @param is_all: It has two values, 0 and 1. 1 represents sharing all sub accounts,
                       and 0 represents sharing sub accounts under share_user_ids
        @param share_user_ids: Share sub accounts under share_user_ids.
        """
        url = SHARE_RESOURCE_GROUP
        params = {
            'zone': self.zone,
        }
        body = {
            'rg_id': rg_id,
            'is_all': is_all,
            'share_user_ids': share_user_ids
        }
        resp = self.send_request(url=url, method="POST", params=params, body=body)
        return resp

    def remove_shared_resource_group(self, rg_id: str, is_all: int = 0, share_user_ids: Optional[List[str]] = []):
        """
        @param rg_id: The id of resource group you want to select.
        @param is_all: It has two values, 0 and 1. 1 represents remove all sub accounts,
                       and 0 represents remove sub accounts under share_user_ids
        @param share_user_ids: Reomve shared sub accounts under share_user_ids.
        """
        url = SHARE_RESOURCE_GROUP
        params = {
            'zone': self.zone,
            'rg_id': rg_id,
            'is_all': is_all,
            'share_user_ids': share_user_ids
        }
        resp = self.send_request(url=url, method="DELETE", params=params)
        return resp

    # Train
    def get_trains(self, namespace: str = "ALL", name: str = '', image_name: str = '', reverse: bool = False, offset: int = 0, limit: int = 100, order_by: Optional[str] = None,
                   status: Optional[List[str]] = None, endpoints: Optional[List[str]] = None, start_at: Optional[datetime] = None,
                   end_at: Optional[datetime] = None, owner: Optional[str] = None):
        url = GET_TRAINS.format(namespace)
        params = {
            'namespace': namespace,
            'zone': self.zone,
            'name': name,
            'image_name': image_name,
            'reverse': reverse,
            'offset': offset,
            'limit': limit,
            'order_by': order_by,
            'status': status,
            'endpoints': endpoints,
            'start_at': start_at,
            'end_at': end_at,
            'owner': owner
        }
        # Remove keys with a value of None
        params = {k: v for k, v in params.items() if v is not None}
        resp = self.send_request(url=url, method="GET", params=params)
        return resp

    def trains_metrics(self, resource_ids: List[str], namespace: str = "ALL"):
        if len(resource_ids) == 0:
            raise Exception("resource_ids cannot be empty.")
        url = TRAINS_METRICS.format(namespace)
        params = {
            'namespace': namespace,
            'zone': self.zone,
            'resource_ids': resource_ids
        }
        # Remove keys with a value of None
        params = {k: v for k, v in params.items() if v is not None}
        resp = self.send_request(url=url, method="GET", params=params)
        return resp


class QAISignatureAuthHandler():
    """
    QAISignatureAuthHandler is used to authenticate QAI.
    """
    @staticmethod
    def generate_signature(method: str, url: str, ak: str, sk: str, params: dict):
        """
        :param url: /api/test/  must be end /
        :param ak: access_key_id
        :param sk:  secure_key
        :param params: dict type
        :param method: method GET POST PUT DELETE
        :return:
        """
        url += "/" if not url.endswith("/") else ""
        params["access_key_id"] = ak
        sorted_param = OrderedDict()
        keys = sorted(params.keys())
        for key in keys:
            if isinstance(params[key], list):
                sorted_param[key] = sorted(params[key])
            else:
                sorted_param[key] = params[key]

        # generate url.
        url_param_parts = []
        for key, values in sorted_param.items():
            if not isinstance(values, list):
                url_param_parts.append(f"{key}={values}")
            else:
                for value in values:
                    url_param_parts.append(f"{key}={value}")

        url_param = '&'.join(url_param_parts)
        string_to_sign = method + "\n" + url + "\n" + url_param + "\n" + hex_encode_md5_hash("")

        h = hmac.new(sk.encode(encoding="utf-8"), digestmod=sha256)
        h.update(string_to_sign.encode(encoding="utf-8"))
        sign = base64.b64encode(h.digest()).strip()
        signature = parse.quote_plus(sign)
        url_param += "&signature=%s" % signature
        return url_param


def hex_encode_md5_hash(data):
    if not data:
        data = "".encode("utf-8")
    else:
        data = data.encode("utf-8")
    md5 = hashlib.md5()
    md5.update(data)
    return md5.hexdigest()

